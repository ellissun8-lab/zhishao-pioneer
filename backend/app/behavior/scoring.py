from __future__ import annotations

from datetime import datetime, timezone

from ..ontology.models import EventType, RiskLevel, ZoneType
from ..world.state import RiskContributor, RiskState, WorldState
from .rules import EVENT_RULES, decayed_weight


def calculate_risk(state: WorldState, now: datetime | None = None) -> RiskState:
    now = now or datetime.now(timezone.utc)
    contributions: dict[str, float] = {}
    contributors: list[RiskContributor] = []
    reasons: list[str] = []

    def add_contribution(key: str, delta: float, reason: str | None = None) -> None:
        nonlocal score
        score += delta
        contributions[key] = round(contributions.get(key, 0) + delta, 2)
        contributors.append(RiskContributor(type=key, delta=round(delta, 2)))
        if reason:
            reasons.append(reason)

    score = max((agent.base_risk for agent in state.agents.values()), default=0)
    contributions["base_risk"] = score
    contributors.append(RiskContributor(type="base_risk", delta=score))

    sensitivity = max(
        (
            zone.sensitivity
            for agent in state.agents.values()
            for zone_id in agent.active_zone_ids
            if (zone := state.zones.get(zone_id)) and zone.zone_type == ZoneType.SENSITIVE
        ),
        default=0,
    )
    if sensitivity:
        value = sensitivity * 20
        score += value
        contributions["sensitive_zone"] = round(value, 2)
        # Zone 风险是 State 而非 Event：只要主体仍在敏感区（active_zone_ids），贡献持续存在、不随时间衰减
        contributors.append(RiskContributor(type="SensitiveZoneActive", delta=round(value, 2)))
        reasons.append("模拟主体进入敏感区域")

    for event in state.active_events:
        rule = EVENT_RULES.get(event.type)
        if not rule:
            continue
        event_time = event.timestamp if event.timestamp.tzinfo else event.timestamp.replace(tzinfo=timezone.utc)
        age = max(0, (now - event_time).total_seconds() / 60)
        value = decayed_weight(rule.weight, age, rule.half_life_minutes) * event.confidence
        key = event.type.value
        add_contribution(key, value)
        if event.type == EventType.CROWD_GATHERED:
            reasons.append("检测到模拟聚集事件")
        elif event.type == EventType.CROWD_DETECTED:
            reasons.append("模拟视觉感知检测到人流聚集（感知层）")
        elif event.type == EventType.RISK_OBJECT_DETECTED:
            reasons.append("模拟视觉感知检测到风险物品")
        elif event.type == EventType.VEHICLE_DETECTED:
            reasons.append("模拟视觉感知检测到车辆滞留")

    if now.hour >= 22 or now.hour < 5:
        score += 10
        contributions["abnormal_time"] = 10
        contributors.append(RiskContributor(type="abnormal_time", delta=10))
        reasons.append("当前处于异常时段")

    if any(agent.risk_level == RiskLevel.HIGH for agent in state.agents.values()):
        bonus = score * 0.15
        score += bonus
        contributions["high_risk_multiplier"] = 1.15
        contributors.append(RiskContributor(type="high_risk_multiplier", delta=round(bonus, 2)))
        reasons.append("存在高风险等级模拟主体")

    score = round(min(100, score), 1)
    level = "critical" if score >= 80 else "high" if score >= 60 else "medium" if score >= 30 else "low"
    return RiskState(
        overall_score=score,
        level=level,
        reasons=list(dict.fromkeys(reasons)),
        contributors=contributors,
        rule_contributions=contributions,
        history=[*state.risk_state.history[-19:], score],
    )
