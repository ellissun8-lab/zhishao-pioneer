from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..ontology.models import Agent, Event, Place, Relation, Zone, utc_now


class RiskContributor(BaseModel):
    type: str
    delta: float


class RiskState(BaseModel):
    overall_score: float = 0
    level: str = "low"
    reasons: list[str] = Field(default_factory=list)
    contributors: list[RiskContributor] = Field(default_factory=list)
    rule_contributions: dict[str, float] = Field(default_factory=dict)
    history: list[float] = Field(default_factory=list)


class WorldState(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    agents: dict[str, Agent] = Field(default_factory=dict)
    places: dict[str, Place] = Field(default_factory=dict)
    zones: dict[str, Zone] = Field(default_factory=dict)
    active_events: list[Event] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    risk_state: RiskState = Field(default_factory=RiskState)

    def clone(self) -> "WorldState":
        return self.model_copy(deep=True)
