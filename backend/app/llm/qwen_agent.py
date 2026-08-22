"""Qwen3.8-Max 真实 Function Calling Loop。

流程：user message + tools -> qwen3.8-max -> 读取 tool_calls -> 应用层执行现有 Tool
-> tool result 作为 tool message 回传 -> 再次请求 -> grounded final answer。
最多 MAX_TOOL_ROUNDS 轮，防止死循环。所有事实来自 Tool；Qwen 绝不自己制造
risk score / prediction / event / person count / strategy result / CV confidence。
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..world.state import WorldState
from .prompts import SYSTEM_NOTICE
from .providers.qwen import QwenAPIError, get_qwen_provider
from .qwen_tools import TOOL_DEFINITIONS, execute_tool, serialize_tool_result
from .tools import AgentTools

MAX_TOOL_ROUNDS = 5
LOOP_LIMIT_NOTICE = "已达到工具调用轮次上限，请立即基于已获得的工具结果给出最终回答，不要再请求工具。"

SYSTEM_PROMPT = f"""你是“智哨先锋”城市行为智能推演 Agent（推演哨兵）。
{SYSTEM_NOTICE}

回答纪律（必须严格遵守）：
1. 所有事实必须来自工具返回结果：risk score、预测值、事件、人数、策略结果、CV 置信度，一个数字都不能自己编造。
2. 用户问“训练模型认为风险多少”必须调用 ml_predict_risk（这是 ML 模型，不要用 predict_future 规则模型冒充）。
3. 用户问“模型建议什么措施”必须调用 ml_recommend_strategy，并可再调用 compare_strategies 做 What-if 验证；回答要区分“模型概率（predict_proba）”与“What-if 仿真结果”，不得把概率说成现实世界成功率。
4. 用户问视觉检测相关问题必须调用 get_cv_detection_summary；不得自己数人、不得自己生成 YOLO 置信度；provider/model_invoked 要如实转述。
5. 工具结果里没有的结论就不要下；没有记录时明确说“当前记录不支持该结论”。
6. 用中文回答，简洁但信息完整，引用具体数值时保留一位小数或百分比。"""


def _verified_grounded_answer(answer: str, tool_results: dict[str, Any]) -> str:
    """对数值敏感回答使用本轮 tool result 做最终格式化，杜绝模型二次演绎数字。"""
    cv_result = tool_results.get("get_cv_detection_summary")
    if isinstance(cv_result, dict):
        if not cv_result.get("available"):
            return "当前 CV 工具记录不可用，记录不支持任何视觉检测结论。"
        labels = cv_result.get("labels") or []
        confidences = cv_result.get("confidences") or []
        detections = "、".join(
            f"{label} {float(confidence):.0%}"
            for label, confidence in zip(labels, confidences, strict=False)
        ) or "无 Detection"
        return (
            f"CV 工具事实：provider={cv_result.get('provider')}，"
            f"model_invoked={str(bool(cv_result.get('model_invoked'))).lower()}，"
            f"detection_count={cv_result.get('detection_count')}，detections={detections}。"
            "以上仅来自 get_cv_detection_summary 的 Synthetic Visual Data 记录。"
        )

    prediction = tool_results.get("ml_predict_risk")
    if isinstance(prediction, dict):
        horizon = int(prediction.get("horizon_minutes") or 10)
        model = prediction.get("model_type") or prediction.get("model")
        fallback = bool(prediction.get("fallback"))
        source = "透明规则回退" if fallback else "训练模型"
        mae = prediction.get("test_mae")
        mae_text = f"，Test MAE={float(mae):.4f}" if mae is not None else ""
        return (
            f"{source}（{model}）预测未来 {horizon} 分钟风险为 "
            f"{float(prediction['prediction']):.1f}{mae_text}。"
            "该数字来自 ml_predict_risk 工具结果，基于 Synthetic Data，仅用于模型验证。"
        )

    recommendation = tool_results.get("ml_recommend_strategy")
    comparison = tool_results.get("compare_strategies")
    if isinstance(recommendation, dict) and isinstance(comparison, dict):
        strategy = str(recommendation.get("strategy"))
        probabilities = recommendation.get("probabilities") or {}
        probability = probabilities.get(strategy)
        probability_text = f"{float(probability):.1%}" if probability is not None else "不可用（规则回退）"
        simulations = comparison.get("results") or []
        simulation_text = "、".join(
            f"{item.get('strategy')}={float((item.get('after') or {}).get('risk')):.1f}"
            for item in simulations
        )
        return (
            f"Model Recommendation：{strategy}，predict_proba 模型概率={probability_text}；"
            f"What-if Verification（10 分钟后风险）：{simulation_text}。"
            "模型概率不代表现实处置成功率；以上数字仅来自本轮工具结果与 Synthetic Data。"
        )

    return answer


class QwenUnavailableError(RuntimeError):
    """Qwen3.8-Max 不可用（Key 缺失 / 模型名非法 / API 失败），调用方走确定性回退。"""


def run_qwen_agent(question: str, state: WorldState) -> dict[str, Any]:
    """真实 Function Calling 循环。返回 answer + 完整 trace（不含任何敏感信息）。"""
    provider = get_qwen_provider()
    if not provider.configured:
        raise QwenUnavailableError(provider.unconfigured_reason() or "Qwen provider not configured")

    agent_tools = AgentTools(state)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tools_used: list[str] = []
    tool_rounds = 0
    request_id: str | None = None
    answer = ""
    last_tool_results: dict[str, Any] = {}
    started = time.perf_counter()

    try:
        while tool_rounds < MAX_TOOL_ROUNDS:
            response = provider.chat_with_tools(messages, tools=TOOL_DEFINITIONS)
            request_id = response.get("request_id") or request_id
            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                answer = response.get("content") or ""
                if not answer.strip():
                    raise QwenAPIError("qwen3.8-max 返回空回答", kind="api_error")
                break
            tool_rounds += 1
            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("content") or None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": call["arguments"]},
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                result = execute_tool(agent_tools, call["name"], call["arguments"])
                last_tool_results[call["name"]] = result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": serialize_tool_result(result),
                    }
                )
                tools_used.append(call["name"])
        else:
            # 轮次耗尽：最后一次不带 tools 强制收敛出最终回答
            messages.append({"role": "user", "content": LOOP_LIMIT_NOTICE})
            response = provider.chat_with_tools(messages, tools=None)
            request_id = response.get("request_id") or request_id
            answer = response.get("content") or "（已达工具调用上限，且模型未给出最终回答）"
    except QwenAPIError as error:
        raise QwenUnavailableError(error.reason) from error

    answer = _verified_grounded_answer(answer, last_tool_results)

    return {
        "answer": answer,
        "provider": "Alibaba Cloud Model Studio",
        "model": provider.model,
        "tools_used": tools_used,
        "tool_rounds": tool_rounds,
        "request_id": request_id,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "fallback": False,
        "synthetic": True,
    }
