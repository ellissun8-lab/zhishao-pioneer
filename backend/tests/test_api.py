from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.perception import real_cv
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


def test_reset_clears_last_cv_inference_summary():
    real_cv.record_last_detection_summary({"provider": "real", "model_invoked": True})
    assert real_cv.get_last_detection_summary() is not None

    response = client.post("/api/world/reset")

    assert response.status_code == 200
    assert real_cv.get_last_detection_summary() is None


def test_invalid_prediction_and_simulation_horizons_return_4xx():
    for horizon in (0, 11, 999):
        assert 400 <= client.get(f"/api/world/predict?horizon_minutes={horizon}").status_code < 500
        assert 400 <= client.get(f"/api/simulation/compare?horizon_minutes={horizon}").status_code < 500
        assert 400 <= client.post(
            "/api/simulation/run",
            json={"strategy": "none", "horizon_minutes": horizon},
        ).status_code < 500


def test_valid_query_horizons_are_parsed_from_http_strings():
    """FastAPI query 参数来自字符串；合法 5/10/30 必须可被前端正常调用。"""
    for horizon in (5, 10, 30):
        assert client.get(f"/api/world/predict?horizon_minutes={horizon}").status_code == 200
        assert client.get(f"/api/simulation/compare?horizon_minutes={horizon}").status_code == 200


def test_blank_chat_and_invalid_agent_limit_return_4xx():
    assert 400 <= client.post("/api/chat", json={"message": "   "}).status_code < 500
    assert 400 <= client.get("/api/agents?limit=-1").status_code < 500


def test_event_and_mock_cv_reject_unknown_subject_ids():
    event = client.post(
        "/api/events",
        json={"type": "RiskObjectDetected", "subject_id": "missing_agent"},
    )
    mock = client.post(
        "/api/perception/mock",
        json={"detection": "person", "subject_id": "missing_agent"},
    )
    assert 400 <= event.status_code < 500
    assert 400 <= mock.status_code < 500


def test_duplicate_event_id_is_idempotent_and_does_not_double_risk():
    payload = {
        "id": "event_retry_same_id",
        "type": "RiskObjectDetected",
        "subject_id": "agent_A",
        "confidence": 1,
    }
    first = client.post("/api/events", json=payload)
    first_risk = first.json()["risk_state"]["overall_score"]
    second = client.post("/api/events", json=payload)
    second_risk = second.json()["risk_state"]["overall_score"]
    matching = [event for event in client.get("/api/events").json() if event["id"] == payload["id"]]

    assert first.status_code == 201 and second.status_code == 201
    assert len(matching) == 1
    assert second_risk == first_risk


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

