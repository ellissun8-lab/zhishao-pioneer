from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..service import world_service
from ..simulation.engine import SimulationEngine
from ..simulation.strategies import Strategy

router = APIRouter(prefix="/simulation", tags=["simulation"])


class SimulationRequest(BaseModel):
    strategy: Strategy
    horizon_minutes: Literal[5, 10, 30] = 10


@router.post("/run")
def run_simulation(request: SimulationRequest):
    return SimulationEngine().run(world_service.state, request.strategy, request.horizon_minutes)


@router.get("/compare")
def compare_strategies(horizon_minutes: int = Query(default=10)):
    if horizon_minutes not in {5, 10, 30}:
        raise HTTPException(400, "horizon_minutes must be one of 5, 10, 30")
    return SimulationEngine().compare(world_service.state, horizon_minutes)

