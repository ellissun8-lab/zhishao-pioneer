from dataclasses import dataclass
from math import exp, log

from ..ontology.models import EventType


@dataclass(frozen=True)
class RiskRule:
    event_type: EventType
    weight: float
    half_life_minutes: float


EVENT_RULES = {
    # 行为层：空间规则确认后的聚集，权重高
    EventType.CROWD_GATHERED: RiskRule(EventType.CROWD_GATHERED, 20, 10),
    # 感知层：视觉感知到的人流聚集事实，权重低于行为层确认
    EventType.CROWD_DETECTED: RiskRule(EventType.CROWD_DETECTED, 10, 8),
    EventType.RISK_OBJECT_DETECTED: RiskRule(EventType.RISK_OBJECT_DETECTED, 35, 30),
    EventType.VEHICLE_DETECTED: RiskRule(EventType.VEHICLE_DETECTED, 8, 15),
}


def decayed_weight(weight: float, age_minutes: float, half_life_minutes: float) -> float:
    if age_minutes <= 0:
        return weight
    return weight * exp(-(log(2) / half_life_minutes) * age_minutes)

