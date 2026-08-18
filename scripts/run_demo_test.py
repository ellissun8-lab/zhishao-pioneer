"""无需启动 HTTP 服务的端到端 Demo 验证脚本。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.behavior.prediction import predict_world_state
from backend.app.data.seed import create_demo_state
from backend.app.llm.agent import explain_question
from backend.app.ontology.models import Event, EventType
from backend.app.simulation.engine import SimulationEngine
from backend.app.simulation.runtime import SyntheticAgentRuntime
from backend.app.simulation.strategies import Strategy
from backend.app.world.event_bus import EventBus


def run_scripted_story():
    state = create_demo_state(80)
    bus = EventBus(state)
    snapshots = [state.risk_state.overall_score]
    for event in [
        Event(type=EventType.MOVE_STARTED, subject_id="agent_A"),
        Event(type=EventType.ZONE_ENTERED, subject_id="agent_A", object_id="school_zone_001"),
        Event(type=EventType.CROWD_GATHERED, subject_id="agent_A", confidence=1),
        Event(type=EventType.RISK_OBJECT_DETECTED, subject_id="agent_A", confidence=1, source="mock_cv"),
    ]:
        bus.publish(event)
        snapshots.append(state.risk_state.overall_score)

    assert snapshots[-1] >= 80, snapshots
    assert any(item.type == "SensitiveZoneActive" for item in state.risk_state.contributors), state.risk_state.contributors
    return snapshots, state


def run_runtime_story():
    state = create_demo_state(80)
    bus = EventBus(state)
    runtime = SyntheticAgentRuntime(seed=42)
    positions_before = {agent.id: agent.position.model_copy() for agent in state.agents.values()}
    published: list[Event] = []
    for _ in range(60):
        published.extend(runtime.tick(state, bus.publish, dt_seconds=60))
    moved = [agent.id for agent in state.agents.values() if agent.position != positions_before[agent.id]]
    event_types = {event.type for event in published}
    assert len(moved) >= 10, f"runtime moved only {len(moved)} agents"
    assert EventType.MOVE_STARTED in event_types, event_types
    assert EventType.ZONE_ENTERED in event_types, event_types
    assert state.active_events, "runtime events should reach World State"
    return state, moved, event_types


def main() -> None:
    snapshots, state = run_scripted_story()

    comparisons = SimulationEngine().compare(state)
    assert len(comparisons) == 4
    assert next(item for item in comparisons if item.strategy == Strategy.WARN).after.risk < next(
        item for item in comparisons if item.strategy == Strategy.NONE
    ).after.risk
    explanation = explain_question("为什么学校区域现在是红色？", state)
    assert explanation["tools_used"] == ["get_risk_analysis", "get_active_events"]

    predictions = {horizon: predict_world_state(state, horizon) for horizon in (5, 10, 30)}
    assert all(0 <= prediction.risk_score <= 100 for prediction in predictions.values())
    future_answer = explain_question("未来10分钟会怎样？", state)
    assert future_answer["tools_used"] == ["predict_future"]

    runtime_state, moved, event_types = run_runtime_story()

    print("DEMO READY")
    print("风险演化:", " -> ".join(f"{value:.1f}" for value in snapshots))
    for result in comparisons:
        print(f"{result.strategy.value:12} {result.before.risk:5.1f} -> {result.after.risk:5.1f}")
    print("Agent解释:", explanation["answer"])
    print("未来预测:", ", ".join(f"{h}min={p.risk_score}" for h, p in predictions.items()))
    print("Agent预测问答:", future_answer["answer"])
    print(f"运行时推演: {len(moved)} 个主体移动, 产生事件类型: {sorted(t.value for t in event_types)}, 当前风险 {runtime_state.risk_state.overall_score:.1f}")


if __name__ == "__main__":
    main()
