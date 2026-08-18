"""P2-1 ~ P2-4 专项测试：Ontology 校验、状态机合法转换、Crowd 感知/行为分层、Zone 状态性风险、What-if 隔离。"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.behavior.rules import EVENT_RULES
from backend.app.behavior.scoring import calculate_risk
from backend.app.data.seed import create_demo_state
from backend.app.main import app
from backend.app.ontology.models import BehaviorState, EventType, Position
from backend.app.ontology.relations import make_relation
from backend.app.perception.mock_cv import MockCVProvider
from backend.app.service import world_service
from backend.app.world.event_bus import EventBus
from backend.app.world.state_machine import transition
from backend.app.world.updater import WorldStateUpdater

client = TestClient(app)


def setup_function():
    world_service.reset()


# ---------- P2-1 Ontology 校验 ----------

def test_position_rejects_invalid_coordinates():
    with pytest.raises(ValidationError):
        Position(lng=200, lat=23.1291)
    with pytest.raises(ValidationError):
        Position(lng=113.2644, lat=95)


def test_api_rejects_invalid_event_type():
    response = client.post("/api/events", json={"type": "Teleported", "subject_id": "agent_A"})
    assert response.status_code == 422


def test_api_rejects_event_missing_subject():
    response = client.post("/api/events", json={"type": "MoveStarted"})
    assert response.status_code == 422


def test_api_rejects_invalid_event_position():
    response = client.post(
        "/api/events",
        json={"type": "ZoneEntered", "subject_id": "agent_A", "object_id": "school_zone_001", "metadata": {"position": {"lng": 999, "lat": 23.1}}},
    )
    assert response.status_code == 422


def test_api_rejects_invalid_risk_level():
    response = client.post("/api/agents", json={"id": "agent_X", "position": {"lng": 113.2644, "lat": 23.1291}, "risk_level": "extreme"})
    assert response.status_code == 422


def test_make_relation_rejects_unknown_predicate():
    with pytest.raises(ValueError):
        make_relation("agent_A", "located_in", "school_zone_001")


def test_zone_entered_and_crowd_create_ontology_relations():
    state = create_demo_state(3)
    bus = EventBus(state)
    bus.publish(EventFactory(EventType.ZONE_ENTERED, "agent_A", "school_zone_001"))
    bus.publish(
        EventFactory(EventType.CROWD_GATHERED, "agent_A", "school_zone_001", metadata={"agent_ids": ["agent_A", "agent_B", "agent_C"]})
    )
    triples = {(r.subject_id, r.predicate, r.object_id) for r in state.relations}
    assert ("agent_A", "enters", "school_zone_001") in triples
    assert ("agent_A", "gathers_with", "agent_B") in triples
    assert ("agent_A", "gathers_with", "agent_C") in triples
    bus.publish(EventFactory(EventType.CROWD_DISPERSED, "agent_A", "school_zone_001"))
    assert all(relation.predicate != "gathers_with" for relation in state.relations)


def EventFactory(event_type, subject_id, object_id=None, metadata=None):
    from backend.app.ontology.models import Event

    return Event(type=event_type, subject_id=subject_id, object_id=object_id, metadata=metadata or {})


# ---------- P2-2 状态机 ----------

def test_legal_state_transitions():
    assert transition(EventType.MOVE_STARTED, BehaviorState.IDLE) == BehaviorState.MOVING
    assert transition(EventType.ZONE_ENTERED, BehaviorState.MOVING) == BehaviorState.ENTERING_SENSITIVE_ZONE
    assert transition(EventType.CROWD_GATHERED, BehaviorState.ENTERING_SENSITIVE_ZONE) == BehaviorState.GATHERING
    assert transition(EventType.RISK_OBJECT_DETECTED, BehaviorState.GATHERING) == BehaviorState.RISK_ESCALATING
    assert transition(EventType.CROWD_DISPERSED, BehaviorState.RISK_ESCALATING) == BehaviorState.DISPERSING
    assert transition(EventType.MOVE_STOPPED, BehaviorState.DISPERSING) == BehaviorState.IDLE


def test_illegal_state_transitions_return_none():
    assert transition(EventType.MOVE_STOPPED, BehaviorState.IDLE) is None
    assert transition(EventType.ZONE_EXITED, BehaviorState.IDLE) is None
    assert transition(EventType.CROWD_DISPERSED, BehaviorState.IDLE) is None
    assert transition(EventType.CROWD_GATHERED, BehaviorState.IDLE) is None


def test_intervention_resolves_from_any_state():
    for current in BehaviorState:
        assert transition(EventType.INTERVENTION_APPLIED, current) == BehaviorState.RESOLVED


def test_updater_rejects_and_records_illegal_transition():
    state = create_demo_state(5)
    event = EventFactory(EventType.MOVE_STOPPED, "agent_D")  # agent_D 初始 idle，idle+MoveStopped 非法
    WorldStateUpdater().apply(state, event)
    assert state.agents["agent_D"].behavior_state == BehaviorState.IDLE
    assert event.metadata.get("rejected_transition") == "idle + MoveStopped"


# ---------- P2-3 CrowdDetected / CrowdGathered 分层 ----------

def test_mock_cv_crowd_is_perception_fact_not_behavior_event():
    event = MockCVProvider().detect("crowd", "agent_A")
    assert event.type == EventType.CROWD_DETECTED
    assert event.type != EventType.CROWD_GATHERED


def test_crowd_detection_weight_is_lower_than_confirmed_gathering():
    assert EVENT_RULES[EventType.CROWD_DETECTED].weight < EVENT_RULES[EventType.CROWD_GATHERED].weight


def test_perception_and_behavior_crowd_events_coexist_in_world_state():
    state = create_demo_state(3)
    bus = EventBus(state)
    bus.publish(MockCVProvider().detect("crowd", "agent_A"))
    bus.publish(EventFactory(EventType.CROWD_GATHERED, "agent_A", "school_zone_001", metadata={"agent_ids": ["agent_A", "agent_B"]}))
    types = [event.type for event in state.active_events]
    assert EventType.CROWD_DETECTED in types
    assert EventType.CROWD_GATHERED in types
    contributions = state.risk_state.rule_contributions
    assert contributions["CrowdDetected"] < contributions["CrowdGathered"]


def test_api_crowd_detection_returns_crowddetected():
    response = client.post("/api/perception/mock", json={"detection": "crowd", "subject_id": "agent_A"})
    assert response.status_code == 200
    assert response.json()["event"]["type"] == "CrowdDetected"


# ---------- P2-4 Zone 风险：State 而非 Event，不随时间衰减 ----------

def test_zone_risk_persists_while_inside_and_not_time_decayed():
    state = create_demo_state(3)
    updater = WorldStateUpdater()
    updater.apply(state, EventFactory(EventType.ZONE_ENTERED, "agent_A", "school_zone_001"))
    one_hour_later = datetime.now(timezone.utc) + timedelta(hours=1)
    risk_inside = calculate_risk(state, now=one_hour_later)
    assert risk_inside.rule_contributions["sensitive_zone"] == pytest.approx(18.0)
    assert any(contributor.type == "SensitiveZoneActive" for contributor in risk_inside.contributors)


def test_zone_risk_clears_after_exit():
    state = create_demo_state(3)
    updater = WorldStateUpdater()
    updater.apply(state, EventFactory(EventType.ZONE_ENTERED, "agent_A", "school_zone_001"))
    updater.apply(state, EventFactory(EventType.ZONE_EXITED, "agent_A", "school_zone_001"))
    risk_after = calculate_risk(state, now=datetime.now(timezone.utc))
    assert "sensitive_zone" not in risk_after.rule_contributions
    assert all(contributor.type != "SensitiveZoneActive" for contributor in risk_after.contributors)


# ---------- What-if 隔离 ----------

def test_what_if_simulation_does_not_mutate_live_world_state():
    before = client.get("/api/world/state").json()
    before.pop("timestamp")
    client.get("/api/simulation/compare").json()
    for strategy in ("none", "warn", "guide_leave", "intervene"):
        assert client.post("/api/simulation/run", json={"strategy": strategy}).status_code == 200
    after = client.get("/api/world/state").json()
    after.pop("timestamp")
    assert before == after
