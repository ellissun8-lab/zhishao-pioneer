from fastapi import APIRouter
from pydantic import BaseModel

from ..service import world_service
from ..simulation.engine import SimulationEngine
from ..simulation.strategies import Strategy

router = APIRouter(prefix="/simulation", tags=["simulation"])


class SimulationRequest(BaseModel):
    strategy: Strategy
    horizon_minutes: int = 10


@router.post("/run")
def run_simulation(request: SimulationRequest):
    return SimulationEngine().run(world_service.state, request.strategy, request.horizon_minutes)


@router.get("/compare")
def compare_strategies(horizon_minutes: int = 10):
    return SimulationEngine().compare(world_service.state, horizon_minutes)

