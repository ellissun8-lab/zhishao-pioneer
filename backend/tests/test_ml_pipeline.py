"""Synthetic Training Pipeline 测试。

覆盖：生成可复现、标签来自仿真、特征无身份泄漏、切分隔离、
预测边界、策略合法、Agent 工具接地（grounding）、无模型回退、全量 synthetic。
"""

from __future__ import annotations

import numpy as np
import pytest
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from backend.app.data.seed import create_demo_state
from backend.app.behavior.prediction import predict_world_state
from backend.app.llm.tools import AgentTools
from backend.app.ml import registry
from backend.app.ml.episodes import (
    ARCHETYPES,
    DEFAULT_INTERVENTION_COST_WEIGHT,
    DEFAULT_SEED,
    build_state,
    canonical_record_hash,
    compute_labels,
    iter_episode_records,
    split_plan,
)
from backend.app.ml.features import FEATURE_SCHEMA, FORBIDDEN_FEATURE_TOKENS, extract_features
from backend.app.simulation.engine import SimulationEngine
from backend.app.simulation.strategies import Strategy

VALID_STRATEGIES = {strategy.value for strategy in Strategy}


def _records(episodes: int, seed: int) -> list[dict[str, object]]:
    return list(iter_episode_records(episodes, seed=seed))


