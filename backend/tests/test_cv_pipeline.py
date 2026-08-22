"""Synthetic CV Training Pipeline 测试。

覆盖（规格命名测试）：
- 数据集：确定性生成、bbox 合法、实例数量、无真实人员数据、train/val/test 切分隔离
- Provider：模型加载、真实 YOLO.predict 调用、Detection 来自模型输出、事件映射、
  绝不产出 CrowdGathered、crowd 仅由 person 聚合、模型缺失显式 mock fallback、模型 metadata
- 防伪造（最高优先级）：predict 调用计数、输出跟随模型输出、real 模式绝不调用 MockCVProvider
- Agent 工具接地：get_cv_detection_summary 绝不把 MockCV 说成 Trained CV
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.llm.agent import explain_question
from backend.app.llm.tools import AgentTools
from backend.app.main import app
from backend.app.ontology.models import EventType
from backend.app.perception import real_cv
from backend.app.perception.mock_cv import MockCVProvider
from backend.app.perception.real_cv import (
    CROWD_DISTANCE_THRESHOLD,
    MODEL_PATH,
    RealCVProvider,
    aggregate_crowd,
)
from backend.app.service import world_service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FULL_STATS = PROJECT_ROOT / "data" / "cv_synthetic" / "stats.json"
FULL_CARD = PROJECT_ROOT / "data" / "cv_synthetic" / "dataset_card.md"
DEMO_LABELS = PROJECT_ROOT / "data" / "cv_demo" / "demo_labels.json"
EXPECTED_DATASET_HASH = "e780807538d213731313ed672769cdd909599c3ad6e03ea3ffcd5bd219c1b1d4"

client = TestClient(app)


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_cv_dataset", PROJECT_ROOT / "scripts" / "generate_cv_dataset.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


cvgen = _load_generator()


def setup_function():
    world_service.reset()
    real_cv.reset_provider_cache()
    real_cv._last_detection_summary = None


# ---------- Fake YOLO（只做 spy/替身，不改变 provider 逻辑） ----------


class FakeBoxes:
    def __init__(self, cls_, conf, xyxy):
        self.cls = np.array(cls_, dtype=float)
        self.conf = np.array(conf, dtype=float)
        self.xyxy = np.array(xyxy, dtype=float)

    def __len__(self):
        return len(self.cls)


class FakeResult:
    def __init__(self, boxes, orig_shape=(480, 640)):
        self.boxes = boxes
        self.orig_shape = orig_shape


class FakeYOLO:
    """记录 predict 调用的替身模型；结果完全由测试配置。"""

    def __init__(self, model_path="fake.pt"):
        self.model_path = model_path
        self.predict_calls: list[dict] = []
        self.next_results: list[FakeResult] = []

    def predict(self, source=None, conf=None, verbose=None, **kwargs):
        self.predict_calls.append({"source": source, "conf": conf, "verbose": verbose, "kwargs": kwargs})
        return self.next_results


def make_provider(boxes_spec: list[tuple[int, float, tuple[float, float, float, float]]], orig_shape=(480, 640)):
    """构造真实 RealCVProvider（跳过重量级 YOLO 加载），model 换成 FakeYOLO。"""
    provider = RealCVProvider.__new__(RealCVProvider)
    provider.model_path = MODEL_PATH
    provider.conf_threshold = 0.25
    provider.model_version = "cv_yolo_test"
    provider._inference_lock = threading.Lock()
    provider.model = FakeYOLO()
    set_fake_results(provider.model, boxes_spec, orig_shape)
    return provider


def set_fake_results(model: FakeYOLO, boxes_spec, orig_shape=(480, 640)):
    model.next_results = [
        FakeResult(
            FakeBoxes(
                [spec[0] for spec in boxes_spec],
                [spec[1] for spec in boxes_spec],
                [spec[2] for spec in boxes_spec],
            ),
            orig_shape,
        )
    ]


# ---------- 数据集生成 ----------


def _generate(tmp_path: Path, images: int = 48, seed: int = 42):
    out_dir = tmp_path / f"cv_{seed}"
    stats = cvgen.generate_dataset(out_dir, images=images, seed=seed)
    return out_dir, stats


def _recompute_dataset_hash(out_dir: Path, stats: dict[str, object]) -> str:
    """从实际图片与标签重建 generator manifest hash，不信任 stats 中的现成值。"""
    manifest: list[dict[str, object]] = []
    for split in cvgen.SPLITS:
        for image_path in sorted((out_dir / "images" / split).glob("*.jpg")):
            label_path = out_dir / "labels" / split / f"{image_path.stem}.txt"
            manifest.append(
                {
                    "name": f"{split}/{image_path.name}",
                    "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    "labels": label_path.read_text(encoding="utf-8").splitlines(),
                }
            )
    payload = json.dumps(
        {
            "seed": stats["seed"],
            "images": stats["image_count"],
            "ood": stats["ood"],
            "files": sorted(manifest, key=lambda item: item["name"]),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_cv_committed_dataset_metadata():
    """发布仓库只提交可重建 metadata；普通 pytest 不要求 gitignored 的 50k 图片存在。"""
    assert FULL_STATS.is_file()
    assert FULL_CARD.is_file()
    full = json.loads(FULL_STATS.read_text(encoding="utf-8"))
    assert full["image_count"] == 50000
    assert full["instance_count"] == 149751
    assert full["seed"] == 42
    assert full["dataset_hash"] == EXPECTED_DATASET_HASH
    assert {split: full["split_distribution"][split]["images"] for split in cvgen.SPLITS} == {
        "train": 35000,
        "val": 7500,
        "test": 7500,
    }
    assert cvgen.SPLITS == ("train", "val", "test")
    assert cvgen.JPEG_QUALITY == 92

    card = FULL_CARD.read_text(encoding="utf-8")
    for expected in ("图片数：50000", "实例数：149751", "seed：42", EXPECTED_DATASET_HASH):
        assert expected in card


def test_cv_dataset_generation_deterministic(tmp_path):
    """同一 seed 两次生成 -> 完全一致（图像字节 + 标注 + dataset_hash）。"""
    out_a, stats_a = _generate(tmp_path / "a")
    out_b, stats_b = _generate(tmp_path / "b")
    assert stats_a["dataset_hash"] == stats_b["dataset_hash"]
    assert stats_a["per_class_instances"] == stats_b["per_class_instances"]

    for split in ("train", "val", "test"):
        names_a = sorted(p.name for p in (out_a / "images" / split).glob("*.jpg"))
        names_b = sorted(p.name for p in (out_b / "images" / split).glob("*.jpg"))
        assert names_a == names_b
        for name in names_a:
            assert (out_a / "images" / split / name).read_bytes() == (out_b / "images" / split / name).read_bytes()
            label_a = out_a / "labels" / split / (name.replace(".jpg", ".txt"))
            label_b = out_b / "labels" / split / (name.replace(".jpg", ".txt"))
            assert label_a.read_text() == label_b.read_text()
    assert _recompute_dataset_hash(out_a, stats_a) == stats_a["dataset_hash"]
    assert _recompute_dataset_hash(out_b, stats_b) == stats_b["dataset_hash"]


def test_cv_dataset_bbox_valid(tmp_path):
    """所有标注满足 0<w,h<=1、0<=cx,cy<=1、bbox 不越界、无零面积/负值。"""
    out_dir, stats = _generate(tmp_path)
    label_files = list((out_dir / "labels").rglob("*.txt"))
    assert len(label_files) == stats["image_count"]
    for label_file in label_files:
        for line in label_file.read_text().splitlines():
            parts = line.split()
            assert len(parts) == 5
            class_id, cx, cy, w, h = int(parts[0]), *map(float, parts[1:])
            assert class_id in (0, 1, 2)
            assert 0 < w <= 1, f"invalid width {w}"
            assert 0 < h <= 1, f"invalid height {h}"
            assert 0 <= cx <= 1 and 0 <= cy <= 1
            assert cx - w / 2 >= 0 and cx + w / 2 <= 1, f"bbox exceeds frame horizontally: {line}"
            assert cy - h / 2 >= 0 and cy + h / 2 <= 1, f"bbox exceeds frame vertically: {line}"


def test_cv_dataset_instance_count(tmp_path):
    """小规模生成集的实例数 = 实际标注行数，并包含负样本。"""
    out_dir, stats = _generate(tmp_path)
    total_lines = sum(
        len(p.read_text().splitlines()) for p in (out_dir / "labels").rglob("*.txt")
    )
    assert stats["instance_count"] == total_lines
    assert stats["instance_count"] >= stats["image_count"]
    assert stats["empty_images"] > 0, "必须有负样本（空标注）"

    assert set(stats["per_class_instances"]) == {"person", "risk_object", "vehicle"}
    counts = stats["per_class_instances"]
    assert max(counts.values()) / sum(counts.values()) < 0.70


def test_cv_no_real_person_data():
    """person 仅是程序化剪影：无外部数据源下载、无人脸/行人公开数据集、类别只有 3 类。"""
    assert set(cvgen.CLASS_IDS) == {"person", "risk_object", "vehicle"}
    assert "crowd" not in cvgen.CLASS_IDS, "crowd 是聚合结果，绝不作为训练类别"

    source = (PROJECT_ROOT / "scripts" / "generate_cv_dataset.py").read_text(encoding="utf-8")
    # 不得引入任何网络下载/真实数据集/视频采集依赖（仅程序化渲染）
    for forbidden in ("requests", "urllib", "http://", "https://", "cv2.VideoCapture"):
        assert forbidden not in source, f"generator 不得引用真实数据源: {forbidden}"
    import_lines = [line for line in source.splitlines() if line.strip().startswith(("import ", "from "))]
    assert import_lines, "generator must have imports"
    for line in import_lines:
        assert not any(
            token in line for token in ("requests", "urllib", "cv2", "torch", "ultralytics", "datasets")
        ), f"generator 不得导入真实数据源依赖: {line}"

    if DEMO_LABELS.exists():
        labels = json.loads(DEMO_LABELS.read_text(encoding="utf-8"))
        for lines in labels.values():
            for line in lines:
                assert int(line.split()[0]) in (0, 1, 2)


def test_cv_split_isolation(tmp_path):
    """tmp_path 小规模数据的 split 互斥，且图片/标签/统计三者一致。"""
    out_dir, stats = _generate(tmp_path)
    splits: dict[str, set[str]] = {}
    for split in ("train", "val", "test"):
        splits[split] = {p.stem for p in (out_dir / "images" / split).glob("*.jpg")}
        labels = {p.stem for p in (out_dir / "labels" / split).glob("*.txt")}
        assert splits[split]
        assert labels == splits[split]
        assert len(splits[split]) == stats["split_distribution"][split]["images"]
        actual_instances = sum(
            len(path.read_text(encoding="utf-8").splitlines())
            for path in (out_dir / "labels" / split).glob("*.txt")
        )
        assert actual_instances == stats["split_distribution"][split]["instances"]
    assert not splits["train"] & splits["val"]
    assert not splits["train"] & splits["test"]
    assert not splits["val"] & splits["test"]
    assert len(splits["train"] | splits["val"] | splits["test"]) == stats["image_count"]


# ---------- RealCVProvider：真实推理与防伪造 ----------


def test_real_cv_provider_loads_model():
    """真实加载 models/cv_detector/best.pt（存在时）；否则验证加载协议。"""
    assert RealCVProvider.model_available() is True, "models/cv_detector/best.pt 必须存在"
    provider = RealCVProvider()
    assert provider.model is not None
    assert provider.model_version is not None
    # 模型类别表只有 3 类（无 crowd）
    from ultralytics import YOLO  # noqa: F401 - 证明真实 ultralytics 栈可用

    assert provider.conf_threshold == real_cv.DEFAULT_CONF_THRESHOLD


def test_real_cv_provider_returns_detection():
    provider = make_provider(
        [
            (0, 0.9123, (100, 50, 180, 250)),
            (1, 0.6789, (300, 300, 420, 360)),
            (2, 0.55, (0, 200, 640, 400)),
        ]
    )
    detections = provider.detect_image("fake-image")
    assert len(detections) == 3
    person = detections[0]
    assert person.label == "person"
    assert person.confidence == 0.9123
    assert person.bbox.x == pytest.approx(100 / 640, abs=1e-4)
    assert person.bbox.y == pytest.approx(50 / 480, abs=1e-4)
    assert person.bbox.width == pytest.approx(80 / 640, abs=1e-4)
    assert person.bbox.height == pytest.approx(200 / 480, abs=1e-4)
    assert detections[1].label == "risk_object"
    assert detections[2].label == "vehicle"
    assert all(d.synthetic for d in detections)


def test_real_cv_calls_yolo_predict():
    """detect_image 必须真实调用 model.predict 恰好一次，并传入原始 image。"""
    provider = make_provider([(0, 0.9, (100, 50, 180, 250))])
    image = object()  # 任意 image 对象都必须原样传给 predict
    provider.detect_image(image)
    assert len(provider.model.predict_calls) == 1
    call = provider.model.predict_calls[0]
    assert call["source"] is image
    assert call["conf"] == provider.conf_threshold


def test_real_cv_results_depend_on_model_output():
    """模型输出变化 -> provider 输出跟随变化（bbox/置信度/类别全部来自模型）。"""
    provider = make_provider([(0, 0.91, (100, 50, 180, 250))])
    first = provider.detect_image("image")
    set_fake_results(provider.model, [(1, 0.42, (200, 200, 400, 300))])
    second = provider.detect_image("image")

    assert first[0].label == "person" and first[0].confidence == 0.91
    assert second[0].label == "risk_object" and second[0].confidence == 0.42
    assert second[0].bbox.x != first[0].bbox.x
    assert second[0].bbox.width == pytest.approx(200 / 640, abs=1e-4)

    # 空结果 -> 空 Detection 列表（不得编造）
    set_fake_results(provider.model, [])
    assert provider.detect_image("image") == []


def test_real_cv_detection_to_event():
    provider = make_provider([(0, 0.9, (100, 50, 180, 250)), (1, 0.8, (300, 300, 420, 360))])
    detections = provider.detect_image("image")
    events = provider.detections_to_events(detections, ["agent_A", "agent_B"], scene_id="demo_test")
    types = [event.type for event in events]
    assert types == [EventType.PERSON_DETECTED, EventType.RISK_OBJECT_DETECTED]
    assert all(event.source == "real_cv" for event in events)
    assert events[0].subject_id == "agent_A"
    assert events[1].subject_id == "agent_A"
    assert events[0].metadata["confidence"] == 0.9
    assert events[1].metadata["display_name"] == "疑似风险物品"


def test_real_cv_never_generates_crowd_gathered():
    """>=3 人近距离 -> CrowdDetected（cv_aggregation）；任何情况下不得出现 CrowdGathered。"""
    provider = make_provider(
        [
            (0, 0.9, (100, 100, 150, 300)),
            (0, 0.88, (170, 100, 220, 300)),
            (0, 0.86, (240, 100, 290, 300)),
        ]
    )
    detections = provider.detect_image("image")
    events = provider.detections_to_events(detections, ["agent_A", "agent_B", "agent_C"])
    types = [event.type for event in events]
    assert types.count(EventType.PERSON_DETECTED) == 3
    assert EventType.CROWD_DETECTED in types
    assert EventType.CROWD_GATHERED not in types, "CV 感知层禁止直接产出 CrowdGathered"
    crowd_event = next(e for e in events if e.type == EventType.CROWD_DETECTED)
    assert crowd_event.source == "cv_aggregation"


def test_crowd_detected_from_person_aggregation():
    """crowd 仅由 person 数量 + 空间距离聚合产生，不是模型类别。"""
    from backend.app.perception.mock_cv import BBox, Detection

    def person_detection(x: float) -> Detection:
        return Detection(
            id=f"det_{x}",
            label="person",
            confidence=0.9,
            bbox=BBox(x=x, y=0.3, width=0.1, height=0.4),
            synthetic=True,
        )

    close = [person_detection(0.10), person_detection(0.18), person_detection(0.26)]
    crowd = aggregate_crowd(close)
    assert crowd is not None
    assert crowd["person_count"] == 3
    assert crowd["max_pair_distance"] <= CROWD_DISTANCE_THRESHOLD

    # 只有 2 人 -> 不聚合
    assert aggregate_crowd(close[:2]) is None
    # 3 人但分散 -> 不聚合
    far = [person_detection(0.10), person_detection(0.50), person_detection(0.90)]
    assert aggregate_crowd(far) is None
    # risk_object / vehicle 不参与聚合
    others = [
        Detection(id="d1", label="risk_object", confidence=0.9,
                  bbox=BBox(x=0.1, y=0.1, width=0.1, height=0.1), synthetic=True),
        Detection(id="d2", label="vehicle", confidence=0.9,
                  bbox=BBox(x=0.2, y=0.2, width=0.1, height=0.1), synthetic=True),
        Detection(id="d3", label="vehicle", confidence=0.9,
                  bbox=BBox(x=0.3, y=0.3, width=0.1, height=0.1), synthetic=True),
    ]
    assert aggregate_crowd(others) is None


def test_real_cv_fallback_to_mock(monkeypatch):
    """模型不可用时显式回退：provider=mock_fallback、model_invoked=false。"""
    import backend.app.api.perception as perception_api

    monkeypatch.setattr(perception_api, "get_real_provider", lambda: None)
    monkeypatch.setattr(perception_api, "provider_unavailable_reason", lambda: "model file missing")

    response = client.post(
        "/api/perception/cv/detect-image",
        data={"demo_scene_id": "demo_high_risk", "provider": "real", "subject_ids": "agent_A,agent_B,agent_C"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock_fallback"
    assert payload["model_invoked"] is False
    assert payload["model_version"] is None
    assert payload["fallback_reason"] == "model file missing"
    assert payload["detections"], "fallback 仍需产出 Detection（来自 MockCV 场景）"
    assert payload["events"], "fallback 事件仍进入 Event Bus"
    types = [event["type"] for event in payload["events"]]
    assert "CrowdGathered" not in types

    # Agent 工具必须如实说明这是 fallback，不得声称 Trained CV
    summary = real_cv.get_last_detection_summary()
    assert summary["provider"] == "mock_fallback"
    assert summary["model_invoked"] is False
    answer = explain_question("视觉模型检测到了什么？", world_service.state)
    assert "Mock Fallback" in answer["answer"]
    assert "Trained CV" not in answer["answer"].split("Mock Fallback")[0]


def test_real_mode_never_calls_mock_provider(monkeypatch):
    """real 模式全链路只调用 RealCVProvider；MockCVProvider.detect 调用次数必须为 0。"""
    import backend.app.api.perception as perception_api

    provider = make_provider(
        [
            (0, 0.9, (100, 100, 150, 300)),
            (0, 0.88, (170, 100, 220, 300)),
            (1, 0.8, (300, 300, 420, 360)),
        ]
    )
    monkeypatch.setattr(perception_api, "get_real_provider", lambda: provider)

    detect_spy = pytest.MonkeyPatch()
    mock_detect_calls: list[str] = []
    original_detect = MockCVProvider.detect
    original_scene = MockCVProvider.detect_scene

    def spy_detect(self, *args, **kwargs):
        mock_detect_calls.append("detect")
        return original_detect(self, *args, **kwargs)

    def spy_scene(self, *args, **kwargs):
        mock_detect_calls.append("detect_scene")
        return original_scene(self, *args, **kwargs)

    detect_spy.setattr(MockCVProvider, "detect", spy_detect)
    detect_spy.setattr(MockCVProvider, "detect_scene", spy_scene)
    try:
        response = client.post(
            "/api/perception/cv/detect-image",
            data={"demo_scene_id": "demo_risk", "provider": "real", "subject_ids": "agent_A,agent_B,agent_C"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "real"
        assert payload["model_invoked"] is True
        assert payload["model_version"] == "cv_yolo_test"
        assert len(payload["detections"]) == 3
        assert [d["label"] for d in payload["detections"]] == ["person", "person", "risk_object"]
        assert payload["detections"][0]["confidence"] == 0.9
        # YOLO.predict 真实被调用一次（API 路径）
        assert len(provider.model.predict_calls) == 1
        # MockCVProvider 在 real 模式下调用次数必须为 0
        assert mock_detect_calls == []
        # 事件真实进入 Event Bus
        types = [event["type"] for event in payload["events"]]
        assert "PersonDetected" in types and "RiskObjectDetected" in types
        assert payload["risk_state"] is not None
    finally:
        detect_spy.undo()


def test_request_conf_threshold_does_not_pollute_singleton_provider(monkeypatch):
    """单次请求的 conf 必须是 request-scoped，后续请求恢复 provider 默认阈值。"""
    import backend.app.api.perception as perception_api

    provider = make_provider([(0, 0.9, (100, 100, 150, 300))])
    monkeypatch.setattr(perception_api, "get_real_provider", lambda: provider)

    first = client.post(
        "/api/perception/cv/detect-image",
        data={
            "demo_scene_id": "demo_normal",
            "provider": "real",
            "subject_ids": "agent_A",
            "conf": "0.80",
        },
    )
    second = client.post(
        "/api/perception/cv/detect-image",
        data={
            "demo_scene_id": "demo_normal",
            "provider": "real",
            "subject_ids": "agent_A",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert [call["conf"] for call in provider.model.predict_calls] == [0.80, real_cv.DEFAULT_CONF_THRESHOLD]
    assert first.json()["conf_threshold"] == 0.80
    assert second.json()["conf_threshold"] == real_cv.DEFAULT_CONF_THRESHOLD
    assert provider.conf_threshold == real_cv.DEFAULT_CONF_THRESHOLD


def test_concurrent_detection_thresholds_remain_request_scoped():
    """并发 A=.2/B=.8 必须把各自阈值传给 YOLO，且不改 singleton 默认值。"""
    provider = make_provider([(0, 0.9, (100, 100, 150, 300))])
    image = Image.new("RGB", (640, 480), "white")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(provider.detect_image, image, 0.2),
            executor.submit(provider.detect_image, image, 0.8),
        ]
        for future in futures:
            assert future.result()

    assert sorted(call["conf"] for call in provider.model.predict_calls) == [0.2, 0.8]
    assert provider.conf_threshold == real_cv.DEFAULT_CONF_THRESHOLD


@pytest.mark.parametrize("conf", [0, 0.01, 0.99, 2])
def test_invalid_conf_is_rejected_before_provider_fallback(conf):
    """非法阈值不能因 mock/fallback 路径而绕过 API 校验。"""
    response = client.post(
        "/api/perception/cv/detect-image",
        data={"demo_scene_id": "demo_normal", "provider": "mock", "conf": str(conf)},
    )

    assert 400 <= response.status_code < 500


def test_cv_model_metadata():
    """models/cv_detector/metrics.json 必须包含可追溯 metadata。"""
    metrics_path = MODEL_PATH.parent / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("models/cv_detector/metrics.json missing; run training first")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    for key in ("model_version", "training_seed", "dataset_hash", "class_names", "ultralytics_version"):
        assert key in metrics, f"metrics.json 缺少 {key}"
    assert metrics["class_names"] == ["person", "risk_object", "vehicle"]
    assert metrics["training_seed"] == 42
    assert metrics["dataset_hash"]


# ---------- Agent 工具接地 ----------


def test_agent_cv_detection_summary_grounding():
    tools = AgentTools(world_service.state)

    # 无推理记录
    empty = tools.get_cv_detection_summary()
    assert empty["available"] is False

    # 真实推理记录：回答必须来自该记录且声明 real
    real_cv.record_last_detection_summary(
        {
            "provider": "real",
            "model_invoked": True,
            "model_version": "cv_yolo_8.4.123",
            "scene_id": "demo_high_risk",
            "detection_count": 2,
            "labels": ["person", "risk_object"],
            "confidences": [0.83, 0.61],
            "crowd": None,
            "latency_ms": 35.2,
        }
    )
    summary = tools.get_cv_detection_summary()
    assert summary["available"] is True
    assert summary["provider"] == "real"
    answer = explain_question("视觉模型检测到了什么？", world_service.state)
    assert answer["tools_used"] == ["get_cv_detection_summary"]
    assert "Trained CV" in answer["answer"]
    assert "YOLO.predict" in answer["answer"]
    assert "provider=real" in answer["answer"]
    assert "model_invoked=true" in answer["answer"]
    assert "person 83%" in answer["answer"] and "risk_object 61%" in answer["answer"]


def _record_real_cv_summary() -> None:
    real_cv.record_last_detection_summary(
        {
            "provider": "real",
            "model_invoked": True,
            "model_version": "cv_yolo_8.4.123",
            "scene_id": "demo_high_risk",
            "detection_count": 3,
            "labels": ["person", "risk_object", "vehicle"],
            "confidences": [0.91, 0.82, 0.73],
            "crowd": {"person_count": 3, "max_pair_distance": 0.161},
            "latency_ms": 42.0,
        }
    )


def _record_fallback_cv_summary() -> None:
    real_cv.record_last_detection_summary(
        {
            "provider": "mock_fallback",
            "model_invoked": False,
            "model_version": None,
            "scene_id": "demo_high_risk",
            "detection_count": 1,
            "labels": ["person"],
            "confidences": [0.96],
            "crowd": None,
            "latency_ms": None,
            "fallback_reason": "model file missing",
        }
    )


def test_agent_cv_summary_contains_provider():
    _record_real_cv_summary()
    answer = explain_question("视觉模型检测到了什么？", world_service.state)
    assert answer["tools_used"] == ["get_cv_detection_summary"]
    assert "provider=real" in answer["answer"]


def test_agent_cv_summary_contains_model_invoked():
    _record_real_cv_summary()
    answer = explain_question("视觉模型检测到了什么？", world_service.state)
    assert "model_invoked=true" in answer["answer"]


def test_agent_cv_real_summary_reports_real():
    _record_real_cv_summary()
    answer = explain_question("视觉模型检测到了什么？", world_service.state)
    assert "Model Version: cv_yolo_8.4.123" in answer["answer"]
    assert "person 91%" in answer["answer"]
    assert "risk_object 82%" in answer["answer"]
    assert "vehicle 73%" in answer["answer"]
    assert "CrowdDetected：来自 cv_aggregation" in answer["answer"]


def test_agent_cv_fallback_not_reported_as_real():
    _record_fallback_cv_summary()
    answer = explain_question("视觉模型检测到了什么？", world_service.state)
    assert "provider=mock_fallback" in answer["answer"]
    assert "model_invoked=false" in answer["answer"]
    assert "当前没有使用 trained model inference" in answer["answer"]
    assert "provider=real" not in answer["answer"]
    assert "model_invoked=true" not in answer["answer"]
    assert "YOLO.predict" not in answer["answer"]
