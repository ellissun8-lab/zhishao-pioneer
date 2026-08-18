from ..simulation.strategies import Strategy
from ..world.state import WorldState
from .tools import AgentTools


def _predict_horizon(question: str) -> int:
    if "30" in question:
        return 30
    if "5" in question:
        return 5
    return 10


def explain_question(question: str, state: WorldState) -> dict[str, object]:
    tools = AgentTools(state)
    normalized = question.lower()
    if "预警" in question or "warn" in normalized:
        result = tools.run_simulation(Strategy.WARN)
        answer = f"发送预警后，模型模拟风险由 {result.before.risk:.1f} 降至 {result.after.risk:.1f}，离开概率约 {result.leave_probability:.0%}。"
        used_tools = ["run_simulation"]
    elif "未来" in question or "预测" in question or "分钟" in question or "predict" in normalized:
        horizon = _predict_horizon(question)
        prediction = tools.predict_future(horizon)
        answer = (
            f"未来 {prediction.horizon_minutes} 分钟模拟推演：风险预计 {prediction.risk_score:.1f}（趋势 {prediction.risk_trend}），"
            f"聚集概率 {prediction.gather_probability:.0%}，进入敏感区概率 {prediction.zone_entry_probability:.0%}，"
            f"预计活跃主体 {prediction.predicted_agents} 个（模型 {prediction.model}）。"
        )
        used_tools = ["predict_future"]
    elif "策略" in question or "比较" in question:
        results = tools.compare_strategies()
        best = min(results, key=lambda item: item.after.risk)
        answer = f"四种策略中，{best.strategy.value} 的模拟剩余风险最低，为 {best.after.risk:.1f}，行动成本 {best.action_cost}。"
        used_tools = ["compare_strategies"]
    else:
        risk = tools.get_risk_analysis()
        events = "、".join(event.type.value for event in tools.get_active_events()[-3:]) or "无活跃事件"
        reasons = "；".join(risk.reasons) or "当前没有显著风险因子"
        answer = f"当前模拟风险为 {risk.overall_score:.1f}（{risk.level}）。活跃事件：{events}。依据：{reasons}。"
        used_tools = ["get_risk_analysis", "get_active_events"]
    return {"answer": answer + " 以上均为 Synthetic Data 行为模型结果，仅用于模型验证。", "tools_used": used_tools, "synthetic": True}
