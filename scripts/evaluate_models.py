"""在独立 test split 上评估 Risk / Policy 模型并与 baseline 对比。

禁止人工填写指标：全部数字由本脚本实际计算写盘。
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, mean_absolute_error, mean_squared_error, r2_score

from training_utils import DEFAULT_DATA_DIR, DEFAULT_MODEL_DIR, STRATEGY_ORDER, feature_matrix, load_split

RISK_HORIZONS = (5, 10, 30)
TIME_FACTOR = {5: 0.6, 10: 1.0, 30: 1.4}
HEURISTIC_DOC = "risk>=60 或 (risk_object 且 risk>=40) -> intervene；crowd 且 risk>=25 -> guide_leave；risk>=15 -> warn；否则 none"


def rule_predict(columns: dict[str, np.ndarray], horizon: int) -> np.ndarray:
    """Rule-based baseline：按 predict_world_state 的透明规则从特征重算预测。"""
    current = columns["current_risk"]
    crowd = np.maximum(columns["crowd_detected"], columns["crowd_gathered"])
    risk_object = columns["risk_object_detected"]
    drift = np.where(crowd > 0, 4, -2) + np.where(risk_object > 0, 3, 0)
    return np.clip(current + drift * TIME_FACTOR[horizon], 0, 100)


def heuristic_strategy(columns: dict[str, np.ndarray]) -> np.ndarray:
    risk = columns["current_risk"]
    crowd = np.maximum(columns["crowd_detected"], columns["crowd_gathered"]) > 0
    risk_object = columns["risk_object_detected"] > 0
    out = np.full(risk.shape, "none", dtype=object)
    out[risk >= 15] = "warn"
    out[crowd & (risk >= 25)] = "guide_leave"
    out[(risk >= 60) | (risk_object & (risk >= 40))] = "intervene"
    return out


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained models on the test split")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--model-dir", type=str, default=str(DEFAULT_MODEL_DIR))
    args = parser.parse_args()
    data_dir, model_dir = Path(args.data_dir), Path(args.model_dir)

    train = load_split(data_dir, "train")
    test = load_split(data_dir, "test")
    x_test = feature_matrix(test)
    risk_artifact = joblib.load(model_dir / "risk_forecast.joblib")
    policy_artifact = joblib.load(model_dir / "intervention_policy.joblib")

    # ---- Risk Forecast ----
    risk_test: dict[str, dict[str, float]] = {}
    mean_baseline: dict[str, dict[str, float]] = {}
    rule_baseline: dict[str, dict[str, float]] = {}
    for horizon in RISK_HORIZONS:
        y_true = np.asarray(test[f"risk_{horizon}m"], dtype=np.float64)
        y_pred = np.clip(risk_artifact["models"][f"{horizon}m"].predict(x_test), 0, 100)
        risk_test[f"{horizon}m"] = regression_metrics(y_true, y_pred)
        mean_baseline[f"{horizon}m"] = regression_metrics(y_true, np.full_like(y_true, float(np.mean(train[f"risk_{horizon}m"]))))
        rule_baseline[f"{horizon}m"] = regression_metrics(y_true, rule_predict(test, horizon))

    # ---- Policy ----
    y_true = np.asarray(test["best_strategy"]).astype(str)
    y_pred = policy_artifact["model"].predict(x_test)
    policy_test = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=STRATEGY_ORDER, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, y_pred, labels=STRATEGY_ORDER, average="weighted", zero_division=0)), 4),
        "confusion_matrix": {
            "labels": STRATEGY_ORDER,
            "matrix": confusion_matrix(y_true, y_pred, labels=STRATEGY_ORDER).tolist(),
        },
    }
    majority = str(np.unique(np.asarray(train["best_strategy"]).astype(str), return_counts=True)[0][np.argmax(np.unique(np.asarray(train["best_strategy"]).astype(str), return_counts=True)[1])])
    majority_acc = round(float(accuracy_score(y_true, np.full_like(y_true, majority, dtype=object))), 4)
    heuristic_pred = heuristic_strategy(test)
    heuristic_acc = round(float(accuracy_score(y_true, heuristic_pred)), 4)

    # ---- 性能 ----
    sample = x_test[:2000]
    risk_started = time.perf_counter()
    risk_artifact["models"]["10m"].predict(sample)
    risk_latency = (time.perf_counter() - risk_started) / len(sample) * 1000
    policy_started = time.perf_counter()
    policy_artifact["model"].predict(sample)
    policy_latency = (time.perf_counter() - policy_started) / len(sample) * 1000

    generation_stats_path = data_dir / "generation_stats.json"
    generation_stats = json.loads(generation_stats_path.read_text(encoding="utf-8")) if generation_stats_path.exists() else {}
    risk_meta_path = model_dir / "risk_training_meta.json"
    policy_meta_path = model_dir / "policy_training_meta.json"
    risk_meta = json.loads(risk_meta_path.read_text(encoding="utf-8")) if risk_meta_path.exists() else {}
    policy_meta = json.loads(policy_meta_path.read_text(encoding="utf-8")) if policy_meta_path.exists() else {}

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_training": True,
        "dataset": {
            "episodes": int(generation_stats.get("episodes", 0)),
            "seed": int(generation_stats.get("seed", 42)),
            "train_rows": int(train["episode_id"].size),
            "validation_rows": int(load_split(data_dir, "validation")["episode_id"].size),
            "test_rows": int(test["episode_id"].size),
            "generation_duration_seconds": generation_stats.get("generation_duration_seconds"),
        },
        "risk_model": {
            "model_version": risk_artifact["model_version"],
            "test": risk_test,
            "baselines": {"mean_predictor": mean_baseline, "rule_predictor": rule_baseline},
            "training_seconds": risk_meta.get("training_seconds"),
        },
        "policy_model": {
            "model_version": policy_artifact["model_version"],
            "test": policy_test,
            "baselines": {
                "majority_strategy": {"strategy": majority, "accuracy": majority_acc},
                "risk_threshold_heuristic": {"definition": HEURISTIC_DOC, "accuracy": heuristic_acc},
            },
            "training_seconds": policy_meta.get("training_seconds"),
        },
        "performance": {
            "risk_inference_latency_ms_per_record": round(risk_latency, 6),
            "policy_inference_latency_ms_per_record": round(policy_latency, 6),
            "artifact_sizes_bytes": {
                "risk_forecast.joblib": (model_dir / "risk_forecast.joblib").stat().st_size,
                "intervention_policy.joblib": (model_dir / "intervention_policy.joblib").stat().st_size,
            },
        },
    }
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    docs_dir = model_dir.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    confusion = policy_test["confusion_matrix"]["matrix"]
    confusion_rows = "\n".join(
        f"| {label} | {' | '.join(str(cell) for cell in row)} |" for label, row in zip(STRATEGY_ORDER, confusion)
    )
    report = f"""# Model Evaluation（全部指标来自独立 test split，禁止人工填写）

