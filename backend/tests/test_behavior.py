from backend.app.behavior.scoring import calculate_risk
from backend.app.data.seed import create_demo_state
from backend.app.ontology.models import Event, EventType
from backend.app.simulation.engine import SimulationEngine
from backend.app.simulation.strategies import Strategy
from backend.app.world.updater import WorldStateUpdater


def test_normal_agent_in_normal_area_stays_low():
    state = create_demo_state(3)
    state.agents["agent_A"].risk_level = "low"
    state.agents["agent_A"].base_risk = 10
    state.risk_state = calculate_risk(state)
    assert state.risk_state.overall_score < 30


def test_high_risk_agent_entering_sensitive_zone_increases_risk():
    state = create_demo_state(3)
    before = state.risk_state.overall_score
    WorldStateUpdater().apply(state, Event(type=EventType.ZONE_ENTERED, subject_id="agent_A", object_id="school_zone_001"))
    assert state.risk_state.overall_score > before


def test_three_agent_crowd_adds_twenty_points_before_multiplier():
    state = create_demo_state(3)
    WorldStateUpdater().apply(state, Event(type=EventType.CROWD_GATHERED, subject_id="agent_A", confidence=1))
    assert state.risk_state.rule_contributions["CrowdGathered"] == 20


def test_risk_object_significantly_increases_risk():
    state = create_demo_state(3)
    before = state.risk_state.overall_score
    WorldStateUpdater().apply(state, Event(type=EventType.RISK_OBJECT_DETECTED, subject_id="agent_A", confidence=1))
    assert state.risk_state.overall_score - before >= 35


def test_warn_is_safer_than_no_intervention_and_does_not_mutate_state():
    state = create_demo_state(3)
    WorldStateUpdater().apply(state, Event(type=EventType.CROWD_GATHERED, subject_id="agent_A"))
    original = state.model_dump_json()
    engine = SimulationEngine()
    warn = engine.run(state, Strategy.WARN)
    none = engine.run(state, Strategy.NONE)
    assert warn.after.risk < none.after.risk
    assert state.model_dump_json() == original

