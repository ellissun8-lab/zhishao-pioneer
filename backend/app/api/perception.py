from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..perception.mock_cv import MockCVProvider
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

