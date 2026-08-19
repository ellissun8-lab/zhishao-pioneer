"""Synthetic Training Pipeline 共享工具：parquet 读取与特征矩阵构造。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pyarrow.parquet as pq

from backend.app.ml.features import FEATURE_SCHEMA

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models"
STRATEGY_ORDER = ["none", "warn", "guide_leave", "intervene"]


def load_split(data_dir: Path, split: str) -> dict[str, np.ndarray]:
    """读取一个 split 的 parquet，返回列名 -> ndarray；只构造 FEATURE_SCHEMA 矩阵。"""
    filenames = {"train": "train.parquet", "validation": "val.parquet", "test": "test.parquet"}
    table = pq.read_table(data_dir / filenames[split])
    return {column: table.column(column).to_numpy() for column in table.column_names}


def feature_matrix(columns: dict[str, np.ndarray]) -> np.ndarray:
    missing = [name for name in FEATURE_SCHEMA if name not in columns]
    if missing:
        raise KeyError(f"feature columns missing: {missing}")
    return np.column_stack([np.asarray(columns[name], dtype=np.float64) for name in FEATURE_SCHEMA])
