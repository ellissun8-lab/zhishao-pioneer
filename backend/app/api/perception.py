"""Perception API：Mock CV 场景识别 + Trained CV 真实 YOLO 推理。

POST /api/perception/cv/detect-image
    输入：image upload 或 demo_scene_id（generator 生成的独立 demo 图）
    链路：image -> RealCVProvider.detect_image -> YOLO.predict -> Detection[] -> Event[]
    响应：provider=real / model_invoked=true 只在真实推理成功后出现；
          模型缺失/加载失败/provider=mock 时 provider=mock_fallback、model_invoked=false。

GET /api/perception/cv/status
    模型可用性与最近一次推理摘要（UI REAL MODEL / MOCK FALLBACK 徽标数据源）。
"""

from __future__ import annotations

import io
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field

from ..perception import real_cv
from ..perception.mock_cv import DEFAULT_SCENE_SUBJECTS, MockCVProvider
from ..perception.real_cv import (
    DEFAULT_CONF_THRESHOLD,
    DEMO_DIR,
    MODEL_PATH,
    RealCVProvider,
    aggregate_crowd,
    get_real_provider,
    model_version_from_metrics,
    provider_unavailable_reason,
)
from ..service import world_service

router = APIRouter(prefix="/perception", tags=["perception"])

MODEL_RELATIVE_PATH = "models/cv_detector/best.pt"
DEMO_TO_MOCK_SCENE = {
    "demo_normal": "scene_normal",
    "demo_crowd": "scene_crowd",
    "demo_risk": "scene_risk_object",
    "demo_high_risk": "scene_high_risk",
}
FALLBACK_NOTE = "trained model unavailable; explicit mock fallback (model_invoked=false)"


def _provider_preference() -> str:
    return os.environ.get("CV_PROVIDER", "mock").strip().lower() or "mock"


class DetectionRequest(BaseModel):
    detection: str
    subject_id: str | None = "agent_A"


@router.post("/mock")
def mock_detection(request: DetectionRequest):
    try:
        event = MockCVProvider().detect(request.detection, request.subject_id)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    state = world_service.publish(event)
    return {"event": event, "risk_state": state.risk_state}


class SceneDetectRequest(BaseModel):
    scene_id: str
    subject_ids: list[str] = Field(default_factory=lambda: list(DEFAULT_SCENE_SUBJECTS))


@router.post("/mock-cv/detect")
def mock_cv_scene_detect(request: SceneDetectRequest):
    """CV 场景识别：Detection -> Standard Event -> Event Bus -> World State / Risk Engine。"""
    try:
        result = MockCVProvider().detect_scene(request.scene_id, request.subject_ids)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    missing = [subject for subject in set(request.subject_ids) if subject not in world_service.state.agents]
    if missing:
        raise HTTPException(400, f"Unknown subject ids: {missing}")
    for event in result["events"]:
        world_service.publish(event)
    return {
        "scene_id": result["scene_id"],
        "synthetic": True,
        "detections": result["detections"],
        "events": result["events"],
        "risk_state": world_service.state.risk_state,
    }


@router.get("/cv/status")
def cv_status() -> dict[str, object]:
    """Trained CV 状态：UI 徽标（REAL MODEL / MOCK FALLBACK）与 Agent 工具的数据源。"""
    provider = get_real_provider()
    return {
        "provider_preference": _provider_preference(),
        "model_available": RealCVProvider.model_available(),
        "model_loaded": provider is not None,
        "model_path": MODEL_RELATIVE_PATH,
        "model_version": provider.model_version if provider else model_version_from_metrics(),
        "class_names": ["person", "risk_object", "vehicle"],
        "conf_threshold": provider.conf_threshold if provider else DEFAULT_CONF_THRESHOLD,
        "unavailable_reason": None if provider else (provider_unavailable_reason() or "model file missing"),
        "last_inference": real_cv.get_last_detection_summary(),
    }


@router.get("/cv/demo-image/{scene_id}")
def cv_demo_image(scene_id: str) -> FileResponse:
    """提供 generator 生成的独立 demo 合成图（Trained CV 模式展示用）。"""
    if scene_id not in DEMO_TO_MOCK_SCENE:
        raise HTTPException(404, f"Unknown demo scene: {scene_id}")
    path = DEMO_DIR / f"{scene_id}.jpg"
    if not path.exists():
        raise HTTPException(404, f"demo image missing: {path}（先运行 python scripts/generate_cv_dataset.py --demo）")
    return FileResponse(path, media_type="image/jpeg", filename=f"{scene_id}.jpg")


