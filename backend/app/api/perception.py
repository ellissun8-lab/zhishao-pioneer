from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..perception.mock_cv import DEFAULT_SCENE_SUBJECTS, MockCVProvider
from ..service import world_service

router = APIRouter(prefix="/perception", tags=["perception"])


class DetectionRequest(BaseModel):
    detection: str
    subject_id: str | None = "agent_A"


@router.post("/mock")
def mock_detection(request: DetectionRequest):
    try:
        event = MockCVProvider().detect(request.detection, request.subject_id)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    state = world_service.publish(event)
    return {"event": event, "risk_state": state.risk_state}


class SceneDetectRequest(BaseModel):
    scene_id: str
    subject_ids: list[str] = Field(default_factory=lambda: list(DEFAULT_SCENE_SUBJECTS))


@router.post("/mock-cv/detect")
def mock_cv_scene_detect(request: SceneDetectRequest):
    """CV 场景识别：Detection -> Standard Event -> Event Bus -> World State / Risk Engine。"""
    try:
        result = MockCVProvider().detect_scene(request.scene_id, request.subject_ids)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    missing = [subject for subject in set(request.subject_ids) if subject not in world_service.state.agents]
    if missing:
        raise HTTPException(400, f"Unknown subject ids: {missing}")
    for event in result["events"]:
        world_service.publish(event)
    return {
        "scene_id": result["scene_id"],
        "synthetic": True,
        "detections": result["detections"],
        "events": result["events"],
        "risk_state": world_service.state.risk_state,
    }
