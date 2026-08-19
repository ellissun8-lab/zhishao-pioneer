from ..behavior.prediction import predict_world_state
from ..ml import registry
from ..ml.features import extract_features
from ..simulation.engine import SimulationEngine
from ..simulation.strategies import Strategy
from ..world.state import WorldState


class AgentTools:
    def __init__(self, state: WorldState) -> None:
        self.state = state

    def get_world_state(self) -> WorldState:
        return self.state

    def get_agent_state(self, agent_id: str):
        return self.state.agents.get(agent_id)

    def get_active_events(self):
        return self.state.active_events

    def get_risk_analysis(self):
        return self.state.risk_state

    def predict_future(self, horizon_minutes: int = 10):
        return predict_world_state(self.state, horizon_minutes)

    def run_simulation(self, strategy: Strategy, horizon_minutes: int = 10):
        return SimulationEngine().run(self.state, strategy, horizon_minutes)

    def compare_strategies(self, horizon_minutes: int = 10):
        return SimulationEngine().compare(self.state, horizon_minutes)

    def ml_predict_risk(self, horizon_minutes: int = 10) -> dict[str, object]:
        """World State -> features -> trained model；模型缺失时透明规则回退。"""
        features = extract_features(self.state)
        if not registry.risk_model_available():
            if horizon_minutes not in {5, 10, 30}:
                raise ValueError("horizon_minutes must be one of 5, 10, 30")
            prediction = predict_world_state(self.state, horizon_minutes)
            return {
                "model": prediction.model,
                "model_version": None,
                "horizon_minutes": horizon_minutes,
                "prediction": prediction.risk_score,
                "input_features": features,
                "synthetic_training": False,
                "fallback": True,
                "note": registry.FALLBACK_NOTE,
            }
        return registry.predict_risk(features, horizon_minutes)

    def ml_recommend_strategy(self) -> dict[str, object]:
        """World State -> features -> trained policy model；缺失时 compare_strategies 回退。"""
        features = extract_features(self.state)
        if not registry.policy_model_available():
            results = self.compare_strategies()
            best = min(results, key=lambda result: result.after.risk)
            return {
                "model": "rule_compare",
                "model_version": None,
                "strategy": best.strategy.value,
                "probabilities": None,
                "confidence": None,
                "input_features": features,
                "synthetic_training": False,
                "fallback": True,
                "note": registry.FALLBACK_NOTE,
            }
        return registry.recommend_strategy(features)
