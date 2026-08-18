from ..ontology.models import Event, EventType
from .base import CVEventProvider


class MockCVProvider(CVEventProvider):
    # 感知层：Mock CV 只产出感知事实（CrowdDetected），
    # CrowdGathered 属于行为/空间规则确认事件，由 SyntheticAgentRuntime 或显式事件产生
    SUPPORTED = {
        "person": EventType.PERSON_DETECTED,
        "person_detected": EventType.PERSON_DETECTED,
        "vehicle": EventType.VEHICLE_DETECTED,
        "vehicle_detected": EventType.VEHICLE_DETECTED,
        "crowd": EventType.CROWD_DETECTED,
        "crowd_detected": EventType.CROWD_DETECTED,
        "risk_object": EventType.RISK_OBJECT_DETECTED,
    }

    def detect(self, event_name: str, subject_id: str | None = None) -> Event:
        event_type = self.SUPPORTED.get(event_name)
        if event_type is None:
            raise ValueError(f"Unsupported mock detection: {event_name}")
        return Event(type=event_type, subject_id=subject_id, confidence=0.91, source="mock_cv")
