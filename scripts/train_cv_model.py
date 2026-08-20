"""Ultralytics YOLO 训练脚本（Synthetic CV Dataset）。

用法：
    python scripts/train_cv_model.py --data data/cv_synthetic/data.yaml \
        --epochs 50 --imgsz 640 --batch 16 --seed 42

- 自动检测 CUDA：有 GPU -> device=0；无 GPU -> device=cpu（允许 --epochs 5 作为 smoke run）
- 训练只用 train + val split；test split 保留给 scripts/evaluate_cv_model.py 独立评估
- 产物：models/cv_detector/best.pt + models/cv_detector/metrics.json（含 ultralytics 版本、
  dataset hash、训练硬件与 seed，可复现）
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import torch
import ultralytics
from ultralytics import YOLO

MODEL_DIR = PROJECT_ROOT / "models" / "cv_detector"
PREFERRED_BASE = "yolo26n.pt"
FALLBACK_BASE = "yolo11n.pt"


def resolve_base_model(requested: str) -> str:
    """优先 yolo26n.pt；若环境不支持则回退到当前 ultralytics 可用的轻量 nano 检测模型。"""
    if requested != "auto":
        return requested
    try:
        YOLO(PREFERRED_BASE)
        return PREFERRED_BASE
    except Exception as error:  # noqa: BLE001 - 下载/加载失败统一回退
        print(f"[warn] {PREFERRED_BASE} unavailable ({error}); falling back to {FALLBACK_BASE}")
        return FALLBACK_BASE


def dataset_hash(data_yaml: Path) -> str | None:
    """从数据集目录读取 stats.json 的 dataset_hash（训练 metadata 必须可追溯）。"""
    stats_path = data_yaml.parent / "stats.json"
    if not stats_path.exists():
        return None
    return json.loads(stats_path.read_text(encoding="utf-8")).get("dataset_hash")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLO detector on synthetic CV dataset")
    parser.add_argument("--data", type=str, default="data/cv_synthetic/data.yaml")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", type=str, default="auto", help="base checkpoint (auto: yolo26n.pt -> yolo11n.pt)")
    parser.add_argument("--name", type=str, default="cv_train")
    parser.add_argument("--project", type=str, default="runs/cv")
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--device", type=str, default="auto", help="auto | 0 | cpu")
    parser.add_argument("--workers", type=int, default=4, help="dataloader workers（低内存机器建议 4）")
    args = parser.parse_args()

    data_yaml = (PROJECT_ROOT / args.data).resolve()
    if not data_yaml.exists():
        raise SystemExit(f"data yaml not found: {data_yaml}")

    if args.device == "auto":
        device = 0 if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    hardware = f"{torch.cuda.get_device_name(0)} (CUDA)" if device == 0 and torch.cuda.is_available() else "CPU"
    print(f"ultralytics {ultralytics.__version__} | torch {torch.__version__} | device: {device} ({hardware})")

    base = resolve_base_model(args.model)
    print(f"base model: {base}")
    model = YOLO(base)
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        seed=args.seed,
        device=device,
        patience=args.patience,
        workers=args.workers,
        project=str(PROJECT_ROOT / args.project),
        name=args.name,
        exist_ok=True,
        deterministic=True,
        verbose=True,
        # 训练/验证只使用 train+val split；test split 不参与训练与 early stop
    )

    run_dir = Path(results.save_dir)
    best = run_dir / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit(f"best.pt not produced: {best}")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, MODEL_DIR / "best.pt")

    # 训练期（val split）指标仅为过程参考；正式指标由 evaluate_cv_model.py 在 test split 独立计算
    metrics = {
        "model_version": f"cv_yolo_{ultralytics.__version__}",
        "base_model": base,
        "ultralytics_version": ultralytics.__version__,
        "torch_version": torch.__version__,
        "training_seed": args.seed,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "hardware": hardware,
        "dataset": str(data_yaml.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "dataset_hash": dataset_hash(data_yaml),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "class_names": ["person", "risk_object", "vehicle"],
        "val_metrics": {
            "mAP50": round(float(results.box.map50), 4),
            "mAP50-95": round(float(results.box.map), 4),
            "precision": round(float(results.box.mp), 4),
            "recall": round(float(results.box.mr), 4),
        },
        "note": "val_metrics 是训练期 val split 过程指标；正式 test/OOD 指标由 scripts/evaluate_cv_model.py 写入 test_metrics/ood_metrics",
    }
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics["val_metrics"], indent=2))
    print(f"model saved -> {MODEL_DIR / 'best.pt'}")


if __name__ == "__main__":
    main()
