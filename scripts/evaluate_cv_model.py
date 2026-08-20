"""独立评估脚本：test split + OOD split + 推理延迟（绝不参与训练与 early stop）。

用法：
    python scripts/evaluate_cv_model.py \
        --model models/cv_detector/best.pt \
        --data data/cv_synthetic/data.yaml \
        --ood-data data/cv_synthetic_ood/data.yaml

输出写入 models/cv_detector/metrics.json 的 test_metrics / ood_metrics / inference 字段，
并生成混淆矩阵图与 per-class AP。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
import ultralytics
from ultralytics import YOLO

MODEL_DIR = PROJECT_ROOT / "models" / "cv_detector"
CLASS_NAMES = ["person", "risk_object", "vehicle"]


def _val_metrics(model: YOLO, data: Path, split: str, plots: bool, name: str) -> dict[str, object]:
    results = model.val(data=str(data), split=split, plots=plots, name=name, exist_ok=True, verbose=False, workers=4)
    per_class = {label: round(float(value), 4) for label, value in zip(results.names.values(), results.box.maps)}
    payload: dict[str, object] = {
        "mAP50-95": round(float(results.box.map), 4),
        "mAP50": round(float(results.box.map50), 4),
        "mAP75": round(float(results.box.map75), 4),
        "precision": round(float(results.box.mp), 4),
        "recall": round(float(results.box.mr), 4),
        "per_class_ap50-95": per_class,
    }
    confusion = getattr(results, "confusion_matrix", None)
    if confusion is not None and getattr(confusion, "matrix", None) is not None:
        matrix = np.asarray(confusion.matrix)
        payload["confusion_matrix"] = {
            "labels": list(results.names.values()) + ["background"],
            "matrix": [[round(float(v), 4) for v in row] for row in matrix],
        }
    return payload


def _inference_latency(model: YOLO, image_dir: Path, limit: int = 100) -> dict[str, object]:
    images = sorted(image_dir.glob("*.jpg"))[:limit]
    if not images:
        return {"ms_per_image": None, "sample_count": 0}
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    # warmup
    model.predict(source=str(images[0]), device=device, verbose=False)
    started = time.perf_counter()
    for image in images:
        model.predict(source=str(image), device=device, verbose=False)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "ms_per_image": round(elapsed_ms / len(images), 2),
        "sample_count": len(images),
        "device": device,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained CV detector on test / OOD splits")
    parser.add_argument("--model", type=str, default=str(MODEL_DIR / "best.pt"))
    parser.add_argument("--data", type=str, default="data/cv_synthetic/data.yaml")
    parser.add_argument("--ood-data", "--ood", dest="ood_data", type=str, default=None)
    parser.add_argument("--latency-dir", type=str, default="data/cv_synthetic/images/test")
    parser.add_argument("--latency-samples", type=int, default=100)
    args = parser.parse_args()

    model_path = (PROJECT_ROOT / args.model).resolve()
    if not model_path.exists():
        raise SystemExit(f"model not found: {model_path}（先运行 scripts/train_cv_model.py）")
    data_yaml = (PROJECT_ROOT / args.data).resolve()
    metrics_path = MODEL_DIR / "metrics.json"
    metrics: dict[str, object] = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}

    model = YOLO(str(model_path))
    print(f"evaluating {model_path.name} on test split of {data_yaml}")
    test_metrics = _val_metrics(model, data_yaml, split="test", plots=True, name="cv_eval_test")
    print(json.dumps({k: v for k, v in test_metrics.items() if k != "confusion_matrix"}, indent=2))

    ood_metrics = None
    if args.ood_data:
        ood_yaml = (PROJECT_ROOT / args.ood_data).resolve()
        if ood_yaml.exists():
            print(f"evaluating OOD split of {ood_yaml}")
            ood_metrics = _val_metrics(model, ood_yaml, split="val", plots=True, name="cv_eval_ood")
            print(json.dumps({k: v for k, v in ood_metrics.items() if k != "confusion_matrix"}, indent=2))

    latency = _inference_latency(model, (PROJECT_ROOT / args.latency_dir).resolve(), limit=args.latency_samples)
    size_mb = round(model_path.stat().st_size / (1024 * 1024), 2)

    metrics.update(
        {
            "model_file": str(model_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "model_size_mb": size_mb,
            "test_metrics": test_metrics,
            "ood_metrics": ood_metrics,
            "inference": latency,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "ultralytics_version": ultralytics.__version__,
        }
    )
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"metrics updated -> {metrics_path}")
    print(json.dumps({"test mAP50-95": test_metrics["mAP50-95"], "test mAP50": test_metrics["mAP50"], "ood mAP50-95": ood_metrics["mAP50-95"] if ood_metrics else None, "inference": latency}, indent=2))


if __name__ == "__main__":
    main()
