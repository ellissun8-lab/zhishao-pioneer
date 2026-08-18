from pydantic import BaseModel, Field

from ..ontology.models import Event, EventType
from .base import CVEventProvider


class BBox(BaseModel):
    """归一化检测框（0~1），与具体画面分辨率解耦。"""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class Detection(BaseModel):
    """统一 CV Detection 数据模型；全部为 Synthetic Data。"""

    id: str
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: BBox
    subject_id: str | None = None
    synthetic: bool = True


# 感知层固定置信度（Demo seed=42 语义：同一场景每次识别结果完全稳定，不随时间抖动）
SCENE_CONFIDENCE = {
    "person": [0.96, 0.94, 0.92],  # 0.92~0.98
    "crowd": [0.91],  # 0.88~0.95
    "risk_object": [0.89],  # 0.85~0.93
    "vehicle": [0.93],  # 0.90~0.97
}

# 每个场景的检测框布局（归一化 bbox），前端模拟画面按同一布局绘制轮廓
SCENE_LAYOUT: dict[str, list[tuple[str, BBox]]] = {
    "scene_normal": [("person", BBox(x=0.12, y=0.30, width=0.16, height=0.52))],
    "scene_crowd": [
        ("person", BBox(x=0.08, y=0.28, width=0.15, height=0.55)),
        ("person", BBox(x=0.40, y=0.32, width=0.15, height=0.52)),
        ("person", BBox(x=0.70, y=0.26, width=0.15, height=0.56)),
        ("crowd", BBox(x=0.04, y=0.18, width=0.86, height=0.70)),
    ],
    "scene_risk_object": [
        ("person", BBox(x=0.10, y=0.28, width=0.16, height=0.54)),
        ("risk_object", BBox(x=0.58, y=0.62, width=0.24, height=0.18)),
    ],
    "scene_high_risk": [
        ("person", BBox(x=0.08, y=0.28, width=0.15, height=0.55)),
        ("person", BBox(x=0.40, y=0.32, width=0.15, height=0.52)),
        ("person", BBox(x=0.70, y=0.26, width=0.15, height=0.56)),
        ("crowd", BBox(x=0.04, y=0.18, width=0.86, height=0.70)),
        ("risk_object", BBox(x=0.58, y=0.62, width=0.24, height=0.18)),
    ],
}

DEFAULT_SCENE_SUBJECTS = ["agent_A", "agent_B", "agent_C"]


def _label_confidence(label: str, index: int) -> float:
    values = SCENE_CONFIDENCE[label]
    return values[index % len(values)]


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

    def detect_scene(
        self,
        scene_id: str,
        subject_ids: list[str] | None = None,
    ) -> dict[str, object]:
        """按场景输出 Detection 列表与标准 Event（仅感知事实，绝不产出 CrowdGathered）。"""
        layout = SCENE_LAYOUT.get(scene_id)
        if layout is None:
            raise ValueError(f"Unsupported scene: {scene_id}")
        subjects = subject_ids or DEFAULT_SCENE_SUBJECTS
        person_counter = 0
        detections: list[Detection] = []
        for index, (label, bbox) in enumerate(layout):
            detection = Detection(
                id=f"det_{index + 1:03d}",
                label=label,
                confidence=_label_confidence(label, 0 if label != "person" else person_counter),
                bbox=bbox,
                subject_id=subjects[person_counter] if label == "person" and person_counter < len(subjects) else subjects[0],
                synthetic=True,
            )
            if label == "person":
                person_counter += 1
            detections.append(detection)
        events = [self._detection_to_event(scene_id, detection) for detection in detections]
        return {"scene_id": scene_id, "synthetic": True, "detections": detections, "events": events}

    @staticmethod
    def _detection_to_event(scene_id: str, detection: Detection) -> Event:
        event_type = {
            "person": EventType.PERSON_DETECTED,
            "crowd": EventType.CROWD_DETECTED,
            "risk_object": EventType.RISK_OBJECT_DETECTED,
            "vehicle": EventType.VEHICLE_DETECTED,
        }.get(detection.label)
        if event_type is None:
            raise ValueError(f"Unsupported detection label: {detection.label}")
        # 审计 payload 携带 scene_id / detection_id / bbox / label，事件仍走统一 Event Bus
        metadata: dict[str, object] = {
            "scene_id": scene_id,
            "detection_id": detection.id,
            "label": detection.label,
            "bbox": detection.bbox.model_dump(),
        }
        if detection.label == "risk_object":
            # 模拟 Demo 严谨性：只表述为“疑似”，不做“确认刀具/武器”类判定
            metadata["display_name"] = "疑似风险物品"
        return Event(
            type=event_type,
            subject_id=detection.subject_id,
            confidence=detection.confidence,
            source="mock_cv",
            metadata=metadata,
        )
