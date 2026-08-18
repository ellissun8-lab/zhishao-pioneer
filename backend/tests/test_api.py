from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.service import world_service

client = TestClient(app)


def setup_function():
    world_service.reset()


def test_health_and_state():
    assert client.get("/health").json() == {"status": "ok"}
    state = client.get("/api/world/state").json()
    assert len(state["agents"]) == 80
    assert all(agent["synthetic"] for agent in state["agents"].values())


def test_event_changes_risk():
    before = client.get("/api/world/state").json()["risk_state"]["overall_score"]
    response = client.post("/api/events", json={"type": "RiskObjectDetected", "subject_id": "agent_A", "confidence": 1})
    assert response.status_code == 201
    assert response.json()["risk_state"]["overall_score"] > before


def test_compare_and_chat_use_world_tools():
    comparisons = client.get("/api/simulation/compare").json()
    assert len(comparisons) == 4
    answer = client.post("/api/chat", json={"message": "为什么学校区域现在是红色？"}).json()
    assert answer["synthetic"] is True
    assert "get_risk_analysis" in answer["tools_used"]


def test_tick_runs_event_driven_simulation_and_records_audit():
    world_service.reset(42)
    response = client.post("/api/world/tick", json={"steps": 5, "dt_seconds": 120})
    assert response.status_code == 200
    payload = response.json()
    assert payload["events"], "tick should emit events through the Event Bus"
    assert len(payload["state"]["agents"]) == 80
    audit = client.get("/api/events/audit?limit=50").json()
    assert audit, "events must be persisted to SQLite audit log"
    assert all("subject_id" in record and "confidence" in record for record in audit)


def test_reset_with_seed_is_deterministic():
    def snapshot():
        client.post("/api/world/reset?seed=42")
        return client.get("/api/world/state").json()["agents"]["agent_D"]["position"]

    assert snapshot() == snapshot()


def test_vehicle_detection_increases_risk():
    before = client.get("/api/world/state").json()["risk_state"]["overall_score"]
    response = client.post("/api/perception/mock", json={"detection": "vehicle", "subject_id": "agent_A"})
    assert response.status_code == 200
    assert response.json()["risk_state"]["overall_score"] > before


def test_chat_prediction_uses_predict_tool():
    answer = client.post("/api/chat", json={"message": "未来10分钟会怎样？"}).json()
    assert answer["tools_used"] == ["predict_future"]
    assert answer["synthetic"] is True


def test_alert_triggered_when_risk_reaches_high():
    world_service.reset()
    client.post("/api/events", json={"type": "RiskObjectDetected", "subject_id": "agent_A", "confidence": 1})
    client.post("/api/events", json={"type": "CrowdGathered", "subject_id": "agent_A", "confidence": 1})
    client.post("/api/events", json={"type": "ZoneEntered", "subject_id": "agent_A", "object_id": "school_zone_001", "confidence": 1})
    events = client.get("/api/events").json()
    assert any(event["type"] == "AlertTriggered" for event in events)
    assert any(event["type"] == "ZoneEntered" for event in events)

