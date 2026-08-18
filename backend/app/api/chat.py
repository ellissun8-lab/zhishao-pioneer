from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..llm.agent import explain_question
from ..service import world_service

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


@router.post("")
def chat(request: ChatRequest):
    return explain_question(request.message, world_service.state)

