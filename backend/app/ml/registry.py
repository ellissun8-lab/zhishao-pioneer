"""训练模型注册中心：加载 joblib 模型并暴露推理接口。

模型文件缺失时系统不崩溃，调用方回退 Rule-based Prediction
与 compare_strategies()。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

import numpy as np

from .features import FEATURE_SCHEMA

MODEL_DIR_ENV = "ZHISHAO_MODEL_DIR"
RISK_ARTIFACT = "risk_forecast.joblib"
POLICY_ARTIFACT = "intervention_policy.joblib"
METRICS_FILE = "metrics.json"
FALLBACK_NOTE = "ML model unavailable, using transparent rule-based fallback."

_lock = Lock()
_cache: dict[str, object] = {}


def model_dir() -> Path:
    override = os.getenv(MODEL_DIR_ENV)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "models"


def reset_cache() -> None:
    """测试用：清空模型缓存（配合 ZHISHAO_MODEL_DIR 切换目录）。"""
    with _lock:
        _cache.clear()


def _artifact(filename: str) -> object | None:
    with _lock:
        if filename in _cache:
            return _cache[filename]
        path = model_dir() / filename
        artifact = None
        if path.exists():
            try:
                import joblib

                artifact = joblib.load(path)
            except Exception:
                artifact = None
        _cache[filename] = artifact
        return artifact


def risk_model_available() -> bool:
    return _artifact(RISK_ARTIFACT) is not None


def policy_model_available() -> bool:
    return _artifact(POLICY_ARTIFACT) is not None


def get_metrics() -> dict[str, object]:
    path = model_dir() / METRICS_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _feature_vector(features: dict[str, float]) -> np.ndarray:
    missing = [name for name in FEATURE_SCHEMA if name not in features]
    if missing:
        raise KeyError(f"feature values missing: {missing}")
    return np.array([[float(features[name]) for name in FEATURE_SCHEMA]])


def predict_risk(features: dict[str, float], horizon_minutes: int = 10) -> dict[str, object]:
    """World State 特征 -> 训练模型风险预测（[0,100] 边界内）。"""
    artifact = _artifact(RISK_ARTIFACT)
    if artifact is None:
        raise RuntimeError(FALLBACK_NOTE)
    key = f"{horizon_minutes}m"
    model = artifact["models"].get(key)
    if model is None:
        raise ValueError(f"horizon {horizon_minutes}m 不在训练范围内: {list(artifact['models'])}")
    raw = float(model.predict(_feature_vector(features))[0])
    return {
        "model": "risk_forecast",
        "model_version": artifact["model_version"],
        "horizon_minutes": horizon_minutes,
        "prediction": round(min(100.0, max(0.0, raw)), 1),
        "input_features": {name: float(features[name]) for name in FEATURE_SCHEMA},
        "synthetic_training": True,
    }


def recommend_strategy(features: dict[str, float]) -> dict[str, object]:
    """World State 特征 -> 训练策略模型推荐（含概率）。"""
    artifact = _artifact(POLICY_ARTIFACT)
    if artifact is None:
        raise RuntimeError(FALLBACK_NOTE)
    model = artifact["model"]
    probabilities = model.predict_proba(_feature_vector(features))[0]
    classes = [str(value) for value in model.classes_]
    best_index = int(np.argmax(probabilities))
    return {
        "model": "intervention_policy",
        "model_version": artifact["model_version"],
        "strategy": classes[best_index],
        "probabilities": {label: round(float(probability), 4) for label, probability in zip(classes, probabilities)},
        "confidence": round(float(probabilities[best_index]), 4),
        "input_features": {name: float(features[name]) for name in FEATURE_SCHEMA},
        "synthetic_training": True,
    }


def status() -> dict[str, object]:
    metrics = get_metrics()
    risk_available = risk_model_available()
    policy_available = policy_model_available()
    dataset = metrics.get("dataset", {})
    risk_test = metrics.get("risk_model", {}).get("test", {})
    policy_test = metrics.get("policy_model", {}).get("test", {})
    return {
        "risk_available": risk_available,
        "policy_available": policy_available,
        "fallback_note": None if risk_available and policy_available else FALLBACK_NOTE,
        "model_version": metrics.get("risk_model", {}).get("model_version"),
        "episodes": dataset.get("episodes", 0),
        "train_rows": dataset.get("train_rows", 0),
        "validation_rows": dataset.get("validation_rows", 0),
        "test_rows": dataset.get("test_rows", 0),
        "test_risk_mae_10m": risk_test.get("10m", {}).get("mae"),
        "test_policy_macro_f1": policy_test.get("macro_f1"),
        "synthetic_training": True,
    }
