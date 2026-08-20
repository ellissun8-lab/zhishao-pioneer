"""Qwen3.8-Max Tool Adapter：JSON Schema + 参数校验 + 调用现有 AgentTools + 序列化。

绝不重写业务函数——所有事实（risk score / prediction / event / person count /
strategy result / CV confidence）都来自既有 AgentTools 调用结果。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

from ..simulation.strategies import Strategy
from .tools import AgentTools

HORIZON_VALUES = (5, 10, 30)
STRATEGY_VALUES = ("none", "warn", "guide_leave", "intervene")

# 每个工具的 OpenAI function schema（只描述参数，不复制业务逻辑）
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_world_state",
            "description": "获取当前模拟世界状态摘要（agents、zones、活跃事件、风险状态）。数据 100% Synthetic。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_state",
            "description": "按 agent_id 获取单个模拟主体的状态（位置、行为、风险分）。",
            "parameters": {
                "type": "object",
                "properties": {"agent_id": {"type": "string", "description": "主体 id，例如 agent_A"}},
                "required": ["agent_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_events",
            "description": "获取当前 Event Bus 活跃事件列表（最近 30 条，含 type/subject/confidence/source）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_analysis",
            "description": "获取当前风险状态（overall_score、level、reasons、factors）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "predict_future",
            "description": "透明规则世界模型（非 ML）预测未来风险走势。",
            "parameters": {
                "type": "object",
                "properties": {
                    "horizon_minutes": {"type": "integer", "enum": list(HORIZON_VALUES), "default": 10}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ml_predict_risk",
            "description": "训练风险预测模型（HistGradientBoostingRegressor，120k synthetic episodes）预测未来风险分。用户问“训练模型认为风险多少”时必须调用本工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "horizon_minutes": {"type": "integer", "enum": list(HORIZON_VALUES), "default": 10}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ml_recommend_strategy",
            "description": "训练策略模型（HistGradientBoostingClassifier）给出当前干预策略推荐与四策略概率（predict_proba）。用户问“模型建议什么措施”时必须调用本工具。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_simulation",
            "description": "What-if 仿真：对指定策略推演干预前后的风险变化（规则仿真引擎）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "enum": list(STRATEGY_VALUES)},
                    "horizon_minutes": {"type": "integer", "enum": list(HORIZON_VALUES), "default": 10},
                },
                "required": ["strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_strategies",
            "description": "What-if 仿真：对比四种干预策略的风险变化与行动成本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "horizon_minutes": {"type": "integer", "enum": list(HORIZON_VALUES), "default": 10}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cv_detection_summary",
            "description": "获取最近一次 CV 推理摘要（provider/model_invoked/labels/confidences/crowd）。用户问视觉检测相关问题时必须调用本工具；不得自行估计人数或置信度。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _world_state_summary(state: Any) -> dict[str, Any]:
    agents = {
        agent_id: {
            "type": agent.type,
            "behavior_state": agent.behavior_state,
            "risk_score": agent.risk_score,
            "risk_level": agent.risk_level,
            "position": {"lng": agent.position.lng, "lat": agent.position.lat},
        }
        for agent_id, agent in list(state.agents.items())[:60]
    }
    return {
        "timestamp": state.timestamp.isoformat(),
        "agent_count": len(state.agents),
        "agents": agents,
        "zone_ids": sorted(state.zones.keys()),
        "active_event_count": len(state.active_events),
        "recent_events": [_dump(event) for event in state.active_events[-20:]],
        "risk_state": _dump(state.risk_state),
        "synthetic": True,
    }


# 每个工具：参数校验 + 调用现有 AgentTools 方法 + 序列化
# (校验器, 执行器)；校验器返回 (error, args)
_TOOL_HANDLERS: dict[str, Callable[[AgentTools, dict[str, Any]], Any]] = {
    "get_world_state": lambda tools, args: _world_state_summary(tools.state),
    "get_agent_state": lambda tools, args: (
        _dump(tools.get_agent_state(args["agent_id"]))
        if tools.get_agent_state(args["agent_id"]) is not None
        else {"error": f"unknown agent_id: {args['agent_id']}", "known_ids": list(tools.state.agents.keys())[:10]}
    ),
    "get_active_events": lambda tools, args: {
        "count": len(tools.get_active_events()),
        "events": [_dump(event) for event in tools.get_active_events()[-30:]],
    },
    "get_risk_analysis": lambda tools, args: _dump(tools.get_risk_analysis()),
    "predict_future": lambda tools, args: _dump(tools.predict_future(args.get("horizon_minutes", 10))),
    "ml_predict_risk": lambda tools, args: tools.ml_predict_risk(args.get("horizon_minutes", 10)),
    "ml_recommend_strategy": lambda tools, args: tools.ml_recommend_strategy(),
    "run_simulation": lambda tools, args: _dump(
        tools.run_simulation(Strategy(args["strategy"]), args.get("horizon_minutes", 10))
    ),
    "compare_strategies": lambda tools, args: {
        "results": [_dump(result) for result in tools.compare_strategies(args.get("horizon_minutes", 10))]
    },
    "get_cv_detection_summary": lambda tools, args: tools.get_cv_detection_summary(),
}


def _validate_arguments(name: str, arguments: dict[str, Any]) -> str | None:
    if name not in _TOOL_HANDLERS:
        return f"unknown tool: {name}"
    if name == "get_agent_state":
        agent_id = arguments.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id.strip():
            return "agent_id must be a non-empty string"
    if name == "run_simulation":
        strategy = arguments.get("strategy")
        if strategy not in STRATEGY_VALUES:
            return f"strategy must be one of {STRATEGY_VALUES}"
    for field in ("horizon_minutes",):
        if field in arguments and arguments[field] not in HORIZON_VALUES:
            return f"{field} must be one of {HORIZON_VALUES}"
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _dump(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def execute_tool(agent_tools: AgentTools, name: str, arguments_json: str | dict[str, Any]) -> dict[str, Any]:
    """校验 + 调用现有 Tool + JSON 安全序列化。出错时返回 {'error': ...} 回给模型纠正。"""
    try:
        arguments: dict[str, Any] = (
            json.loads(arguments_json) if isinstance(arguments_json, str) else dict(arguments_json or {})
        )
    except (json.JSONDecodeError, TypeError) as error:
        return {"error": f"invalid tool arguments JSON: {error}"}
    if not isinstance(arguments, dict):
        return {"error": "tool arguments must be a JSON object"}
    validation_error = _validate_arguments(name, arguments)
    if validation_error:
        return {"error": validation_error}
    handler = _TOOL_HANDLERS[name]
    try:
        return _json_safe(handler(agent_tools, arguments))  # type: ignore[operator]
    except Exception as error:  # noqa: BLE001 - 工具异常回传模型，不让循环崩溃
        return {"error": f"tool execution failed: {type(error).__name__}: {error}"}


def serialize_tool_result(result: Any) -> str:
    return json.dumps(_json_safe(result), ensure_ascii=False, default=str)
