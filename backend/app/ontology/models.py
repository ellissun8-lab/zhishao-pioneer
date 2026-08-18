from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BehaviorState(StrEnum):
    IDLE = "idle"
    MOVING = "moving"
    ENTERING_SENSITIVE_ZONE = "entering_sensitive_zone"
    GATHERING = "gathering"
    RISK_ESCALATING = "risk_escalating"
    DISPERSING = "dispersing"
    RESOLVED = "resolved"


class EventType(StrEnum):
    PERSON_DETECTED = "PersonDetected"
    VEHICLE_DETECTED = "VehicleDetected"
    CROWD_DETECTED = "CrowdDetected"
    MOVE_STARTED = "MoveStarted"
    MOVE_STOPPED = "MoveStopped"
    ZONE_ENTERED = "ZoneEntered"
    ZONE_EXITED = "ZoneExited"
    CROWD_GATHERED = "CrowdGathered"
    CROWD_DISPERSED = "CrowdDispersed"
    RISK_OBJECT_DETECTED = "RiskObjectDetected"
    ALERT_TRIGGERED = "AlertTriggered"
    INTERVENTION_APPLIED = "InterventionApplied"


# 必须携带 subject_id 的事件：感知与主体行为事实；系统级事件（AlertTriggered / InterventionApplied）除外
SUBJECT_REQUIRED_EVENTS = frozenset(
    {
        EventType.PERSON_DETECTED,
        EventType.VEHICLE_DETECTED,
        EventType.CROWD_DETECTED,
        EventType.MOVE_STARTED,
        EventType.MOVE_STOPPED,
        EventType.ZONE_ENTERED,
        EventType.ZONE_EXITED,
        EventType.CROWD_GATHERED,
        EventType.RISK_OBJECT_DETECTED,
    }
)


class ActionType(StrEnum):
    OBSERVE = "Observe"
    WARN = "Warn"
    GUIDE_LEAVE = "GuideLeave"
    DISPATCH = "Dispatch"
    INTERVENE = "Intervene"


class ZoneType(StrEnum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"


class Position(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class Agent(BaseModel):
    id: str
    type: str = "Person"
    synthetic: bool = True
    # 展示用中文名称（模拟人员NNN），仅用于前端显示，不参与主键/关系
    display_name: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    position: Position
    destination: Position | None = None
    home_zone: str = "residential_demo"
    mobility_pattern: str = "commute"
    behavior_state: BehaviorState = BehaviorState.IDLE
    social_group: str = "group_0"
    base_risk: float = 10
    risk_score: float = 10
    active_zone_ids: list[str] = Field(default_factory=list)
    history: list[Position] = Field(default_factory=list)


class Place(BaseModel):
    id: str
    type: str = "Place"
    category: str
    name: str
    position: Position
    source: str = "demo_public_dataset"


class Zone(BaseModel):
    id: str
    type: str = "Zone"
    zone_type: ZoneType = ZoneType.SENSITIVE
    name: str
    center: Position
    radius: float = 500
    sensitivity: float = Field(default=0.9, ge=0, le=1)


class Event(BaseModel):
    id: str = Field(default_factory=lambda: f"event_{uuid4().hex[:10]}")
    type: EventType
    subject_id: str | None = None
    object_id: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    confidence: float = Field(default=1, ge=0, le=1)
    source: str = "simulation"
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_event(self) -> "Event":
        if self.type in SUBJECT_REQUIRED_EVENTS and not self.subject_id:
            raise ValueError(f"Event {self.type.value} requires subject_id")
        position = self.metadata.get("position")
        if position is not None:
            Position.model_validate(position)
        return self


class Relation(BaseModel):
    subject_id: str
    predicate: str
    object_id: str
    since: datetime = Field(default_factory=utc_now)

