from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..behavior.prediction import predict_world_state
from ..service import world_service

router = APIRouter(prefix="/world", tags=["world"])


class TickRequest(BaseModel):
    steps: int = Field(1, ge=1, le=20)
    dt_seconds: float = Field(15, ge=1, le=120)


@router.get("/state")
def get_world_state():
    return world_service.state


@router.get("/predict")
def predict(horizon_minutes: int = 10):
    return predict_world_state(world_service.state, horizon_minutes)


@router.post("/reset")
def reset(seed: int | None = None):
    world_service.reset(seed)
    return world_service.state


@router.post("/advance")
def advance():
    return world_service.advance_demo()


@router.post("/tick")
def tick(request: TickRequest | None = None):
    body = request or TickRequest()
    return world_service.tick(body.steps, body.dt_seconds)
