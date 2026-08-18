from fastapi import APIRouter, HTTPException

from ..ontology.models import Agent
from ..service import world_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
def list_agents(limit: int = 80):
    return list(world_service.state.agents.values())[:limit]


@router.get("/{agent_id}")
def get_agent(agent_id: str):
    agent = world_service.state.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Synthetic agent not found")
    return agent


@router.post("", status_code=201)
def create_agent(agent: Agent):
    try:
        return world_service.add_agent(agent)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

