"""LLM Agent API：Qwen3.8-Max 状态与多模态视觉理解。

/api/llm/status 绝不返回 API Key；connected 来自真实轻量调用（带 TTL 缓存），
不得伪造。/api/llm/vision/analyze 是 Qwen Vision 语义理解链路，
与 YOLO 结构化检测（bbox/class/confidence）严格分工，绝不冒充。
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..llm.providers.qwen import QwenAPIError, get_qwen_provider
from ..ml import registry
from ..perception import real_cv
from .perception import DEMO_TO_MOCK_SCENE, _resolve_demo_image

router = APIRouter(prefix="/llm", tags=["llm"])

VISION_NOTE = "Qwen Vision 为语义理解（scene understanding），不是 YOLO 检测；不产出 bbox / 检测类别 / 检测置信度，也不写入事件链。"

VISION_PROMPT = """你是“智哨先锋”推演系统的视觉语义分析模块。下图是程序化合成的模拟监控画面（Synthetic Visual Data，非真实场景）。
请只依据画面内容做语义理解，输出严格 JSON（不要 markdown 代码块、不要多余文字），字段：
{
  "estimated_people": <整数，画面中估计的人数>,
  "vehicle_visible": <布尔，是否有车辆>,
  "possible_risk_object": <布尔，是否疑似存在风险物品>,
  "crowd_semantics": "<一句话，人群/空间语义描述>",
  "summary": "<一两句话，整体场景语义总结>",
  "synthetic_visual_data": true
}"""


@router.get("/status")
def llm_status() -> dict[str, Any]:
    provider = get_qwen_provider()
    configured = provider.configured
    connected = False
    connection_error: str | None = provider.unconfigured_reason()
    if configured:
        connected, connection_error = provider.check_connection()
    return {
        "provider": "Alibaba Cloud Model Studio",
        "model": provider.model,
        "configured": configured,
        "connected": connected,
        "function_calling": True,
        "multimodal": True,
        "fallback": not connected,
        "fallback_reason": connection_error if not connected else None,
        "components": {
            "cv_detector": {
                "name": "YOLO26n",
                "status": "TRAINED" if real_cv.model_version_from_metrics() else "MISSING",
                "model_version": real_cv.model_version_from_metrics(),
                "model_path": "models/cv_detector/best.pt",
                "available": real_cv.RealCVProvider.model_available(),
            },
            "risk_forecast": {
                "name": "HistGradientBoostingRegressor",
                "status": "LOADED" if registry.risk_model_available() else "FALLBACK",
                "model_version": registry.status().get("risk_model_version"),
            },
            "policy_model": {
                "name": "HistGradientBoostingClassifier",
                "status": "LOADED" if registry.policy_model_available() else "FALLBACK",
                "model_version": registry.status().get("policy_model_version"),
            },
        },
    }


class VisionAnalyzeRequest(BaseModel):
    demo_scene_id: str = Field(default="demo_high_risk")
    prompt: str | None = None


_VISION_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _parse_vision_json(content: str) -> dict[str, Any] | None:
    match = _VISION_JSON_PATTERN.search(content)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_vision_structured(parsed: dict[str, Any]) -> dict[str, Any]:
    """补齐/规范字段；synthetic_visual_data 恒为 true（输入就是合成图）。"""
    people_value = parsed.get("estimated_people")
    try:
        estimated_people = max(0, int(people_value or 0))
    except (TypeError, ValueError, OverflowError):
        estimated_people = 0

    def coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "是"}
        return False

    return {
        "estimated_people": estimated_people,
        "vehicle_visible": coerce_bool(parsed.get("vehicle_visible")),
        "possible_risk_object": coerce_bool(parsed.get("possible_risk_object")),
        "crowd_semantics": str(parsed.get("crowd_semantics") or ""),
        "summary": str(parsed.get("summary") or ""),
        "synthetic_visual_data": True,
    }


@router.post("/vision/analyze")
def vision_analyze(request: VisionAnalyzeRequest) -> dict[str, Any]:
    provider = get_qwen_provider()
    started = time.perf_counter()
    if request.demo_scene_id not in DEMO_TO_MOCK_SCENE:
        raise HTTPException(status_code=400, detail=f"unknown demo scene: {request.demo_scene_id}")
    if not provider.configured:
        return {
            "fallback": True,
            "provider": "Alibaba Cloud Model Studio",
            "model": provider.model,
            "note": f"Qwen3.8-Max Offline：{provider.unconfigured_reason()}；无法执行视觉语义理解。",
            "structured": None,
        }
    try:
        image_bytes = _resolve_demo_image(request.demo_scene_id)
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = request.prompt or VISION_PROMPT
        response = provider.vision_analyze(image_base64, "image/jpeg", prompt)
        structured = _parse_vision_json(response.get("content") or "")
        if structured is None:
            # 一次修复重试：强制只要 JSON
            retry = provider.vision_analyze(
                image_base64,
                "image/jpeg",
                prompt + "\n注意：只输出 JSON 本身，不要任何其它文字或代码块标记。",
            )
            structured = _parse_vision_json(retry.get("content") or "")
            if structured is not None:
                response = retry
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if structured is None:
            return {
                "fallback": False,
                "provider": "Alibaba Cloud Model Studio",
                "model": provider.model,
                "source": "Qwen3.8-Max Vision",
                "scene_id": request.demo_scene_id,
                "structured": None,
                "raw_content": response.get("content"),
                "parse_error": True,
                "request_id": response.get("request_id"),
                "latency_ms": latency_ms,
                "note": VISION_NOTE + "（本次未能解析出结构化 JSON）",
            }
        return {
            "fallback": False,
            "provider": "Alibaba Cloud Model Studio",
            "model": provider.model,
            "source": "Qwen3.8-Max Vision",
            "scene_id": request.demo_scene_id,
            "structured": _coerce_vision_structured(structured),
            "raw_content": response.get("content"),
            "request_id": response.get("request_id"),
            "latency_ms": latency_ms,
            "note": VISION_NOTE,
        }
    except QwenAPIError as error:
        return {
            "fallback": True,
            "provider": "Alibaba Cloud Model Studio",
            "model": provider.model,
            "note": f"Qwen3.8-Max Offline：{error.reason}；本次视觉理解不可用。",
            "structured": None,
        }


__all__ = ["router", "VISION_NOTE"]
