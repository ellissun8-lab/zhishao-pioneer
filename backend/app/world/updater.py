from ..behavior.engine import BehaviorEngine
from ..ontology.models import Event, EventType, Relation, utc_now
from .state import WorldState
from .state_machine import transition

MAX_ACTIVE_EVENTS = 100


class WorldStateUpdater:
    def __init__(self, behavior_engine: BehaviorEngine | None = None) -> None:
        self.behavior_engine = behavior_engine or BehaviorEngine()

    def apply(self, state: WorldState, event: Event) -> WorldState:
        agent = state.agents.get(event.subject_id or "")
        if agent:
            new_behavior = transition(event.type, agent.behavior_state)
            if new_behavior is None:
                # 非法状态跳转：拒绝（保持当前行为状态），并在事件 metadata 中明确记录，随审计日志可追溯
                event.metadata.setdefault(
                    "rejected_transition",
                    f"{agent.behavior_state.value} + {event.type.value}",
                )
            else:
                agent.behavior_state = new_behavior
            position_data = event.metadata.get("position")
            if isinstance(position_data, dict):
                agent.history.append(agent.position.model_copy())
                agent.position = agent.position.model_validate(position_data)
            if event.type == EventType.ZONE_ENTERED and event.object_id and event.object_id not in agent.active_zone_ids:
                agent.active_zone_ids.append(event.object_id)
                state.relations.append(Relation(subject_id=agent.id, predicate="enters", object_id=event.object_id))
            if event.type == EventType.ZONE_EXITED and event.object_id:
                agent.active_zone_ids = [zone_id for zone_id in agent.active_zone_ids if zone_id != event.object_id]
                state.relations = [relation for relation in state.relations if not (relation.subject_id == agent.id and relation.object_id == event.object_id)]

        if event.type == EventType.CROWD_GATHERED:
            member_ids = [item for item in event.metadata.get("agent_ids", []) if isinstance(item, str) and item != event.subject_id]
            for member_id in member_ids:
                state.relations.append(Relation(subject_id=event.subject_id or "", predicate="gathers_with", object_id=member_id))
        if event.type == EventType.CROWD_DISPERSED:
            state.active_events = [item for item in state.active_events if item.type != EventType.CROWD_GATHERED]
            state.relations = [relation for relation in state.relations if relation.predicate != "gathers_with"]
        elif event.type == EventType.INTERVENTION_APPLIED:
            state.active_events = []
        else:
            state.active_events.append(event)
            if len(state.active_events) > MAX_ACTIVE_EVENTS:
                state.active_events = state.active_events[-MAX_ACTIVE_EVENTS:]
        state.timestamp = utc_now()
        return self.behavior_engine.recalculate(state)
