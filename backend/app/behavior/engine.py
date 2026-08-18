from ..world.state import WorldState
from .scoring import calculate_risk


class BehaviorEngine:
    def recalculate(self, state: WorldState) -> WorldState:
        state.risk_state = calculate_risk(state)
        for agent in state.agents.values():
            agent.risk_score = state.risk_state.overall_score
        return state