@pytest.fixture
def trained_models(tmp_path, monkeypatch):
    """训练极小模型到临时目录，供 registry / AgentTools 测试使用。"""
    records = _records(400, seed=7)
    matrix = np.array([[float(record[name]) for name in FEATURE_SCHEMA] for record in records])
    risk_models = {}
    for horizon in (5, 10, 30):
        model = HistGradientBoostingRegressor(max_iter=60, random_state=42)
        model.fit(matrix, np.array([float(record[f"risk_{horizon}m"]) for record in records]))
        risk_models[f"{horizon}m"] = model
    policy = HistGradientBoostingClassifier(max_iter=60, random_state=42)
    policy.fit(matrix, np.array([str(record["best_strategy"]) for record in records]))
    joblib.dump({"models": risk_models, "horizons": [5, 10, 30], "model_version": "risk_test_v1"}, tmp_path / "risk_forecast.joblib")
    joblib.dump({"model": policy, "classes": list(policy.classes_), "model_version": "policy_test_v1"}, tmp_path / "intervention_policy.joblib")
    (tmp_path / "metrics.json").write_text(
        '{"dataset": {"episodes": 400}, "risk_model": {"model_version": "risk_test_v1", "test": {"10m": {"mae": 0.1}}}, "policy_model": {"model_version": "policy_test_v1", "test": {"macro_f1": 0.9}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("ZHISHAO_MODEL_DIR", str(tmp_path))
    registry.reset_cache()
    yield tmp_path
    registry.reset_cache()


@pytest.fixture
def no_models(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHISHAO_MODEL_DIR", str(tmp_path / "empty"))
    registry.reset_cache()
    yield
    registry.reset_cache()


def test_episode_generation_reproducible():
    first = _records(40, seed=DEFAULT_SEED)
    second = _records(40, seed=DEFAULT_SEED)
    other_seed = _records(40, seed=DEFAULT_SEED + 1)
    assert canonical_record_hash(first) == canonical_record_hash(second)
    assert canonical_record_hash(first) != canonical_record_hash(other_seed)
    assert [record["episode_id"] for record in first] == list(range(40))


def test_episode_labels_from_simulation():
    """标签必须来自 predict_world_state + SimulationEngine，逐条重算比对。"""
    episodes = 30
    records = _records(episodes, seed=DEFAULT_SEED)
    rng = np.random.default_rng(DEFAULT_SEED)
    archetype_rng = np.random.default_rng(DEFAULT_SEED + 1)
    for record in records:
        archetype = ARCHETYPES[int(archetype_rng.integers(0, len(ARCHETYPES)))]
        state = build_state(rng, archetype)
        labels = compute_labels(state, DEFAULT_INTERVENTION_COST_WEIGHT)
        for horizon in (5, 10, 30):
            assert record[f"risk_{horizon}m"] == labels[f"risk_{horizon}m"]
        assert record["best_strategy"] == labels["best_strategy"]
        # 与 What-if 仿真直接对账：best_strategy 的 utility 必须并列最大
        utilities = {key: float(record[f"utility_{key}"]) for key in VALID_STRATEGIES}
        assert utilities[record["best_strategy"]] == max(utilities.values())


def test_no_identity_feature_leakage():
    lowered = [name.lower() for name in FEATURE_SCHEMA]
    for token in FORBIDDEN_FEATURE_TOKENS:
        assert all(token not in name for name in lowered), f"身份字段泄漏进特征: {token}"
    state = create_demo_state(10)
    features = extract_features(state)
    assert set(features) == set(FEATURE_SCHEMA)
    assert all(isinstance(value, float) for value in features.values())


def test_train_test_episode_isolation():
    episodes = 200
    splits = split_plan(episodes, seed=DEFAULT_SEED)
    assert list(split_plan(episodes, seed=DEFAULT_SEED)) == list(splits), "切分必须可复现"
    ids_by_split: dict[str, set[int]] = {"train": set(), "validation": set(), "test": set()}
    for episode_id, split in enumerate(splits):
        ids_by_split[split].add(episode_id)
    train, validation, test = ids_by_split["train"], ids_by_split["validation"], ids_by_split["test"]
    assert len(train) == 140 and len(validation) == 30 and len(test) == 30
    assert not train & validation and not train & test and not validation & test
    assert train | validation | test == set(range(episodes))
    records = _records(episodes, seed=DEFAULT_SEED)
    for record in records:
        assert record["split"] == splits[record["episode_id"]], "同一 episode 不得跨集"


def test_risk_model_prediction_bounds(trained_models):
    records = _records(20, seed=99)
    for record in records:
        features = {name: float(record[name]) for name in FEATURE_SCHEMA}
        for horizon in (5, 10, 30):
            result = registry.predict_risk(features, horizon)
            assert 0.0 <= result["prediction"] <= 100.0
            assert result["model_version"] == "risk_test_v1"
            assert result["synthetic_training"] is True
            assert set(result["input_features"]) == set(FEATURE_SCHEMA)


def test_policy_model_valid_strategy(trained_models):
    records = _records(20, seed=99)
    for record in records:
        features = {name: float(record[name]) for name in FEATURE_SCHEMA}
        result = registry.recommend_strategy(features)
        assert result["strategy"] in VALID_STRATEGIES
        assert abs(sum(result["probabilities"].values()) - 1.0) < 0.005  # 概率各自保留 4 位小数
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["synthetic_training"] is True


def test_ml_agent_tool_grounding(trained_models):
    """Agent 不得自行生成预测值：结果必须逐字段等于 registry 对同一 World State 的输出。"""
    state = create_demo_state(12)
    tools = AgentTools(state)
    features = extract_features(state)
    risk = tools.ml_predict_risk(10)
    expected_risk = registry.predict_risk(features, 10)
    assert risk["prediction"] == expected_risk["prediction"]
    assert risk["model_version"] == expected_risk["model_version"] == "risk_test_v1"
    assert risk["input_features"] == expected_risk["input_features"]
    assert risk["synthetic_training"] is True
    assert risk.get("fallback") is None
    recommendation = tools.ml_recommend_strategy()
    expected_recommendation = registry.recommend_strategy(features)
    assert recommendation["strategy"] == expected_recommendation["strategy"]
    assert recommendation["probabilities"] == expected_recommendation["probabilities"]
    assert recommendation["model_version"] == "policy_test_v1"


def test_ml_fallback_without_model(no_models):
    state = create_demo_state(8)
    tools = AgentTools(state)
    risk = tools.ml_predict_risk(10)
    assert risk["fallback"] is True
    assert "ML model unavailable" in risk["note"]
    assert risk["prediction"] == predict_world_state(state, 10).risk_score
    recommendation = tools.ml_recommend_strategy()
    assert recommendation["fallback"] is True
    assert "ML model unavailable" in recommendation["note"]
    best = min(SimulationEngine().compare(state), key=lambda result: result.after.risk)
    assert recommendation["strategy"] == best.strategy.value
    status = registry.status()
    assert status["risk_available"] is False and status["policy_available"] is False


def test_training_data_all_synthetic(tmp_path):
    records = _records(60, seed=DEFAULT_SEED)
    assert len(records) == 60
    assert all(record["synthetic"] is True for record in records)
    # 写入 parquet 后再读回，确认落盘数据同样全部 synthetic
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema([pa.field("episode_id", pa.int64()), pa.field("synthetic", pa.bool_()), pa.field("best_strategy", pa.string())])
    table = pa.Table.from_pylist(
        [{"episode_id": record["episode_id"], "synthetic": record["synthetic"], "best_strategy": record["best_strategy"]} for record in records],
        schema=schema,
    )
    path = tmp_path / "synthetic_check.parquet"
    pq.write_table(table, path)
    reloaded = pq.read_table(path).to_pylist()
    assert all(row["synthetic"] is True for row in reloaded)
    assert all(row["best_strategy"] in VALID_STRATEGIES for row in reloaded)