数据：{metrics['dataset']['episodes']:,} Synthetic Episodes（seed={metrics['dataset']['seed']}），
train {metrics['dataset']['train_rows']:,} / validation {metrics['dataset']['validation_rows']:,} / test {metrics['dataset']['test_rows']:,}，
按 episode_id 切分，无跨集泄漏。所有训练数据 100% Synthetic。

## Risk Forecast（{risk_artifact['model_version']}，test split）

| Horizon | MAE | RMSE | R2 | Baseline mean MAE | Baseline rule MAE |
|---|---|---|---|---|---|
""" + "\n".join(
        f"| {h}m | {risk_test[f'{h}m']['mae']} | {risk_test[f'{h}m']['rmse']} | {risk_test[f'{h}m']['r2']} | {mean_baseline[f'{h}m']['mae']} | {rule_baseline[f'{h}m']['mae']} |"
        for h in RISK_HORIZONS
    ) + f"""

- Baseline 1（mean predictor）：常数预测 train 均值。
- Baseline 2（rule predictor）：按 predict_world_state 透明规则从特征重算。

## Policy（{policy_artifact['model_version']}，test split）

- Accuracy: {policy_test['accuracy']}
- Macro F1: {policy_test['macro_f1']}
- Weighted F1: {policy_test['weighted_f1']}
- Baseline majority（{majority}）Accuracy: {majority_acc}
- Baseline heuristic Accuracy: {heuristic_acc}（{HEURISTIC_DOC}）

Confusion Matrix（行=真实，列=预测，顺序 none/warn/guide_leave/intervene）：

| 真实\\预测 | none | warn | guide_leave | intervene |
|---|---|---|---|---|
{confusion_rows}

## 性能

- 训练耗时：risk {metrics['risk_model']['training_seconds']}s / policy {metrics['policy_model']['training_seconds']}s
- 推理延迟：risk {metrics['performance']['risk_inference_latency_ms_per_record']} ms/条，policy {metrics['performance']['policy_inference_latency_ms_per_record']} ms/条
- 模型文件：risk {(metrics['performance']['artifact_sizes_bytes']['risk_forecast.joblib'] / 1024):.0f} KB，policy {(metrics['performance']['artifact_sizes_bytes']['intervention_policy.joblib'] / 1024):.0f} KB
- 数据生成耗时：{metrics['dataset']['generation_duration_seconds']}s

以上均为 Synthetic Data 训练结果，不代表真实城市预测。
"""
    (docs_dir / "model-evaluation.md").write_text(report, encoding="utf-8")
    print(json.dumps({"risk_10m": risk_test["10m"], "policy": {k: v for k, v in policy_test.items() if k != "confusion_matrix"}, "majority_acc": majority_acc, "heuristic_acc": heuristic_acc}, ensure_ascii=False, indent=2))
    print(f"已写入 {model_dir / 'metrics.json'} 与 {docs_dir / 'model-evaluation.md'}")


if __name__ == "__main__":
    main()
