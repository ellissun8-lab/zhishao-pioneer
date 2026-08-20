"""Qwen3.8-Max Provider（Alibaba Cloud Model Studio，OpenAI-compatible API）。

固定模型 qwen3.8-max；禁止用 qwen3-max / qwen-plus / qwen3.8-max-preview 冒充正式模型。
API Key 只允许来自本地 .env / deployment secret，绝不入仓、绝不进任何 API 响应。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from openai import OpenAI

QWEN_MODEL = "qwen3.8-max"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
FORBIDDEN_MODELS = ("qwen3-max", "qwen-plus", "qwen3.8-max-preview")

# 连通性检查缓存（避免每次 /llm/status 都打一次真实 API）
_CONNECTION_CACHE_TTL_SECONDS = 30.0


class QwenAPIError(RuntimeError):
    """Qwen API 调用失败（timeout / 429 / 5xx / 网络错误），触发确定性回退。"""

    def __init__(self, reason: str, kind: str = "api_error") -> None:
        super().__init__(reason)
        self.reason = reason
        self.kind = kind  # timeout / rate_limit / server / network / api_error


class QwenProvider:
    def __init__(self, api_key: str | None, base_url: str | None, model: str | None) -> None:
        env_model = (model or "").strip()
        self.invalid_model_reason: str | None = None
        if env_model and env_model != QWEN_MODEL:
            forbidden = env_model in FORBIDDEN_MODELS
            self.invalid_model_reason = (
                f"QWEN_MODEL 必须固定为 {QWEN_MODEL}（检测到 {env_model}，"
                + ("禁用名单模型，禁止冒充正式模型" if forbidden else "非本项目固定模型")
                + "）"
            )
        self.api_key = (api_key or "").strip() or None
        self.base_url = (base_url or "").strip() or DEFAULT_BASE_URL
        # 模型名固定 qwen3.8-max；env 配置了其它名字时拒绝启用（configured=False）
        self.model = QWEN_MODEL
        self._client: OpenAI | None = None
        self._connection_cache: tuple[float, bool, str | None] = (0.0, False, None)
        self._lock = threading.Lock()

    # ---- 构造 ----
    @classmethod
    def from_env(cls) -> "QwenProvider":
        import os

        return cls(
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url=os.environ.get("DASHSCOPE_BASE_URL"),
            model=os.environ.get("QWEN_MODEL"),
        )

    @property
    def configured(self) -> bool:
        """只有 Key 存在且模型名合法时才可用。"""
        return bool(self.api_key) and self.invalid_model_reason is None

    def unconfigured_reason(self) -> str | None:
        if self.invalid_model_reason:
            return self.invalid_model_reason
        if not self.api_key:
            return "DASHSCOPE_API_KEY 未配置（仅允许本地 .env / deployment secret）"
        return None

    # ---- client（测试可注入 fake）----
    def _build_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def client(self) -> OpenAI:
        with self._lock:
            if self._client is None:
                self._client = self._build_client()
            return self._client

    def use_client(self, client: Any) -> None:
        """测试注入 fake OpenAI client（只替换网络边界，不碰 Agent 核心逻辑）。"""
        with self._lock:
            self._client = client
            self._connection_cache = (0.0, False, None)

    # ---- 调用 ----
    def _complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, **kwargs: Any) -> Any:
        if not self.configured:
            raise QwenAPIError(self.unconfigured_reason() or "provider not configured", kind="not_configured")
        request: dict[str, Any] = {"model": self.model, "messages": messages, **kwargs}
        if tools:
            request["tools"] = tools
        try:
            return self.client.chat.completions.create(**request)
        except Exception as error:  # noqa: BLE001 - openai 异常族统一包装
            reason, kind = _classify_openai_error(error)
            raise QwenAPIError(reason, kind) from error

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """普通文本对话（OpenAI-compatible chat.completions）。"""
        response = self._complete(messages, tools=None, **kwargs)
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "request_id": getattr(response, "id", None),
            "model": getattr(response, "model", self.model),
            "finish_reason": getattr(choice, "finish_reason", None),
        }

    def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Function Calling 对话：返回 content 与结构化 tool_calls。"""
        extra: dict[str, Any] = {"tool_choice": "auto"} if tools else {}
        response = self._complete(messages, tools=tools, **extra, **kwargs)
        choice = response.choices[0]
        message = choice.message
        raw_calls = getattr(message, "tool_calls", None) or []
        tool_calls = [
            {
                "id": call.id,
                "type": "function",
                "name": call.function.name,
                "arguments": call.function.arguments,
            }
            for call in raw_calls
            if getattr(call, "type", "function") == "function"
        ]
        return {
            "content": message.content or "",
            "tool_calls": tool_calls,
            "request_id": getattr(response, "id", None),
            "model": getattr(response, "model", self.model),
            "finish_reason": getattr(choice, "finish_reason", None),
        }

    def vision_analyze(self, image_base64: str, media_type: str = "image/jpeg", prompt: str = "") -> dict[str, Any]:
        """多模态视觉理解（qwen3.8-max multimodal；语义理解，绝不产出 YOLO bbox）。"""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_base64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        response = self._complete(messages, tools=None)
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "request_id": getattr(response, "id", None),
            "model": getattr(response, "model", self.model),
        }

    def check_connection(self) -> tuple[bool, str | None]:
        """轻量真实连通性检查（带 TTL 缓存）。"""
        if not self.configured:
            return False, self.unconfigured_reason()
        now = time.time()
        cached_at, cached_ok, cached_reason = self._connection_cache
        if now - cached_at < _CONNECTION_CACHE_TTL_SECONDS:
            return cached_ok, cached_reason
        try:
            self.chat([{"role": "user", "content": "ping"}], max_tokens=8, timeout=8)
            result = (True, None)
        except QwenAPIError as error:
            result = (False, error.reason)
        self._connection_cache = (now, result[0], result[1])
        return result


_provider: QwenProvider | None = None
_provider_lock = threading.Lock()


def get_qwen_provider() -> QwenProvider:
    global _provider
    with _provider_lock:
        if _provider is None:
            _provider = QwenProvider.from_env()
        return _provider


def reset_qwen_provider() -> None:
    """重新读取环境变量（测试用）。"""
    global _provider
    with _provider_lock:
        _provider = QwenProvider.from_env()


def _classify_openai_error(error: Exception) -> tuple[str, str]:
    text = f"{type(error).__name__}: {error}"
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return (f"Qwen API timeout: {text}", "timeout")
    if "429" in text or "rate limit" in lowered:
        return (f"Qwen API rate limited (429): {text}", "rate_limit")
    if any(code in text for code in ("500", "502", "503", "504")) or "server error" in lowered:
        return (f"Qwen API server error (5xx): {text}", "server")
    return (f"Qwen API unavailable: {text}", "network")
