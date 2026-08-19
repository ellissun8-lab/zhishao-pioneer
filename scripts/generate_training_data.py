"""生成 Synthetic Training Episodes 并流式写入 parquet。

用法：
    python scripts/generate_training_data.py --episodes 120000 --seed 42

标签完全来自 World Behavior Model（predict_world_state）与
What-if Simulation（SimulationEngine），100% Synthetic Data。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyarrow as pa
import pyarrow.parquet as pq

from backend.app.ml.episodes import (
    DEFAULT_INTERVENTION_COST_WEIGHT,
    DEFAULT_SEED,
    DistributionStats,
    canonical_record_hash,
    iter_episode_records,
)
from backend.app.ml.features import FEATURE_SCHEMA

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "synthetic"
DEFAULT_BATCH_SIZE = 5000
RECORD_HASH_COUNT = 100

PARQUET_SCHEMA = pa.schema(
    [
        pa.field("episode_id", pa.int64(), nullable=False),
        pa.field("synthetic", pa.bool_(), nullable=False),
        pa.field("split", pa.string(), nullable=False),
        pa.field("archetype", pa.string(), nullable=False),
        pa.field("event_types", pa.string(), nullable=False),
        pa.field("dominant_behavior", pa.string(), nullable=False),
        *[pa.field(name, pa.float64(), nullable=False) for name in FEATURE_SCHEMA],
        *[pa.field(name, pa.float64(), nullable=False) for name in ("risk_5m", "risk_10m", "risk_30m")],
        *[pa.field(name, pa.float64(), nullable=False) for name in ("utility_none", "utility_warn", "utility_guide_leave", "utility_intervene")],
        pa.field("best_strategy", pa.string(), nullable=False),
    ]
)


def write_streaming(episodes: int, seed: int, weight: float, out_dir: Path, batch_size: int) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        name: out_dir / filename
        for name, filename in {
            "episodes": "episodes.parquet",
            "train": "train.parquet",
            "validation": "val.parquet",
            "test": "test.parquet",
        }.items()
    }
    writers = {name: pq.ParquetWriter(path, PARQUET_SCHEMA) for name, path in paths.items()}
    buffers: dict[str, list[dict[str, object]]] = {name: [] for name in writers}
    stats = DistributionStats()
    head_records: list[dict[str, object]] = []
    started = time.perf_counter()

    def flush(name: str) -> None:
        if buffers[name]:
            writers[name].write_table(pa.Table.from_pylist(buffers[name], schema=PARQUET_SCHEMA))
            buffers[name].clear()

    try:
        for record in iter_episode_records(episodes, seed, weight):
            stats.update(record)
            if len(head_records) < RECORD_HASH_COUNT:
                head_records.append(record)
            buffers[record["split"]].append(record)
            buffers["episodes"].append(record)
            if len(buffers["episodes"]) >= batch_size:
                for name in writers:
                    flush(name)
    finally:
        for name in writers:
            flush(name)
            writers[name].close()

    duration = time.perf_counter() - started
    return {
        "duration_seconds": round(duration, 2),
        "rows_per_second": round(episodes / duration, 1),
        "paths": {name: str(path) for name, path in paths.items()},
        "file_sizes_bytes": {name: path.stat().st_size for name, path in paths.items()},
        "distribution": stats.to_dict(),
        "first_records_sha256": canonical_record_hash(head_records),
    }


def write_dataset_card(out_dir: Path, episodes: int, seed: int, weight: float, result: dict[str, object]) -> None:
    distribution = result["distribution"]
    split_counts = {
        name: pq.ParquetFile(path).metadata.num_rows
        for name, path in [("train", out_dir / "train.parquet"), ("validation", out_dir / "val.parquet"), ("test", out_dir / "test.parquet")]
    }
    card = f"""# Synthetic Training Dataset Card

## Dataset Size
{episodes:,} Synthetic Episodes（100% Synthetic Data）

## Generated from
- World Behavior Model（backend/app/behavior/prediction.py::predict_world_state）
- Event Simulation（backend/app/simulation/engine.py::SimulationEngine）
- What-if Intervention Engine（四策略 What-if 对比 + utility 标签）

## Not
- real Guangzhou residents
- real surveillance footage
- real police data
- real personal trajectories

所有 Episode 均为参数化采样的模拟世界状态，不含任何真实个人数据。

## Reproducibility
- seed: {seed}
- episodes: {episodes:,}
- intervention_cost_weight: {weight}
- 首批 {RECORD_HASH_COUNT} 条记录 sha256: `{result["first_records_sha256"]}`
- 同参数重跑生成一致的统计与标签

## Feature Schema
{", ".join(FEATURE_SCHEMA)}

禁止把 agent id / display_name / episode id / event id 作为训练特征。

## Label Generation
- risk_5m / risk_10m / risk_30m：来自 predict_world_state(state, horizon)
- best_strategy：对同一 World State 运行 run_simulation(NONE/WARN/GUIDE_LEAVE/INTERVENE)，
  utility = risk_reduction - intervention_cost_weight * action_cost，取 utility 最大者
- 不得随机生成标签

## Train/Val/Test Split（按 episode_id 切分，禁止同 episode 跨集）
- train: {split_counts["train"]:,}
- validation: {split_counts["validation"]:,}
- test: {split_counts["test"]:,}

## Distribution Summary
- strategy label distribution: {json.dumps(distribution["strategy_label_distribution"], ensure_ascii=False)}
- risk score distribution: {json.dumps(distribution["risk_score_distribution"], ensure_ascii=False)}
- zone active ratio: {distribution["zone_active_ratio"]}
- risk object ratio: {distribution["risk_object_ratio"]}
- crowd ratio: {distribution["crowd_ratio"]}
"""
    (out_dir / "dataset_card.md").write_text(card, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic training episodes")
    parser.add_argument("--episodes", type=int, default=120000)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--intervention-cost-weight", type=float, default=DEFAULT_INTERVENTION_COST_WEIGHT)
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()
    if args.episodes < 1:
        raise SystemExit("--episodes 必须为正整数")

    out_dir = Path(args.out_dir)
    print(f"生成 {args.episodes:,} episodes（seed={args.seed}, weight={args.intervention_cost_weight}）-> {out_dir}")
    result = write_streaming(args.episodes, args.seed, args.intervention_cost_weight, out_dir, args.batch_size)

    try:
        import psutil

        peak_note = f" | peak RSS approx {psutil.Process().memory_info().rss / 1024 / 1024:.0f} MB"
    except Exception:
        peak_note = ""
    summary = {
        "episodes": args.episodes,
        "seed": args.seed,
        "intervention_cost_weight": args.intervention_cost_weight,
        "generation_duration_seconds": result["duration_seconds"],
        "rows_per_second": result["rows_per_second"],
        "first_records_sha256": result["first_records_sha256"],
        "file_sizes_bytes": result["file_sizes_bytes"],
        **result["distribution"],
    }
    (out_dir / "generation_stats.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_dataset_card(out_dir, args.episodes, args.seed, args.intervention_cost_weight, result)

    print(f"完成：{args.episodes:,} episodes / {result['duration_seconds']}s / {result['rows_per_second']:.0f} rows/s{peak_note}")
    print(f"first_records_sha256={result['first_records_sha256']}")
    for name, size in result["file_sizes_bytes"].items():
        print(f"{name}.parquet {size / 1024 / 1024:.1f} MB")
    print("策略标签分布:", json.dumps(result["distribution"]["strategy_label_distribution"], ensure_ascii=False))


if __name__ == "__main__":
    main()
