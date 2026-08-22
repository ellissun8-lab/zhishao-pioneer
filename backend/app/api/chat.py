from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from ..llm.agent import explain_question
from ..llm.qwen_agent import QwenUnavailableError, run_qwen_agent
from ..service import world_service

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


@router.post("")
def chat(request: ChatRequest):
    """优先真实 Qwen3.8-Max Function Calling；不可用时确定性 grounded 回退。

    fallback=true 时 answer 来自现有 deterministic grounded explanation，
    绝不伪造 Qwen request_id / connected 状态。
    """
    state = world_service.state
    try:
        return run_qwen_agent(request.message, state)
    except QwenUnavailableError as error:
        fallback = explain_question(request.message, state)
        fallback.update(
            {
                "provider": "deterministic_fallback",
                "model": None,
                "tool_rounds": 0,
                "request_id": None,
                "latency_ms": None,
                "fallback": True,
                "fallback_reason": f"Qwen3.8-Max Offline：{error}",
                "fallback_explanation": True,
            }
        )
        return fallback
