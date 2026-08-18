from ..behavior.prediction import predict_world_state
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

