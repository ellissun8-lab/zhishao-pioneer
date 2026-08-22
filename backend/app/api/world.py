from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..behavior.prediction import predict_world_state
from ..perception import real_cv
from ..service import world_service

router = APIRouter(prefix="/world", tags=["world"])


class TickRequest(BaseModel):
    steps: int = Field(1, ge=1, le=20)
    dt_seconds: float = Field(15, ge=1, le=120)


@router.get("/state")
def get_world_state():
    return world_service.state


@router.get("/predict")
def predict(horizon_minutes: int = Query(default=10)):
    if horizon_minutes not in {5, 10, 30}:
        raise HTTPException(400, "horizon_minutes must be one of 5, 10, 30")
    return predict_world_state(world_service.state, horizon_minutes)


@router.post("/reset")
def reset(seed: int | None = None):
    world_service.reset(seed)
    real_cv.clear_last_detection_summary()
    return world_service.state


@router.post("/advance")
def advance():
    return world_service.advance_demo()


@router.post("/tick")
def tick(request: TickRequest | None = None):
    body = request or TickRequest()
    return world_service.tick(body.steps, body.dt_seconds)
