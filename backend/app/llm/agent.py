from ..ml.episodes import DEFAULT_INTERVENTION_COST_WEIGHT
from ..simulation.strategies import Strategy
from ..world.state import WorldState
from .tools import AgentTools

STRATEGY_LABELS = {
    Strategy.NONE.value: "不干预",
    Strategy.WARN.value: "发送预警",
    Strategy.GUIDE_LEAVE.value: "引导离开",
    Strategy.INTERVENE.value: "现场处置",
}

ML_MARKERS = ("训练模型", "模型", "机器学习")
RECOMMEND_MARKERS = ("推荐", "建议", "措施", "策略")
PREDICT_MARKERS = ("预测", "风险", "未来", "分钟", "多少")
CV_MARKERS = ("视觉", "检测到", "摄像头", "画面", "目标检测", "cv")


def _predict_horizon(question: str) -> int:
    if "30" in question:
        return 30
    if "5" in question:
        return 5
    return 10


def _is_ml_question(question: str) -> bool:
    normalized = question.lower()
    return any(marker in question for marker in ML_MARKERS) or "ml" in normalized or "machine learning" in normalized


def _ml_recommendation_answer(tools: AgentTools) -> dict[str, object]:
    """模型推荐路径：先 ml_recommend_strategy，再用 What-if 仿真独立验证。"""
    recommendation = tools.ml_recommend_strategy()
    simulations = tools.compare_strategies()
    strategy = str(recommendation["strategy"])
    answer_parts: list[str] = []
    if recommendation.get("fallback"):
        answer_parts.append(
            f"ML 模型不可用（{recommendation.get('note')}），已按 What-if 仿真 utility 推荐回退策略 {strategy}。"
        )
    else:
        probabilities = recommendation.get("probabilities") or {}
        probability_line = "、".join(
            f"{STRATEGY_LABELS.get(label, label)} {float(probability):.1%}" for label, probability in probabilities.items()
        )
        confidence = float(recommendation.get("confidence") or 0.0)
        answer_parts.append(
            f"干预策略模型（{recommendation['model_version']}）推荐 {STRATEGY_LABELS.get(strategy, strategy)}，"
            f"模型概率/置信度 {confidence:.1%}（四策略概率：{probability_line}）。"
        )
        features = recommendation.get("input_features") or {}
        feature_line = "、".join(
            f"{name}={float(features[name]):g}"
            for name in ("current_risk", "crowd_detected", "crowd_gathered", "risk_object_detected")
            if name in features
        )
        answer_parts.append(f"该推荐基于当前 World State 特征（{feature_line}）。")
    simulation_line = "、".join(
        f"{STRATEGY_LABELS.get(result.strategy.value, result.strategy.value)} {result.after.risk:.1f}"
        for result in simulations
    )
    answer_parts.append(f"随后 What-if 仿真验证（10 分钟后风险）：{simulation_line}。")
    if not recommendation.get("fallback"):
        best_simulation = max(
            simulations,
            key=lambda result: (
                result.before.risk
                - result.after.risk
                - DEFAULT_INTERVENTION_COST_WEIGHT * result.action_cost
            ),
        )
        if best_simulation.strategy.value == strategy:
            answer_parts.append(f"因此当前模型推荐为{STRATEGY_LABELS.get(strategy, strategy)}，仿真结果也显示其能显著降低风险。")
        else:
            answer_parts.append(
                f"仿真效用最优策略为 {STRATEGY_LABELS.get(best_simulation.strategy.value, best_simulation.strategy.value)}，"
                f"与模型推荐不一致，建议以仿真结果为准。"
            )
    answer_parts.append("以上基于 100% Synthetic Training 与 Simulation，仅用于模型验证，不代表现实世界最佳措施概率。")
    return {
        "answer": " ".join(answer_parts),
        "tools_used": ["ml_recommend_strategy", "compare_strategies"],
        "synthetic": True,
        "ml_recommendation": recommendation,
    }


def _ml_risk_answer(tools: AgentTools, question: str) -> dict[str, object]:
    """ML 风险预测路径：调用 ml_predict_risk，绝不把规则输出说成 ML 输出。"""
    horizon = _predict_horizon(question)
    prediction = tools.ml_predict_risk(horizon)
    if prediction.get("fallback"):
        answer = (
            f"ML 模型不可用（{prediction.get('note')}），以下为规则世界模型回退预测："
            f"未来 {horizon} 分钟风险预计 {float(prediction['prediction']):.1f}（模型 {prediction['model']}，透明规则）。"
        )
    else:
        mae_line = f"，Test MAE {prediction['test_mae']}" if prediction.get("test_mae") is not None else ""
        answer = (
            f"ML Prediction：训练模型（{prediction.get('model_type', prediction['model'])} "
            f"{prediction['model_version']}）预测未来 {horizon} 分钟风险为 "
            f"{float(prediction['prediction']):.1f}{mae_line}。该预测基于当前 World State 的 16 维特征"
            f"（current_risk={float(prediction['input_features']['current_risk']):g} 等）。"
            "以上为 Synthetic Training 模型输出，仅用于模型验证。"
        )
    return {"answer": answer, "tools_used": ["ml_predict_risk"], "synthetic": True, "ml_prediction": prediction}


