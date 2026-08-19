"""World State -> 训练特征。

特征必须是可从任意 WorldState 聚合得到的数值量；
严禁把 agent id / display_name / episode id / event id 等身份标识
作为特征（防止身份泄漏与记忆化）。
"""

from __future__ import annotations

from ..ontology.models import Agent, EventType
from ..world.state import WorldState

# 训练特征固定顺序（模型输入契约，训练与推理必须一致）
FEATURE_SCHEMA: list[str] = [
    "current_risk",
    "active_event_count",
    "nearby_agent_count",
    "high_risk_agent_count",
    "sensitive_zone_active",
    "crowd_detected",
    "crowd_gathered",
    "risk_object_detected",
    "vehicle_detected",
    "average_agent_risk",
    "event_recency_minutes",
    "hour_of_day",
    "crowd_size",
    "zone_sensitivity_max",
    "mobility_intensity",
    "event_confidence_max",
]

# 禁止出现在特征中的标识类 token（测试会校验）
FORBIDDEN_FEATURE_TOKENS: tuple[str, ...] = ("agent_id", "display_name", "episode_id", "event_id", "subject", "name")

HIGH_RISK_AGENT_SCORE = 60.0
NO_EVENT_RECENCY_MINUTES = 60.0


def _nearby_agent_count(agents: list[Agent]) -> int:
    """同一敏感区域内成员数 >= 2 时，该区域内的主体视为互相邻近。"""
    zone_members: dict[str, int] = {}
    for agent in agents:
        for zone_id in agent.active_zone_ids:
            zone_members[zone_id] = zone_members.get(zone_id, 0) + 1
    crowded_zones = {zone_id for zone_id, count in zone_members.items() if count >= 2}
    return sum(1 for agent in agents if any(zone_id in crowded_zones for zone_id in agent.active_zone_ids))


def extract_features(state: WorldState) -> dict[str, float]:
    """从 WorldState 提取 FEATURE_SCHEMA 定义的数值特征。"""
    agents = list(state.agents.values())
    events = state.active_events
    event_types = {event.type for event in events}
    sensitive_zone_active = float(any(agent.active_zone_ids for agent in agents))
    crowd_events = [event for event in events if event.type in {EventType.CROWD_DETECTED, EventType.CROWD_GATHERED}]
    crowd_size = 0
    for event in crowd_events:
        size = event.metadata.get("crowd_size", event.metadata.get("agent_count"))
        if isinstance(size, (int, float)) and size > crowd_size:
            crowd_size = int(size)
    zone_sensitivity = [
        state.zones[zone_id].sensitivity
        for agent in agents
        for zone_id in agent.active_zone_ids
        if zone_id in state.zones
    ]
    moving_states = {"moving", "entering_sensitive_zone", "gathering"}
    latest_event_time = max((event.timestamp for event in events), default=None)
    if latest_event_time is not None:
        recency_minutes = (state.timestamp - latest_event_time).total_seconds() / 60
        event_recency = max(0.0, min(240.0, recency_minutes))
    else:
        event_recency = NO_EVENT_RECENCY_MINUTES
    return {
        "current_risk": float(state.risk_state.overall_score),
        "active_event_count": float(len(events)),
        "nearby_agent_count": float(_nearby_agent_count(agents)),
        "high_risk_agent_count": float(sum(1 for agent in agents if agent.risk_score >= HIGH_RISK_AGENT_SCORE)),
        "sensitive_zone_active": sensitive_zone_active,
        "crowd_detected": float(EventType.CROWD_DETECTED in event_types),
        "crowd_gathered": float(EventType.CROWD_GATHERED in event_types),
        "risk_object_detected": float(EventType.RISK_OBJECT_DETECTED in event_types),
        "vehicle_detected": float(EventType.VEHICLE_DETECTED in event_types),
        "average_agent_risk": (sum(agent.risk_score for agent in agents) / len(agents)) if agents else 0.0,
        "event_recency_minutes": event_recency,
        "hour_of_day": float(state.timestamp.hour),
        "crowd_size": float(crowd_size),
        "zone_sensitivity_max": max(zone_sensitivity) if zone_sensitivity else 0.0,
        "mobility_intensity": (sum(1 for agent in agents if agent.behavior_state.value in moving_states) / len(agents)) if agents else 0.0,
        "event_confidence_max": max((event.confidence for event in events), default=0.0),
    }
