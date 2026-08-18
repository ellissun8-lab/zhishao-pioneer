from backend.app.data.seed import create_demo_state
from backend.app.ontology.models import BehaviorState, EventType, Position
from backend.app.simulation.runtime import SyntheticAgentRuntime
from backend.app.world.event_bus import EventBus


def _positions(state):
    return [(agent.id, round(agent.position.lng, 9), round(agent.position.lat, 9)) for agent in state.agents.values()]


def test_runtime_moves_agents_and_emits_move_and_zone_events():
    state = create_demo_state(80)
    bus = EventBus(state)
    before = {agent.id: agent.position.model_copy() for agent in state.agents.values()}
    runtime = SyntheticAgentRuntime(seed=42)
    events: list = []
    for _ in range(60):
        events.extend(runtime.tick(state, bus.publish, dt_seconds=60))
    moved = [agent.id for agent in state.agents.values() if agent.position != before[agent.id]]
    types = {event.type for event in events}
    assert len(moved) >= 10
    assert EventType.MOVE_STARTED in types
    assert EventType.ZONE_ENTERED in types
    assert all(agent.synthetic for agent in state.agents.values())
    assert state.active_events, "runtime events must reach World State through the Event Bus"


def test_runtime_detects_crowd_when_agents_converge_in_zone():
    state = create_demo_state(3)
    bus = EventBus(state)
    zone = next(iter(state.zones.values()))
    for index, agent in enumerate(state.agents.values()):
        agent.position = Position(lng=zone.center.lng + 0.006, lat=zone.center.lat + index * 0.0002)
        agent.destination = Position(lng=zone.center.lng, lat=zone.center.lat)
        agent.behavior_state = BehaviorState.MOVING
    runtime = SyntheticAgentRuntime(seed=42)
    events: list = []
    baseline = state.risk_state.overall_score
    risk_at_gather = baseline
    for _ in range(40):
        tick_events = runtime.tick(state, bus.publish, dt_seconds=60)
        events.extend(tick_events)
        if any(event.type == EventType.CROWD_GATHERED for event in tick_events):
            risk_at_gather = max(risk_at_gather, state.risk_state.overall_score)
    types = [event.type for event in events]
    assert EventType.ZONE_ENTERED in types
    assert EventType.CROWD_GATHERED in types
    gathered = next(event for event in events if event.type == EventType.CROWD_GATHERED)
    assert len(gathered.metadata["agent_ids"]) >= 3
    assert risk_at_gather > baseline, "CrowdGathered must raise risk through the Risk Engine"


def test_runtime_is_deterministic_for_same_seed():
    def run():
        state = create_demo_state(80)
        bus = EventBus(state)
        runtime = SyntheticAgentRuntime(seed=7)
        for _ in range(30):
            runtime.tick(state, bus.publish, dt_seconds=30)
        return _positions(state)

    assert run() == run()


def test_runtime_does_not_touch_risk_directly_but_via_events():
    state = create_demo_state(3)
    bus = EventBus(state)
    baseline = state.risk_state.overall_score
    zone = next(iter(state.zones.values()))
    for index, agent in enumerate(state.agents.values()):
        agent.position = Position(lng=zone.center.lng + 0.004, lat=zone.center.lat + index * 0.0001)
        agent.destination = Position(lng=zone.center.lng, lat=zone.center.lat)
        agent.behavior_state = BehaviorState.MOVING
    runtime = SyntheticAgentRuntime(seed=42)
    for _ in range(10):
        runtime.tick(state, bus.publish, dt_seconds=60)
    assert any(event.type == EventType.ZONE_ENTERED for event in state.active_events)
    assert state.risk_state.overall_score > baseline
