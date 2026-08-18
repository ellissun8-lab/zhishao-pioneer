"""行为状态机：current_state + event_type 的合法转换表。

transition() 返回 None 表示非法转换，由调用方拒绝或明确记录；
InterventionApplied 是全局干预，任何状态都允许进入 Resolved。
"""

from ..ontology.models import BehaviorState, EventType

TRANSITIONS: dict[tuple[BehaviorState, EventType], BehaviorState] = {
    (BehaviorState.IDLE, EventType.MOVE_STARTED): BehaviorState.MOVING,
    (BehaviorState.IDLE, EventType.ZONE_ENTERED): BehaviorState.ENTERING_SENSITIVE_ZONE,
    (BehaviorState.IDLE, EventType.RISK_OBJECT_DETECTED): BehaviorState.RISK_ESCALATING,
    (BehaviorState.MOVING, EventType.MOVE_STOPPED): BehaviorState.IDLE,
    (BehaviorState.MOVING, EventType.ZONE_ENTERED): BehaviorState.ENTERING_SENSITIVE_ZONE,
    (BehaviorState.MOVING, EventType.RISK_OBJECT_DETECTED): BehaviorState.RISK_ESCALATING,
    (BehaviorState.ENTERING_SENSITIVE_ZONE, EventType.CROWD_GATHERED): BehaviorState.GATHERING,
    (BehaviorState.ENTERING_SENSITIVE_ZONE, EventType.ZONE_EXITED): BehaviorState.MOVING,
    (BehaviorState.ENTERING_SENSITIVE_ZONE, EventType.RISK_OBJECT_DETECTED): BehaviorState.RISK_ESCALATING,
    (BehaviorState.GATHERING, EventType.CROWD_GATHERED): BehaviorState.GATHERING,
    (BehaviorState.GATHERING, EventType.CROWD_DISPERSED): BehaviorState.DISPERSING,
    (BehaviorState.GATHERING, EventType.ZONE_EXITED): BehaviorState.DISPERSING,
    (BehaviorState.GATHERING, EventType.RISK_OBJECT_DETECTED): BehaviorState.RISK_ESCALATING,
    (BehaviorState.RISK_ESCALATING, EventType.CROWD_DISPERSED): BehaviorState.DISPERSING,
    (BehaviorState.RISK_ESCALATING, EventType.ZONE_EXITED): BehaviorState.DISPERSING,
    (BehaviorState.DISPERSING, EventType.MOVE_STOPPED): BehaviorState.IDLE,
    (BehaviorState.DISPERSING, EventType.MOVE_STARTED): BehaviorState.MOVING,
    (BehaviorState.DISPERSING, EventType.RISK_OBJECT_DETECTED): BehaviorState.RISK_ESCALATING,
    (BehaviorState.RESOLVED, EventType.MOVE_STARTED): BehaviorState.MOVING,
}

GLOBAL_TRANSITIONS: dict[EventType, BehaviorState] = {
    EventType.INTERVENTION_APPLIED: BehaviorState.RESOLVED,
}


def transition(event_type: EventType, current: BehaviorState) -> BehaviorState | None:
    """合法转换返回目标状态；非法转换返回 None（调用方必须拒绝或明确记录）。"""
    if event_type in GLOBAL_TRANSITIONS:
        return GLOBAL_TRANSITIONS[event_type]
    return TRANSITIONS.get((current, event_type))
