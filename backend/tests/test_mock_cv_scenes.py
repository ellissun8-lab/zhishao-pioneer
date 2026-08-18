import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ontology.models import EventType
from backend.app.perception.mock_cv import SCENE_CONFIDENCE, SCENE_LAYOUT, MockCVProvider
from backend.app.service import world_service

client = TestClient(app)

SCENE_IDS = ["scene_normal", "scene_crowd", "scene_risk_object", "scene_high_risk"]


def setup_function():
    world_service.reset()


def _detect(scene_id: str, subject_ids: list[str] | None = None):
    payload = {"scene_id": scene_id}
    if subject_ids:
        payload["subject_ids"] = subject_ids
    return client.post("/api/perception/mock-cv/detect", json=payload)


def _event_types(payload):
    return [event["type"] for event in payload["events"]]


def test_mock_cv_normal_scene():
    payload = _detect("scene_normal").json()
    assert payload["synthetic"] is True
    assert _event_types(payload) == ["PersonDetected"]
    assert [detection["label"] for detection in payload["detections"]] == ["person"]


def test_mock_cv_crowd_scene():
    payload = _detect("scene_crowd").json()
    types = _event_types(payload)
    assert types.count("PersonDetected") == 3
    assert "CrowdDetected" in types
    assert "CrowdGathered" not in types, "Mock CV 是感知层，禁止直接产出 CrowdGathered"


def test_mock_cv_risk_object_scene():
    payload = _detect("scene_risk_object").json()
    types = _event_types(payload)
    assert "PersonDetected" in types
    assert "RiskObjectDetected" in types
    risk_event = next(event for event in payload["events"] if event["type"] == "RiskObjectDetected")
    assert risk_event["metadata"]["display_name"] == "疑似风险物品"


def test_mock_cv_high_risk_scene():
    payload = _detect("scene_high_risk").json()
    types = _event_types(payload)
    assert types.count("PersonDetected") == 3
    assert "CrowdDetected" in types
    assert "RiskObjectDetected" in types


def test_cv_detection_bbox_valid():
    for scene_id in SCENE_IDS:
        payload = _detect(scene_id).json()
        for detection in payload["detections"]:
            bbox = detection["bbox"]
            for key in ("x", "y", "width", "height"):
                assert 0 <= bbox[key] <= 1, f"{scene_id} {detection['id']} bbox.{key} 越界"
            assert bbox["x"] + bbox["width"] <= 1.0001
            assert bbox["y"] + bbox["height"] <= 1.0001


def test_cv_confidence_valid():
    ranges = {"person": (0.92, 0.98), "crowd": (0.88, 0.95), "risk_object": (0.85, 0.93)}
    for scene_id in SCENE_IDS:
        payload = _detect(scene_id).json()
        for detection in payload["detections"]:
            low, high = ranges[detection["label"]]
            assert low <= detection["confidence"] <= high, f"{scene_id} {detection['label']} 置信度越界"
    # 同一场景重复识别结果必须完全稳定（固定 seed 语义，不随时间抖动）
    first = _detect("scene_high_risk").json()["detections"]
    second = _detect("scene_high_risk").json()["detections"]
    assert first == second


def test_cv_events_enter_event_bus():
    before = {event.id for event in world_service.state.active_events}
    payload = _detect("scene_high_risk").json()
    published_ids = {event["id"] for event in payload["events"]}
    after = {event.id for event in world_service.state.active_events}
    assert published_ids <= after - before, "识别事件必须经 Event Bus 写入 World State"


def test_cv_updates_world_state():
    before_events = len(world_service.state.active_events)
    _detect("scene_high_risk")
    assert len(world_service.state.active_events) >= before_events + 5
    # RiskObjectDetected 应推动主体状态机进入风险升级
    assert any(agent.behavior_state.value == "risk_escalating" for agent in world_service.state.agents.values())


def test_cv_updates_risk_through_event_only():
    before_events = list(world_service.state.active_events)
    before_risk = world_service.state.risk_state.overall_score
    result = MockCVProvider().detect_scene("scene_high_risk")
    # Provider 只返回 Detection + Event，不得直接触碰 World State / 风险数值（禁止 CV 按钮 risk += 35）
    assert set(result.keys()) == {"scene_id", "synthetic", "detections", "events"}
    assert world_service.state.active_events == before_events
    assert world_service.state.risk_state.overall_score == before_risk
    response = _detect("scene_high_risk")
    assert response.status_code == 200
    assert world_service.state.risk_state.overall_score > before_risk, "风险只能由 Risk Engine 基于事件计算"


def test_crowd_detected_not_equal_crowd_gathered():
    payload = _detect("scene_crowd").json()
    types = _event_types(payload)
    assert EventType.CROWD_DETECTED.value in types
    assert EventType.CROWD_GATHERED.value not in types
    # 分层约束：Mock CV 的所有入口（单目标 detect + 场景 detect_scene）都无法产出 CrowdGathered
    assert EventType.CROWD_GATHERED not in MockCVProvider.SUPPORTED.values()
    assert all(
        detection["label"] != "crowd_gathered"
        for scene_id in SCENE_IDS
        for detection in _detect(scene_id).json()["detections"]
    )


def test_unknown_scene_returns_4xx():
    assert _detect("scene_unknown").status_code == 400


def test_audit_records_cv_scene_payload():
    _detect("scene_risk_object")
    audit = client.get("/api/events/audit?limit=20").json()
    cv_records = [record for record in audit if record["source"] == "mock_cv"]
    assert cv_records, "CV 事件必须写入 SQLite 审计"
    risk_record = next(record for record in cv_records if record["event_type"] == "RiskObjectDetected")
    metadata = json.loads(risk_record["payload"])["metadata"]
    assert metadata["scene_id"] == "scene_risk_object"
    assert metadata["detection_id"]
    assert metadata["bbox"]
    assert metadata["display_name"] == "疑似风险物品"
    assert risk_record["confidence"] == SCENE_CONFIDENCE["risk_object"][0]


def test_scene_layout_covers_all_scenes():
    assert set(SCENE_LAYOUT) == set(SCENE_IDS)
