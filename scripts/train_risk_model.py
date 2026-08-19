"""训练 Risk Forecast Model（HistGradientBoostingRegressor，5/10/30 分钟三个 horizon）。

只用 train + validation 选参；禁止读取 test.parquet。
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from training_utils import DEFAULT_DATA_DIR, DEFAULT_MODEL_DIR, feature_matrix, load_split

RISK_HORIZONS = (5, 10, 30)
MODEL_VERSION = "risk_hgb_v1"
PARAM_GRID = [
    {"learning_rate": 0.06, "max_iter": 300},
    {"learning_rate": 0.1, "max_iter": 300},
    {"learning_rate": 0.1, "max_iter": 600},
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train risk forecast model on synthetic episodes")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--model-dir", type=str, default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--max-train", type=int, default=0, help="仅使用前 N 条训练数据（调试用；0=全部）")
    args = parser.parse_args()
    data_dir, model_dir = Path(args.data_dir), Path(args.model_dir)

    train = load_split(data_dir, "train")
    validation = load_split(data_dir, "validation")
    x_train = feature_matrix(train)
    x_val = feature_matrix(validation)
    if args.max_train:
        x_train, limit = x_train[: args.max_train], slice(0, args.max_train)
    else:
        limit = slice(None)

    models: dict[str, HistGradientBoostingRegressor] = {}
    val_metrics: dict[str, dict[str, object]] = {}
    started = time.perf_counter()
    for horizon in RISK_HORIZONS:
        y_train = np.asarray(train[f"risk_{horizon}m"])[limit]
        y_val = np.asarray(validation[f"risk_{horizon}m"])
        best_model, best_mae = None, float("inf")
        best_params: dict[str, object] = {}
        for params in PARAM_GRID:
            candidate = HistGradientBoostingRegressor(random_state=42, early_stopping=True, **params)
            candidate.fit(x_train, y_train)
            mae = mean_absolute_error(y_val, candidate.predict(x_val))
            if mae < best_mae:
                best_model, best_mae, best_params = candidate, mae, params
        models[f"{horizon}m"] = best_model
        val_metrics[f"{horizon}m"] = {"validation_mae": round(float(best_mae), 4), "params": best_params}
        print(f"risk_{horizon}m: validation MAE={best_mae:.4f} params={best_params}")

    duration = time.perf_counter() - started
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "models": models,
        "horizons": list(RISK_HORIZONS),
        "model_version": MODEL_VERSION,
        "training_seconds": round(duration, 2),
        "train_rows": int(x_train.shape[0]),
        "validation_rows": int(x_val.shape[0]),
        "validation_metrics": val_metrics,
    }
    output = model_dir / "risk_forecast.joblib"
    joblib.dump(artifact, output)
    (model_dir / "risk_training_meta.json").write_text(
        json.dumps({"training_seconds": round(duration, 2), "train_rows": int(x_train.shape[0]), "validation_metrics": val_metrics}, indent=2),
        encoding="utf-8",
    )
    print(f"已保存 {output}（训练 {duration:.1f}s，train={x_train.shape[0]}, val={x_val.shape[0]}）")


if __name__ == "__main__":
    main()
