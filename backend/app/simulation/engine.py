from pydantic import BaseModel

from ..behavior.prediction import Prediction, predict_world_state
from ..ontology.models import BehaviorState, Event, EventType
from ..world.state import WorldState
from ..world.updater import WorldStateUpdater
from .strategies import STRATEGY_EFFECTS, Strategy


class RiskSnapshot(BaseModel):
    risk: float
    crowd_size: int


class SimulationResult(BaseModel):
    strategy: Strategy
    horizon_minutes: int
    before: RiskSnapshot
    after: RiskSnapshot
    changes: list[str]
    action_cost: int
    leave_probability: float
    prediction: Prediction
    synthetic: bool = True


class SimulationEngine:
    def run(self, source: WorldState, strategy: Strategy, horizon_minutes: int = 10) -> SimulationResult:
        state = source.clone()
        effect = STRATEGY_EFFECTS[strategy]
        before_risk = state.risk_state.overall_score
        crowd_size = 3 if any(event.type == EventType.CROWD_GATHERED for event in state.active_events) else 1
        changes: list[str] = []

        if strategy == Strategy.INTERVENE:
            event = Event(type=EventType.INTERVENTION_APPLIED, source="what_if", metadata={"strategy": strategy.value})
            WorldStateUpdater().apply(state, event)
            for agent in state.agents.values():
                agent.behavior_state = BehaviorState.RESOLVED
            changes.append("高风险模拟事件已标记为 Resolved")
        elif strategy in {Strategy.WARN, Strategy.GUIDE_LEAVE}:
            changes.append("预计 1 名模拟主体离开敏感区域" if strategy == Strategy.WARN else "聚集状态预计解除")
            crowd_size = max(1, crowd_size - (1 if strategy == Strategy.WARN else 2))
        else:
            crowd_size = min(len(state.agents), crowd_size + 2)
            changes.append("未干预情况下聚集规模可能继续增加")

        after_risk = round(min(100, before_risk * float(effect["risk_factor"])), 1)
        state.risk_state.overall_score = after_risk
        prediction = predict_world_state(state, horizon_minutes)
        return SimulationResult(
            strategy=strategy,
            horizon_minutes=horizon_minutes,
            before=RiskSnapshot(risk=before_risk, crowd_size=3),
            after=RiskSnapshot(risk=after_risk, crowd_size=crowd_size),
            changes=changes,
            action_cost=int(effect["cost"]),
            leave_probability=float(effect["leave_probability"]),
            prediction=prediction,
        )

    def compare(self, source: WorldState, horizon_minutes: int = 10) -> list[SimulationResult]:
        return [self.run(source, strategy, horizon_minutes) for strategy in Strategy]

