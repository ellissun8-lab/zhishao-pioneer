"""RealCVProvider：真实训练模型推理（Ultralytics YOLO），绝不预设 Detection。

链路：image -> YOLO.predict -> results.boxes -> Detection[] -> Standard Event。

分层约束：
- 模型只输出 person / risk_object / vehicle；
- CrowdDetected 属于 perception aggregation（>=3 person + 空间距离阈值）；
- CrowdGathered 永远不由 CV 产生（由 World Behavior / Spatial Model 确认）。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ..ontology.models import Event, EventType
from .base import CVEventProvider
from .mock_cv import BBox, Detection

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "models" / "cv_detector" / "best.pt"
METRICS_PATH = PROJECT_ROOT / "models" / "cv_detector" / "metrics.json"
DEMO_DIR = PROJECT_ROOT / "data" / "cv_demo"

CLASS_NAMES = ("person", "risk_object", "vehicle")
DEFAULT_CONF_THRESHOLD = 0.25
# perception aggregation：>=3 person 且中心间距阈值内视为聚集
CROWD_PERSON_THRESHOLD = 3
CROWD_DISTANCE_THRESHOLD = 0.30

LABEL_TO_EVENT = {
    "person": EventType.PERSON_DETECTED,
    "risk_object": EventType.RISK_OBJECT_DETECTED,
    "vehicle": EventType.VEHICLE_DETECTED,
}


def model_version_from_metrics() -> str | None:
    try:
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = metrics.get("model_version")
    return str(version) if version else None


class RealCVProvider(CVEventProvider):
    """真实 YOLO 推理 Provider；接口与 MockCVProvider 兼容。"""

    def __init__(self, model_path: str | Path = MODEL_PATH, conf_threshold: float = DEFAULT_CONF_THRESHOLD) -> None:
        from ultralytics import YOLO  # 延迟导入：未安装 ultralytics 时仅 real 路径不可用

        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.model_version = model_version_from_metrics()
        self._inference_lock = threading.Lock()
        # 真实加载训练产物；失败由调用方捕获并进入显式 mock fallback
        self.model = YOLO(str(self.model_path))

    @staticmethod
    def model_available(model_path: str | Path = MODEL_PATH) -> bool:
        return Path(model_path).exists()

    def detect(self, event_name: str, subject_id: str | None = None) -> Event:
        """CVEventProvider 接口兼容方法（单事件语义）；真实推理入口是 detect_image。"""
        raise NotImplementedError("RealCVProvider 走 detect_image(image) 真实推理路径")

    def detect_image(self, image, conf_threshold: float | None = None) -> list[Detection]:
        """真实调用 YOLO.predict；Detection 全部来自 results.boxes，禁止任何预设值。"""
        effective_threshold = self.conf_threshold if conf_threshold is None else conf_threshold
        # Ultralytics model 是跨请求共享的重量级实例；串行化 predict，避免内部可变状态并发竞争。
        with self._inference_lock:
            results = self.model.predict(source=image, conf=effective_threshold, verbose=False)
        return self._parse_results(results)

    def _parse_results(self, results) -> list[Detection]:
        detections: list[Detection] = []
        for result in results:
            height, width = result.orig_shape
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for index in range(len(boxes)):
                class_id = int(boxes.cls[index])
                confidence = float(boxes.conf[index])
                x1, y1, x2, y2 = (float(value) for value in boxes.xyxy[index])
                # 裁剪到画面内，保证归一化 bbox 合法
                x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
                y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
                if x2 - x1 < 1e-3 or y2 - y1 < 1e-3:
                    continue
                label = self._label_for(class_id)
                if label is None:
                    continue
                bbox = BBox(
                    x=round(x1 / width, 6),
                    y=round(y1 / height, 6),
                    width=round((x2 - x1) / width, 6),
                    height=round((y2 - y1) / height, 6),
                )
                detections.append(
                    Detection(
                        id=f"cv_det_{len(detections) + 1:03d}",
                        label=label,
                        confidence=round(confidence, 4),
                        bbox=bbox,
                        synthetic=True,
                    )
                )
        return detections

    @staticmethod
    def _label_for(class_id: int) -> str | None:
        if 0 <= class_id < len(CLASS_NAMES):
            return CLASS_NAMES[class_id]
        return None

    # ---------- Detection -> Standard Event（含 crowd 聚合） ----------

    def detections_to_events(
        self,
        detections: list[Detection],
        subject_ids: list[str],
        scene_id: str | None = None,
    ) -> list[Event]:
        """person->PersonDetected / risk_object->RiskObjectDetected / vehicle->VehicleDetected。

        crowd 不进模型：此处仅按 person 数量 + 空间距离做 perception aggregation 产出
        CrowdDetected；CrowdGathered 仍由行为/空间规则层产生。
        """
        events: list[Event] = []
        person_index = 0
        for detection in detections:
            event_type = LABEL_TO_EVENT.get(detection.label)
            if event_type is None:
                continue
            # 感知事件必须携带 subject_id（ontology 约束）：
            # person 依序分配；risk_object / vehicle 绑定首个 subject（与 MockCVProvider 语义一致）
            if detection.label == "person":
                subject = subject_ids[person_index] if person_index < len(subject_ids) else subject_ids[0]
                person_index += 1
            else:
                subject = subject_ids[0]
            metadata: dict[str, object] = {
                "detection_id": detection.id,
                "label": detection.label,
                "confidence": detection.confidence,
                "bbox": detection.bbox.model_dump(),
                "model_version": self.model_version,
            }
            if scene_id:
                metadata["scene_id"] = scene_id
            if detection.label == "risk_object":
                metadata["display_name"] = "疑似风险物品"
            events.append(
                Event(
                    type=event_type,
                    subject_id=subject,
                    confidence=detection.confidence,
                    source="real_cv",
                    metadata=metadata,
                )
            )

        crowd = aggregate_crowd(detections)
        if crowd is not None:
            events.append(
                Event(
                    type=EventType.CROWD_DETECTED,
                    subject_id=subject_ids[0] if subject_ids else None,
                    confidence=crowd["confidence"],
                    source="cv_aggregation",
                    metadata={
                        **crowd,
                        "rule": f"person_count >= {CROWD_PERSON_THRESHOLD} 且成对中心距 <= {CROWD_DISTANCE_THRESHOLD}",
                        "note": "perception aggregation；CrowdGathered 由行为/空间规则层另行确认",
                    },
                )
            )
        return events


def aggregate_crowd(detections: list[Detection]) -> dict[str, object] | None:
    """当前帧 person 聚合：>=3 人且任意成对中心距离 <= 阈值 -> CrowdDetected 事实。"""
    persons = [d for d in detections if d.label == "person"]
    if len(persons) < CROWD_PERSON_THRESHOLD:
        return None
    centers = [
        (d.bbox.x + d.bbox.width / 2, d.bbox.y + d.bbox.height / 2)
        for d in persons
    ]
    max_pair_distance = 0.0
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            distance = ((centers[i][0] - centers[j][0]) ** 2 + (centers[i][1] - centers[j][1]) ** 2) ** 0.5
            max_pair_distance = max(max_pair_distance, distance)
    if max_pair_distance > CROWD_DISTANCE_THRESHOLD:
        return None
    xs = [c[0] for c in centers]
    ys = [c[1] for c in centers]
    return {
        "person_count": len(persons),
        "max_pair_distance": round(max_pair_distance, 4),
        "confidence": round(min(d.confidence for d in persons), 4),
        "bbox": {
            "x": round(min(d.bbox.x for d in persons), 4),
            "y": round(min(d.bbox.y for d in persons), 4),
            "width": round(max(d.bbox.x + d.bbox.width for d in persons) - min(d.bbox.x for d in persons), 4),
            "height": round(max(d.bbox.y + d.bbox.height for d in persons) - min(d.bbox.y for d in persons), 4),
        },
        "centroid": [round(sum(xs) / len(xs), 4), round(sum(ys) / len(ys), 4)],
        "detection_ids": [d.id for d in persons],
    }


# ---------- 模块级懒加载单例（避免每个请求重复加载 YOLO） ----------

_provider: RealCVProvider | None = None
_provider_error: str | None = None
_last_detection_summary: dict[str, object] | None = None
_lock = threading.Lock()


def get_real_provider() -> RealCVProvider | None:
    """加载并缓存 RealCVProvider；模型缺失/加载失败返回 None（调用方显式 fallback）。"""
    global _provider, _provider_error
    with _lock:
        if _provider is not None:
            return _provider
        if not RealCVProvider.model_available():
            _provider_error = f"model file missing: {MODEL_PATH}"
            return None
        try:
            _provider = RealCVProvider()
            _provider_error = None
            return _provider
        except Exception as error:  # noqa: BLE001 - 任何加载失败都必须显式 fallback
            _provider_error = f"model load failed: {error}"
            return None


def reset_provider_cache() -> None:
    """测试钩子：清理单例缓存。"""
    global _provider, _provider_error
    with _lock:
        _provider = None
        _provider_error = None


def provider_unavailable_reason() -> str | None:
    return _provider_error


def record_last_detection_summary(summary: dict[str, object]) -> None:
    """记录最近一次 trained CV 推理摘要（Agent 工具 / UI 状态的数据源）。"""
    global _last_detection_summary
    with _lock:
        _last_detection_summary = summary


def get_last_detection_summary() -> dict[str, object] | None:
    with _lock:
        return _last_detection_summary


def clear_last_detection_summary() -> None:
    """清除最近推理摘要；World Reset 后禁止 Agent 引用重置前画面。"""
    global _last_detection_summary
    with _lock:
        _last_detection_summary = None
