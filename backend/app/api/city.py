from fastapi import APIRouter

from ..service import world_service

router = APIRouter(prefix="/city", tags=["city"])


@router.get("")
def get_city():
    state = world_service.state
    return {"places": list(state.places.values()), "zones": list(state.zones.values()), "synthetic": True}

