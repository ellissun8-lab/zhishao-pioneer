"""Qwen3.8-Max Agent Integration 测试。

原则：只 fake OpenAI 网络边界（FakeClient），Function Calling 循环、Tool Adapter、
现有 AgentTools 业务函数全部真实执行，绝不 mock Agent 核心逻辑来制造 PASS。
"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.llm.prompts import SYSTEM_NOTICE
from backend.app.llm.providers import qwen as qwen_provider_module
from backend.app.llm.providers.qwen import (
    FORBIDDEN_MODELS,
    QWEN_MODEL,
    get_qwen_provider,
    reset_qwen_provider,
)
from backend.app.llm.qwen_agent import MAX_TOOL_ROUNDS, run_qwen_agent
from backend.app.llm.qwen_tools import TOOL_DEFINITIONS
from backend.app.llm.tools import AgentTools
from backend.app.main import app
from backend.app.perception import real_cv
from backend.app.service import world_service

client = TestClient(app)

TEST_KEY = "sk-test-secret-ABC123xyz"


# ---------- Fake OpenAI 网络 boundary ----------

class FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments_json: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments_json)


class FakeMessage:
    def __init__(self, content: str | None = None, tool_calls: list | None = None) -> None:
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message
        self.finish_reason = "tool_calls" if message.tool_calls else "stop"


class FakeResponse:
    def __init__(self, response_id: str, message: FakeMessage) -> None:
        self.id = response_id
        self.model = QWEN_MODEL
        self.choices = [FakeChoice(message)]


class FakeCompletions:
    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if callable(item):
            item = item(kwargs)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, script: list) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(script))


def tool_call_response(call_id: str, name: str, arguments: dict, response_id: str = "req-tool") -> FakeResponse:
    return FakeResponse(response_id, FakeMessage(tool_calls=[FakeToolCall(call_id, name, json.dumps(arguments))]))


def text_response(content: str, response_id: str = "req-final") -> FakeResponse:
    return FakeResponse(response_id, FakeMessage(content=content))


def _tool_messages(messages: list[dict]) -> list[dict]:
    return [message for message in messages if message["role"] == "tool"]


def _last_tool_json(messages: list[dict]) -> dict:
    return json.loads(_tool_messages(messages)[-1]["content"])


# ---------- fixtures ----------

@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch):
    world_service.reset()
    monkeypatch.setattr(real_cv, "_last_detection_summary", None)
    # 每个测试从“无 Key”干净状态开始（需要 Key 的测试自行调用 _configure）
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_MODEL", raising=False)
    reset_qwen_provider()
    yield
    reset_qwen_provider()


def _configure(monkeypatch: pytest.MonkeyPatch, script: list, key: str = TEST_KEY):
    """配置 provider（Key + fake 网络 client）；Agent 循环与工具仍为真实实现。"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", key)
    monkeypatch.setenv("QWEN_MODEL", QWEN_MODEL)
    reset_qwen_provider()
    provider = get_qwen_provider()
    fake = FakeClient(script)
    provider.use_client(fake)
    return provider, fake


# ---------- 模型名 ----------

