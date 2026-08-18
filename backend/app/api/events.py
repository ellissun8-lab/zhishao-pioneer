from fastapi import APIRouter, Query

from ..database import query_events
from ..ontology.models import Event
from ..service import world_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events():
    return world_service.state.active_events


@router.get("/audit")
def audit_events(limit: int = Query(50, ge=1, le=500)):
    return query_events(limit)


@router.post("", status_code=201)
def create_event(event: Event):
    state = world_service.publish(event)
    return {"event": event, "risk_state": state.risk_state}
