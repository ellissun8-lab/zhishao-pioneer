from __future__ import annotations

from pydantic import BaseModel

from ..ontology.models import EventType
from ..world.state import WorldState


class Prediction(BaseModel):
    horizon_minutes: int
    risk_score: float
    risk_trend: str
    gather_probability: float
    zone_entry_probability: float
    predicted_agents: int
    model: str = "transparent_rule_probability_v1"
    synthetic: bool = True


def predict_world_state(state: WorldState, horizon_minutes: int) -> Prediction:
    if horizon_minutes not in {5, 10, 30}:
        raise ValueError("horizon_minutes must be one of 5, 10, 30")
    current = state.risk_state.overall_score
    has_crowd = any(event.type in {EventType.CROWD_GATHERED, EventType.CROWD_DETECTED} for event in state.active_events)
    has_object = any(event.type == EventType.RISK_OBJECT_DETECTED for event in state.active_events)
    zone_count = sum(bool(agent.active_zone_ids) for agent in state.agents.values())
    drift = (4 if has_crowd else -2) + (3 if has_object else 0)
    time_factor = {5: 0.6, 10: 1.0, 30: 1.4}[horizon_minutes]
    predicted_risk = round(max(0, min(100, current + drift * time_factor)), 1)
    trend = "up" if predicted_risk > current else "down" if predicted_risk < current else "stable"
    gather_probability = min(0.95, 0.22 + (0.48 if has_crowd else 0) + current / 500)
    zone_entry_probability = min(0.9, 0.2 + zone_count * 0.12 + current / 600)
    predicted_agents = min(len(state.agents), max(zone_count, 3 if has_crowd else zone_count + 1))
    return Prediction(
        horizon_minutes=horizon_minutes,
        risk_score=predicted_risk,
        risk_trend=trend,
        gather_probability=round(gather_probability, 2),
        zone_entry_probability=round(zone_entry_probability, 2),
        predicted_agents=predicted_agents,
    )