def test_qwen_model_name(monkeypatch: pytest.MonkeyPatch):
    """模型固定 qwen3.8-max；禁用名单（qwen3-max/qwen-plus/qwen3.8-max-preview）绝不能成为生效模型。"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", TEST_KEY)
    monkeypatch.delenv("QWEN_MODEL", raising=False)
    reset_qwen_provider()
    assert get_qwen_provider().model == "qwen3.8-max"

    for forbidden in FORBIDDEN_MODELS:
        monkeypatch.setenv("QWEN_MODEL", forbidden)
        reset_qwen_provider()
        provider = get_qwen_provider()
        assert provider.model == QWEN_MODEL, f"{forbidden} 禁止冒充正式模型"
        assert provider.configured is False
        assert "冒充" in (provider.invalid_model_reason or "")

    monkeypatch.setenv("QWEN_MODEL", QWEN_MODEL)
    reset_qwen_provider()
    assert get_qwen_provider().configured is True


# ---------- /api/llm/status ----------

def test_qwen_status_no_secret(monkeypatch: pytest.MonkeyPatch):
    """status 端点：字段齐全、connected 来自真实调用、绝不泄漏 API Key。"""
    status = client.get("/api/llm/status").json()
    assert status["provider"] == "Alibaba Cloud Model Studio"
    assert status["model"] == "qwen3.8-max"
    assert status["configured"] is False and status["connected"] is False
    assert status["fallback"] is True and "DASHSCOPE_API_KEY" in status["fallback_reason"]

    _configure(monkeypatch, [text_response("pong", "req-status")])
    status = client.get("/api/llm/status").json()
    assert status["configured"] is True and status["connected"] is True
    assert status["fallback"] is False
    assert status["function_calling"] is True and status["multimodal"] is True
    assert status["components"]["cv_detector"]["status"] == "TRAINED"
    assert status["components"]["risk_forecast"]["status"] == "LOADED"
    assert status["components"]["policy_model"]["status"] == "LOADED"

    raw = json.dumps(status)
    assert TEST_KEY not in raw, "API Key 严禁出现在任何响应中"


# ---------- Function Calling 循环 ----------

def test_qwen_function_calling(monkeypatch: pytest.MonkeyPatch):
    """真实循环：user+tools -> tool_calls -> 执行现有 Tool -> tool message -> 最终回答。"""
    _configure(
        monkeypatch,
        [
            tool_call_response("call_1", "get_risk_analysis", {}),
            text_response("当前风险来自工具结果。", "req-final"),
        ],
    )
    result = run_qwen_agent("现在风险怎么样？", world_service.state)

    assert result["provider"] == "Alibaba Cloud Model Studio"
    assert result["model"] == "qwen3.8-max"
    assert result["tools_used"] == ["get_risk_analysis"]
    assert result["tool_rounds"] == 1
    assert result["request_id"] == "req-final"
    assert result["fallback"] is False
    assert result["answer"] == "当前风险来自工具结果。"
    assert result["latency_ms"] >= 0


def test_qwen_tool_result_roundtrip(monkeypatch: pytest.MonkeyPatch):
    """Tool 执行结果必须以 tool role message 回传给模型（grounding 数据链）。"""
    provider, fake = _configure(
        monkeypatch,
        [
            tool_call_response("call_9", "get_risk_analysis", {}),
            text_response("ok", "req-2"),
        ],
    )
    run_qwen_agent("风险？", world_service.state)

    assert len(fake.chat.completions.calls) == 2
    first_call, second_call = fake.chat.completions.calls
    # 第一次请求：带全部 tool schema 与系统提示
    assert first_call["model"] == "qwen3.8-max"
    assert [tool["function"]["name"] for tool in first_call["tools"]] == [
        definition["function"]["name"] for definition in TOOL_DEFINITIONS
    ]
    assert SYSTEM_NOTICE in first_call["messages"][0]["content"]
    # 第二次请求：assistant(tool_calls) + tool(result) 消息齐全
    second_messages = second_call["messages"]
    assistant_messages = [m for m in second_messages if m["role"] == "assistant" and m.get("tool_calls")]
    tool_messages = _tool_messages(second_messages)
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["tool_calls"][0]["id"] == "call_9"
    assert assistant_messages[0]["tool_calls"][0]["function"]["name"] == "get_risk_analysis"
    assert len(tool_messages) == 1 and tool_messages[0]["tool_call_id"] == "call_9"
    payload = json.loads(tool_messages[0]["content"])
    assert "overall_score" in payload, "tool result 必须是真实 get_risk_analysis 序列化结果"
    assert payload["overall_score"] == world_service.state.risk_state.overall_score


# ---------- 接地验收 ----------

def _ml_final(kwargs: dict) -> FakeResponse:
    result = _last_tool_json(kwargs["messages"])
    return text_response(
        f"训练模型（{result['model_version']}）预测未来10分钟风险为 {float(result['prediction']):.1f}。",
        "req-ml",
    )


def test_qwen_ml_predict_grounding(monkeypatch: pytest.MonkeyPatch):
    """“训练模型认为未来10分钟风险多少” -> 真实执行 ml_predict_risk -> 数字只能来自工具。"""
    _configure(
        monkeypatch,
        [
            tool_call_response("call_ml", "ml_predict_risk", {"horizon_minutes": 10}),
            _ml_final,
        ],
    )
    result = client.post("/api/chat", json={"message": "训练模型认为未来10分钟风险多少？"}).json()

    assert result["tools_used"] == ["ml_predict_risk"]
    assert result["model"] == "qwen3.8-max" and result["fallback"] is False
    expected = float(AgentTools(world_service.state).ml_predict_risk(10)["prediction"])
    assert f"{expected:.1f}" in result["answer"], "回答中的风险值必须来自真实 ml_predict_risk 工具结果"
    assert "predict_future" not in result["tools_used"], "禁止用规则 predict_future 冒充 ML"


def _policy_final(kwargs: dict) -> FakeResponse:
    messages = kwargs["messages"]
    tool_payloads = [json.loads(m["content"]) for m in _tool_messages(messages)]
    recommend = next(p for p in tool_payloads if "strategy" in p)
    compare = next(p for p in tool_payloads if "results" in p)
    sims = "、".join(f"{r['strategy']} {float(r['after']['risk']):.1f}" for r in compare["results"])
    probability = (recommend.get("probabilities") or {}).get(recommend["strategy"])
    return text_response(
        f"模型推荐 {recommend['strategy']}（模型概率 {float(probability):.1%}，来自 predict_proba）；"
        f"What-if 仿真验证：{sims}。",
        "req-policy",
    )


def test_qwen_policy_multi_tool_grounding(monkeypatch: pytest.MonkeyPatch):
    """“模型建议什么措施” -> ml_recommend_strategy + compare_strategies 双工具接地。"""
    _configure(
        monkeypatch,
        [
            tool_call_response("call_rec", "ml_recommend_strategy", {}),
            tool_call_response("call_cmp", "compare_strategies", {"horizon_minutes": 10}),
            _policy_final,
        ],
    )
    result = client.post("/api/chat", json={"message": "现在模型建议采取什么措施？"}).json()

    assert result["tools_used"] == ["ml_recommend_strategy", "compare_strategies"]
    assert result["tool_rounds"] == 2
    recommend = AgentTools(world_service.state).ml_recommend_strategy()
    assert recommend["strategy"] in result["answer"]
    assert "predict_proba" in result["answer"]
    assert "What-if" in result["answer"]
    # 仿真数字同样必须来自真实工具
    simulations = AgentTools(world_service.state).compare_strategies()
    for simulation in simulations:
        assert f"{simulation.after.risk:.1f}" in result["answer"]


def _cv_final(kwargs: dict) -> FakeResponse:
    summary = _last_tool_json(kwargs["messages"])
    if not summary.get("available"):
        return text_response("当前 CV 推理记录不支持检测到风险物品的结论。", "req-cv")
    detail = "、".join(f"{label} {float(conf):.0%}" for label, conf in zip(summary["labels"], summary["confidences"]))
    return text_response(
        f"最近一次 CV 推理（provider={summary['provider']}，model_invoked={summary['model_invoked']}）检测到：{detail}。",
        "req-cv",
    )


def test_qwen_cv_summary_grounding(monkeypatch: pytest.MonkeyPatch):
    """“视觉模型检测到了什么” -> get_cv_detection_summary 忠实转述，不得自造置信度。"""
    real_cv.record_last_detection_summary(
        {
            "provider": "real",
            "model_invoked": True,
            "model_version": "cv_yolo_8.4.123",
            "scene_id": "demo_high_risk",
            "detection_count": 3,
            "labels": ["person", "risk_object", "vehicle"],
            "confidences": [0.99, 0.87, 0.92],
            "crowd": None,
            "latency_ms": 12.3,
            "timestamp": "2026-08-20T00:00:00+00:00",
        }
    )
    _configure(
        monkeypatch,
        [
            tool_call_response("call_cv", "get_cv_detection_summary", {}),
            _cv_final,
        ],
    )
    result = client.post("/api/chat", json={"message": "视觉模型检测到了什么？"}).json()

    assert result["tools_used"] == ["get_cv_detection_summary"]
    assert "provider=real" in result["answer"] and "model_invoked=True" in result["answer"]
    assert "person 99%" in result["answer"] and "risk_object 87%" in result["answer"]


def test_qwen_no_risk_hallucination(monkeypatch: pytest.MonkeyPatch):
    """Reset 后无任何 CV 记录 -> 必须回答“记录不支持该结论”；真实推理后再问 -> 引用真实检测。"""
    # 阶段一：无记录，禁止幻觉
    _configure(
        monkeypatch,
        [
            tool_call_response("call_cv_1", "get_cv_detection_summary", {}),
            _cv_final,
        ],
    )
    result = client.post("/api/chat", json={"message": "当前视觉模型检测到风险物品了吗？"}).json()
    assert result["tools_used"] == ["get_cv_detection_summary"]
    assert "不支持" in result["answer"]
    assert "检测到：person" not in result["answer"]

    # 阶段二：真实 YOLO 推理 demo_high_risk（真实 RiskObjectDetected 入记录）
    detection = client.post(
        "/api/perception/cv/detect-image",
        data={"demo_scene_id": "demo_high_risk", "provider": "real"},
    ).json()
    assert detection["provider"] == "real" and detection["model_invoked"] is True
    assert "RiskObjectDetected" in [event["type"] for event in detection["events"]]
    summary = real_cv.get_last_detection_summary()
    assert "risk_object" in summary["labels"]

    # 阶段三：同一问题，回答必须来自最新真实 detection
    _configure(
        monkeypatch,
        [
            tool_call_response("call_cv_2", "get_cv_detection_summary", {}),
            _cv_final,
        ],
    )
    result = client.post("/api/chat", json={"message": "当前视觉模型检测到风险物品了吗？"}).json()
    confidence = summary["confidences"][summary["labels"].index("risk_object")]
    assert f"risk_object {confidence:.0%}" in result["answer"]


# ---------- Vision ----------

def test_qwen_vision_structured_output(monkeypatch: pytest.MonkeyPatch):
    """Vision：合成图真实（fake 网络）发给 qwen3.8-max，结构化语义输出，绝不冒充 YOLO。"""
    vision_json = json.dumps(
        {
            "estimated_people": 3,
            "vehicle_visible": True,
            "possible_risk_object": True,
            "crowd_semantics": "校门口三人驻留",
            "summary": "合成监控画面中三人聚集，旁边有一辆车与一件疑似遗留物品。",
            "synthetic_visual_data": False,
        },
        ensure_ascii=False,
    )
    provider, fake = _configure(monkeypatch, [text_response(vision_json, "req-vision")])
    response = client.post("/api/llm/vision/analyze", json={"demo_scene_id": "demo_high_risk"}).json()

    assert response["fallback"] is False
    assert response["source"] == "Qwen3.8-Max Vision"
    assert response["model"] == "qwen3.8-max"
    assert "不是 YOLO 检测" in response["note"]
    structured = response["structured"]
    assert structured["estimated_people"] == 3
    assert structured["vehicle_visible"] is True
    assert structured["possible_risk_object"] is True
    assert structured["crowd_semantics"] == "校门口三人驻留"
    assert structured["synthetic_visual_data"] is True, "输入是合成图，恒为 true"

    # 请求侧：真实 demo 图 base64 + qwen3.8-max
    call = fake.chat.completions.calls[0]
    assert call["model"] == "qwen3.8-max"
    content = call["messages"][0]["content"]
    image_part = next(part for part in content if part["type"] == "image_url")
    data_url = image_part["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    payload = data_url.split(",", 1)[1]
    assert len(payload) > 1000, "发送的必须是真实合成 demo 图"


# ---------- Fallback ----------

@pytest.mark.parametrize("failure", ["timeout", "rate_limit", "server"])
def test_qwen_api_failure_fallback(monkeypatch: pytest.MonkeyPatch, failure: str):
    """API 失败（timeout/429/5xx）不崩溃：确定性 grounded 回退 + 明确 Offline 标注。"""
    errors = {
        "timeout": TimeoutError("APITimeoutError: request timed out"),
        "rate_limit": RuntimeError("429 Too Many Requests rate limit exceeded"),
        "server": RuntimeError("500 Internal Server Error"),
    }
    _configure(monkeypatch, [errors[failure]])
    result = client.post("/api/chat", json={"message": "训练模型认为未来10分钟风险多少？"}).json()

    assert result["fallback"] is True
    assert result["provider"] == "deterministic_fallback"
    assert result["request_id"] is None, "禁止伪造 Qwen request_id"
    assert "Qwen3.8-Max Offline" in result["fallback_reason"]
    # 回退回答仍接地：确定性 agent 真实调用了 ml_predict_risk
    assert result["tools_used"] == ["ml_predict_risk"]
    expected = float(AgentTools(world_service.state).ml_predict_risk(10)["prediction"])
    assert f"{expected:.1f}" in result["answer"]


def test_qwen_api_key_missing_fallback(monkeypatch: pytest.MonkeyPatch):
    """Key 缺失：同样走确定性回退，且绝不显示 Connected。"""
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    reset_qwen_provider()
    result = client.post("/api/chat", json={"message": "现在风险如何？"}).json()
    assert result["fallback"] is True
    assert "DASHSCOPE_API_KEY" in result["fallback_reason"]
    status = client.get("/api/llm/status").json()
    assert status["connected"] is False and status["fallback"] is True


# ---------- 循环上限 ----------

def test_qwen_tool_loop_limit(monkeypatch: pytest.MonkeyPatch):
    """模型连续要工具时必须在 MAX_TOOL_ROUNDS 停止，防死循环。"""
    # 前 MAX_TOOL_ROUNDS 个响应全是工具调用；其后是收敛回答；
    # 再往后的额外工具调用永远不应被消费（证明循环确实被截断）
    script: list = [tool_call_response(f"call_{i}", "get_risk_analysis", {}) for i in range(MAX_TOOL_ROUNDS)]
    script.append(text_response("基于已获得的工具结果回答。", "req-limit"))
    script.extend(tool_call_response(f"call_extra_{i}", "get_risk_analysis", {}) for i in range(3))
    provider, fake = _configure(monkeypatch, script)

    result = run_qwen_agent("风险？", world_service.state)

    assert result["tool_rounds"] == MAX_TOOL_ROUNDS
    assert result["tools_used"] == ["get_risk_analysis"] * MAX_TOOL_ROUNDS
    assert result["answer"] == "基于已获得的工具结果回答。"
    # 轮次耗尽后的收敛调用不再携带 tools，且额外脚本项未被消费
    assert len(fake.chat.completions.calls) == MAX_TOOL_ROUNDS + 1
    assert not fake.chat.completions.calls[-1].get("tools"), "最后一次收敛调用必须无 tools"
    assert len(fake.chat.completions.script) == 3, "循环必须在 MAX_TOOL_ROUNDS 截断"
