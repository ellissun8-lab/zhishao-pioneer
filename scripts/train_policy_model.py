"""训练 Intervention Policy Model（HistGradientBoostingClassifier，四分类）。

只用 train + validation 选参；禁止读取 test.parquet。
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score

from training_utils import DEFAULT_DATA_DIR, DEFAULT_MODEL_DIR, STRATEGY_ORDER, feature_matrix, load_split

MODEL_VERSION = "policy_hgb_v1"
PARAM_GRID = [
    {"learning_rate": 0.06, "max_iter": 300},
    {"learning_rate": 0.1, "max_iter": 300},
    {"learning_rate": 0.1, "max_iter": 600},
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train intervention policy model on synthetic episodes")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--model-dir", type=str, default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--max-train", type=int, default=0, help="仅使用前 N 条训练数据（调试用；0=全部）")
    args = parser.parse_args()
    data_dir, model_dir = Path(args.data_dir), Path(args.model_dir)

    train = load_split(data_dir, "train")
    validation = load_split(data_dir, "validation")
    x_train = feature_matrix(train)
    x_val = feature_matrix(validation)
    y_train = np.asarray(train["best_strategy"]).astype(str)
    y_val = np.asarray(validation["best_strategy"]).astype(str)
    if args.max_train:
        x_train, y_train = x_train[: args.max_train], y_train[: args.max_train]

    best_model, best_f1, best_params = None, -1.0, {}
    started = time.perf_counter()
    for params in PARAM_GRID:
        candidate = HistGradientBoostingClassifier(random_state=42, **params)
        candidate.fit(x_train, y_train)
        macro_f1 = f1_score(y_val, candidate.predict(x_val), labels=STRATEGY_ORDER, average="macro", zero_division=0)
        print(f"params={params} validation macro-F1={macro_f1:.4f}")
        if macro_f1 > best_f1:
            best_model, best_f1, best_params = candidate, macro_f1, params

    duration = time.perf_counter() - started
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": best_model,
        "classes": list(best_model.classes_),
        "model_version": MODEL_VERSION,
        "training_seconds": round(duration, 2),
        "train_rows": int(x_train.shape[0]),
        "validation_rows": int(x_val.shape[0]),
        "validation_macro_f1": round(float(best_f1), 4),
    }
    output = model_dir / "intervention_policy.joblib"
    joblib.dump(artifact, output)
    (model_dir / "policy_training_meta.json").write_text(
        json.dumps({"training_seconds": round(duration, 2), "train_rows": int(x_train.shape[0]), "validation_macro_f1": round(float(best_f1), 4), "params": best_params}, indent=2),
        encoding="utf-8",
    )
    print(f"已保存 {output}（训练 {duration:.1f}s，validation macro-F1={best_f1:.4f}）")


if __name__ == "__main__":
    main()