def _cv_detection_answer(tools: AgentTools) -> dict[str, object]:
    """视觉模型检测路径：读取最近一次 CV 推理摘要，绝不把 MockCV 说成 Trained CV。"""
    summary = tools.get_cv_detection_summary()
    if not summary.get("available"):
        return {
            "answer": f"{summary['note']} 该回答基于 get_cv_detection_summary 工具，尚无 CV 推理记录。",
            "tools_used": ["get_cv_detection_summary"],
            "synthetic": True,
            "cv_summary": summary,
        }
    labels = list(summary.get("labels") or [])
    confidences = list(summary.get("confidences") or [])
    detail_line = "、".join(
        f"{label} {float(confidence):.0%}" for label, confidence in zip(labels, confidences)
    ) or "无任何 Detection"
    if summary.get("provider") == "real" and summary.get("model_invoked"):
        provider_line = (
            f"Trained CV（{summary.get('model_version') or 'real model'}）在最近一次真实推理"
            f"（YOLO.predict，场景 {summary.get('scene_id')}，耗时 {summary.get('latency_ms')}ms）中检测到 "
            f"{summary.get('detection_count', 0)} 个目标：{detail_line}。"
        )
    else:
        provider_line = (
            f"最近一次 CV 结果来自 Mock Fallback（模型未真实调用，model_invoked=false，"
            f"原因：{summary.get('fallback_reason') or '模型不可用'}），并非 Trained CV 输出；"
            f"该次共 {summary.get('detection_count', 0)} 个 Detection：{detail_line}。"
        )
    crowd = summary.get("crowd")
    crowd_line = (
        f"感知层聚合出多人聚集（{crowd.get('person_count')} 人，成对中心距 {crowd.get('max_pair_distance')}）。"
        if crowd
        else "未触发感知层聚集聚合。"
    )
    answer = (
        f"{provider_line}{crowd_line}"
        "以上均来自 Synthetic Visual Data 的 CV 推理记录，仅用于模型验证。"
    )
    return {"answer": answer, "tools_used": ["get_cv_detection_summary"], "synthetic": True, "cv_summary": summary}


def explain_question(question: str, state: WorldState) -> dict[str, object]:
    tools = AgentTools(state)
    normalized = question.lower()
    if any(marker in normalized for marker in CV_MARKERS) or any(marker in question for marker in CV_MARKERS[:5]):
        return _cv_detection_answer(tools)
    if _is_ml_question(question) and any(marker in question for marker in RECOMMEND_MARKERS):
        return _ml_recommendation_answer(tools)
    if _is_ml_question(question) and any(marker in question for marker in PREDICT_MARKERS):
        return _ml_risk_answer(tools, question)
    if "预警" in question or "warn" in normalized:
        result = tools.run_simulation(Strategy.WARN)
        answer = f"发送预警后，规则世界模型模拟风险由 {result.before.risk:.1f} 降至 {result.after.risk:.1f}，离开概率约 {result.leave_probability:.0%}。"
        used_tools = ["run_simulation"]
    elif "未来" in question or "预测" in question or "分钟" in question or "predict" in normalized:
        horizon = _predict_horizon(question)
        prediction = tools.predict_future(horizon)
        answer = (
            f"规则世界模型（{prediction.model}）推演：未来 {prediction.horizon_minutes} 分钟风险预计 {prediction.risk_score:.1f}"
            f"（趋势 {prediction.risk_trend}），聚集概率 {prediction.gather_probability:.0%}，"
            f"进入敏感区概率 {prediction.zone_entry_probability:.0%}，预计活跃主体 {prediction.predicted_agents} 个。"
            "该结果来自透明规则 World Behavior Model，非 ML 模型。"
        )
        used_tools = ["predict_future"]
    elif "策略" in question or "比较" in question:
        results = tools.compare_strategies()
        best = min(results, key=lambda item: item.after.risk)
        answer = f"四种策略的 What-if 仿真对比中，{best.strategy.value} 的模拟剩余风险最低，为 {best.after.risk:.1f}，行动成本 {best.action_cost}。该结果来自规则仿真引擎，非 ML 模型。"
        used_tools = ["compare_strategies"]
    else:
        risk = tools.get_risk_analysis()
        events = "、".join(event.type.value for event in tools.get_active_events()[-3:]) or "无活跃事件"
        reasons = "；".join(risk.reasons) or "当前没有显著风险因子"
        answer = f"当前模拟风险为 {risk.overall_score:.1f}（{risk.level}）。活跃事件：{events}。依据：{reasons}。"
        used_tools = ["get_risk_analysis", "get_active_events"]
    return {"answer": answer + " 以上均为 Synthetic Data 行为模型结果，仅用于模型验证。", "tools_used": used_tools, "synthetic": True}
