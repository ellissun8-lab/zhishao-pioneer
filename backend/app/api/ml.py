"""ML 训练模型 API：状态展示 + 运行态风险预测 + 模型推荐（必须经 What-if Simulation 验证）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..behavior.prediction import predict_world_state
from ..ml import registry
from ..ml.episodes import DEFAULT_INTERVENTION_COST_WEIGHT
from ..ml.features import extract_features
from ..service import world_service
from ..simulation.engine import SimulationEngine

router = APIRouter(prefix="/ml", tags=["ml"])


class PredictRiskRequest(BaseModel):
    horizon_minutes: int = Field(default=10, ge=1, le=60)
    use_current_world_state: bool = True


@router.get("/status")
def ml_status() -> dict[str, object]:
    """训练模型状态与 test 指标（读取 models/metrics.json，前端禁止写死数字）。"""
    return registry.status()


@router.post("/predict-risk")
def ml_predict_risk(request: PredictRiskRequest) -> dict[str, object]:
    """运行态 ML 风险预测：Current World State -> features.py -> risk_forecast.joblib。

    这是独立于规则 World Behavior Model 的第二条预测路径；
    模型缺失时透明回退规则预测（fallback=true，fallback_source=rule_world_behavior_model），
    绝不把规则输出伪装成 ML 输出。
    """
    state = world_service.state
    features = extract_features(state)
    horizon = request.horizon_minutes
    if horizon not in {5, 10, 30}:
        raise HTTPException(status_code=400, detail="horizon_minutes must be one of 5, 10, 30")
    if registry.risk_model_available():
        result = registry.predict_risk(features, horizon)
        return {**result, "fallback": False}
    prediction = predict_world_state(state, horizon)
    return {
        "model": prediction.model,
        "model_type": "TransparentRuleWorldBehaviorModel",
        "model_version": None,
        "horizon_minutes": horizon,
        "prediction": prediction.risk_score,
        "input_features": features,
        "synthetic_training": False,
        "fallback": True,
        "fallback_source": "rule_world_behavior_model",
        "test_mae": None,
        "note": registry.FALLBACK_NOTE,
    }


@router.get("/recommend")
def ml_recommend() -> dict[str, object]:
    """对当前 World State 给出模型推荐，并用 What-if Simulation 验证后解释。

    推荐不能直接成为事实：模型推荐 -> run_simulation 验证 -> 解释。
    """
    state = world_service.state
    features = extract_features(state)
    recommendation = None
    fallback = False
    if registry.policy_model_available():
        recommendation = registry.recommend_strategy(features)
    else:
        fallback = True

    simulations = []
    best_by_simulation = None
    for result in SimulationEngine().compare(state):
        utility = round((result.before.risk - result.after.risk) - DEFAULT_INTERVENTION_COST_WEIGHT * result.action_cost, 2)
        simulations.append(
            {
                "strategy": result.strategy.value,
                "before_risk": result.before.risk,
                "after_risk": result.after.risk,
                "action_cost": result.action_cost,
                "utility": utility,
                "changes": result.changes,
            }
        )
        if best_by_simulation is None or utility > best_by_simulation["utility"]:
            best_by_simulation = simulations[-1]

    if fallback:
        recommendation = {
            "model": "rule_compare",
            "model_version": None,
            "strategy": best_by_simulation["strategy"],
            "probabilities": None,
            "confidence": None,
            "input_features": features,
            "synthetic_training": False,
            "note": registry.FALLBACK_NOTE,
        }

    verify_line = "；".join(f"{item['strategy']} -> {item['after_risk']}" for item in simulations)
    explanation = (
        f"模型推荐 {recommendation['strategy']}"
        + (f"（置信度 {float(recommendation['confidence']):.0%}）" if recommendation.get("confidence") else "（规则回退推荐）")
        + f"。What-if 仿真验证（10min 后风险）：{verify_line}；仿真 utility 最大策略为 {best_by_simulation['strategy']}。"
        + ("推荐策略已由仿真独立验证。" if recommendation["strategy"] == best_by_simulation["strategy"] else "模型推荐与仿真最优策略不一致，建议以仿真结果为准。")
        + " 以上均为 Synthetic Data 训练与推演结果，仅用于模型验证。"
    )
    return {
        "recommendation": recommendation,
        "fallback": fallback,
        "simulation": simulations,
        "best_by_simulation": best_by_simulation["strategy"],
        "explanation": explanation,
        "synthetic": True,
    }