def _resolve_demo_image(demo_scene_id: str) -> bytes:
    if demo_scene_id not in DEMO_TO_MOCK_SCENE:
        raise HTTPException(400, f"Unknown demo scene: {demo_scene_id}")
    path = DEMO_DIR / f"{demo_scene_id}.jpg"
    if not path.exists():
        raise HTTPException(400, f"demo image missing: {path}（先运行 python scripts/generate_cv_dataset.py --demo）")
    return path.read_bytes()


def _fallback_response(demo_scene_id: str | None, subject_ids: list[str], reason: str) -> dict[str, object]:
    """显式 mock fallback：绝不伪装成 real；model_invoked 恒为 false。"""
    scene_id = DEMO_TO_MOCK_SCENE.get(demo_scene_id or "", "scene_high_risk")
    result = MockCVProvider().detect_scene(scene_id, subject_ids)
    for event in result["events"]:
        world_service.publish(event)
    real_cv.record_last_detection_summary(
        {
            "provider": "mock_fallback",
            "model_invoked": False,
            "model_version": None,
            "scene_id": demo_scene_id,
            "detection_count": len(result["detections"]),
            "labels": [d.label for d in result["detections"]],
            "confidences": [d.confidence for d in result["detections"]],
            "crowd": None,
            "latency_ms": None,
            "fallback_reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {
        "provider": "mock_fallback",
        "model_invoked": False,
        "model_path": MODEL_RELATIVE_PATH,
        "model_version": None,
        "synthetic_visual_data": True,
        "fallback_reason": reason,
        "scene_id": demo_scene_id,
        "detections": result["detections"],
        "events": result["events"],
        "crowd": None,
        "risk_state": world_service.state.risk_state,
        "note": FALLBACK_NOTE,
    }


@router.post("/cv/detect-image")
async def cv_detect_image(
    file: UploadFile | None = File(default=None),
    demo_scene_id: str | None = Form(default=None),
    provider: str | None = Form(default=None),
    subject_ids: str | None = Form(default=None),
    conf: float | None = Form(default=None),
) -> dict[str, object]:
    """Trained CV 推理：uploaded/generated image -> RealCVProvider -> YOLO.predict -> Detection/Event。"""
    requested = (provider or _provider_preference()).strip().lower()
    subjects = [item.strip() for item in (subject_ids or "").split(",") if item.strip()] or list(DEFAULT_SCENE_SUBJECTS)
    missing = [subject for subject in set(subjects) if subject not in world_service.state.agents]
    if missing:
        raise HTTPException(400, f"Unknown subject ids: {missing}")

    if requested == "mock":
        return _fallback_response(demo_scene_id, subjects, "provider=mock requested (CV_PROVIDER/override)")

    if file is not None:
        image_bytes = await file.read()
        scene_label = file.filename or "upload"
    elif demo_scene_id:
        image_bytes = _resolve_demo_image(demo_scene_id)
        scene_label = demo_scene_id
    else:
        raise HTTPException(400, "provide either an image upload or demo_scene_id")

    model_provider = get_real_provider()
    if model_provider is None:
        return _fallback_response(demo_scene_id, subjects, provider_unavailable_reason() or "model file missing")

    if conf is not None:
        if not 0.05 <= conf <= 0.95:
            raise HTTPException(400, "conf must be within [0.05, 0.95]")
        model_provider.conf_threshold = conf

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as error:  # noqa: BLE001
        raise HTTPException(400, f"invalid image: {error}") from error

    started = time.perf_counter()
    # YOLO 推理放线程池，避免阻塞事件循环
    detections = await run_in_threadpool(model_provider.detect_image, image)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    events = model_provider.detections_to_events(detections, subjects, scene_id=scene_label)
    for event in events:
        world_service.publish(event)
    crowd = aggregate_crowd(detections)

    real_cv.record_last_detection_summary(
        {
            "provider": "real",
            "model_invoked": True,
            "model_version": model_provider.model_version,
            "scene_id": scene_label,
            "detection_count": len(detections),
            "labels": [d.label for d in detections],
            "confidences": [d.confidence for d in detections],
            "crowd": crowd,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {
        "provider": "real",
        "model_invoked": True,
        "model_path": MODEL_RELATIVE_PATH,
        "model_version": model_provider.model_version,
        "synthetic_visual_data": True,
        "scene_id": demo_scene_id,
        "conf_threshold": model_provider.conf_threshold,
        "latency_ms": latency_ms,
        "detections": detections,
        "events": events,
        "crowd": crowd,
        "risk_state": world_service.state.risk_state,
    }
