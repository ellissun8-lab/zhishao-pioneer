"""Synthetic Training Pipeline 测试。

覆盖：生成可复现、标签来自仿真、特征无身份泄漏、切分隔离、
预测边界、策略合法、Agent 工具接地（grounding）、无模型回退、全量 synthetic、
跨进程 hash 稳定、特征向量唯一、Agent 运行态 ML 调用链。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import joblib
from fastapi.testclient import TestClient
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from backend.app.data.seed import create_demo_state
from backend.app.behavior.prediction import predict_world_state
from backend.app.llm.agent import explain_question
from backend.app.llm.tools import AgentTools
from backend.app.main import app
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
from backend.app.service import world_service
from backend.app.simulation.engine import SimulationEngine
from backend.app.simulation.strategies import Strategy

VALID_STRATEGIES = {strategy.value for strategy in Strategy}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
        assert set(result["probabilities"]) == set(VALID_STRATEGIES)
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
    best = max(
        SimulationEngine().compare(state),
        key=lambda result: result.before.risk - result.after.risk - DEFAULT_INTERVENTION_COST_WEIGHT * result.action_cost,
    )
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


# ---------- Codex ML Validation 修复：跨进程 hash / 特征唯一 / Agent ML 调用链 ----------

_HASH_SNIPPET = (
    "import sys; sys.path.insert(0, {root!r}); "
    "from backend.app.ml.episodes import canonical_record_hash, iter_episode_records; "
    "print(canonical_record_hash(list(iter_episode_records(60, seed=42))))"
)


def _subprocess_hash(python_hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": python_hash_seed}
    result = subprocess.run(
        [sys.executable, "-c", _HASH_SNIPPET.format(root=str(PROJECT_ROOT))],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(PROJECT_ROOT),
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_dataset_hash_stable_across_processes():
    """同一 seed 在不同 PYTHONHASHSEED 的独立进程中必须产生相同 deterministic hash。

    旧实现 dominant_behavior 用 max(set, ...)，平局时依赖 set 迭代顺序
    （受字符串哈希随机化影响），跨进程不稳定；此处直接回归。
    """
    hashes = [_subprocess_hash(seed) for seed in ("1", "2", "20260819")]
    assert hashes[0] == hashes[1] == hashes[2]
    assert len(hashes[0]) == 64


def test_generated_feature_vectors_unique():
    """生成期 feature-level 唯一性 guard：全部特征向量（16 维）互不相同。"""
    records = _records(2000, seed=DEFAULT_SEED)
    vectors = {tuple(float(record[name]) for name in FEATURE_SCHEMA) for record in records}
    assert len(vectors) == len(records), f"存在重复 feature vector: {len(records) - len(vectors)} 条"


def test_agent_calls_ml_predict_risk(trained_models):
    state = create_demo_state(10)
    response = explain_question("训练模型认为未来10分钟风险多少？", state)
    assert response["tools_used"] == ["ml_predict_risk"]
    prediction = response["ml_prediction"]
    assert prediction["model"] == "risk_forecast"
    assert prediction["model_version"] == "risk_test_v1"
    assert prediction["synthetic_training"] is True
    assert prediction.get("fallback") is None
    assert f"{prediction['prediction']:.1f}" in response["answer"]
    assert "risk_test_v1" in response["answer"]


def test_agent_calls_ml_recommend_strategy(trained_models):
    state = create_demo_state(10)
    response = explain_question("模型建议采取什么措施？", state)
    assert "ml_recommend_strategy" in response["tools_used"]
    recommendation = response["ml_recommendation"]
    assert recommendation["model"] == "intervention_policy"
    assert recommendation["model_version"] == "policy_test_v1"
    assert recommendation["strategy"] in VALID_STRATEGIES


def test_agent_strategy_explanation_contains_probability(trained_models):
    state = create_demo_state(10)
    response = explain_question("模型建议采取什么措施？", state)
    answer = response["answer"]
    assert "模型概率/置信度" in answer
    assert "四策略概率" in answer
    assert "%" in answer
    recommendation = response["ml_recommendation"]
    assert recommendation["confidence"] == max(recommendation["probabilities"].values())
    # 不得宣称现实世界概率
    assert "现实世界最佳措施概率" in answer


def test_agent_ml_recommendation_then_simulation(trained_models):
    """推荐流程必须是 ml_recommend_strategy -> What-if 仿真二次验证，顺序可验证。"""
    state = create_demo_state(10)
    response = explain_question("模型建议采取什么措施？", state)
    assert response["tools_used"] == ["ml_recommend_strategy", "compare_strategies"]
    answer = response["answer"]
    assert "What-if 仿真验证" in answer
    assert "模型推荐" in answer
    # 仿真数字必须来自 compare_strategies 的真实结果
    simulations = SimulationEngine().compare(state)
    for result in simulations:
        assert f"{result.after.risk:.1f}" in answer


def test_agent_does_not_label_rule_prediction_as_ml(no_models):
    state = create_demo_state(8)
    # 显式问 ML：模型缺失时必须说明回退，不得把规则输出伪装成 ML 输出
    ml_answer = explain_question("训练模型认为未来10分钟风险多少？", state)
    assert ml_answer["tools_used"] == ["ml_predict_risk"]
    assert "ML 模型不可用" in ml_answer["answer"]
    assert "规则世界模型" in ml_answer["answer"]
    assert ml_answer["ml_prediction"]["fallback"] is True
    # 普通预测问题走规则路径，且必须声明非 ML
    rule_answer = explain_question("未来10分钟会怎样？", state)
    assert rule_answer["tools_used"] == ["predict_future"]
    assert "规则世界模型" in rule_answer["answer"]
    assert "非 ML 模型" in rule_answer["answer"]


def test_ml_predict_risk_api(trained_models):
    """POST /api/ml/predict-risk：World State -> features -> joblib 模型。"""
    world_service.reset()
    client = TestClient(app)
    response = client.post("/api/ml/predict-risk", json={"horizon_minutes": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "risk_forecast"
    assert payload["model_type"] == "HistGradientBoostingRegressor"
    assert payload["model_version"] == "risk_test_v1"
    assert payload["horizon_minutes"] == 10
    assert 0.0 <= payload["prediction"] <= 100.0
    assert payload["synthetic_training"] is True
    assert payload["fallback"] is False
    assert set(payload["input_features"]) == set(FEATURE_SCHEMA)
    # 与直接调用 registry 的结果一致（同一 World State -> 同一特征 -> 同一模型）
    expected = registry.predict_risk(extract_features(world_service.state), 10)
    assert payload["prediction"] == expected["prediction"]
    # 非法 horizon 拒绝
    assert client.post("/api/ml/predict-risk", json={"horizon_minutes": 15}).status_code == 400


def test_ml_predict_risk_api_fallback(no_models):
    world_service.reset()
    client = TestClient(app)
    response = client.post("/api/ml/predict-risk", json={"horizon_minutes": 10, "use_current_world_state": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] is True
    assert payload["model_type"] == "TransparentRuleWorldBehaviorModel"
    assert payload["fallback_source"] == "rule_world_behavior_model"
    assert payload["synthetic_training"] is False
    assert payload["prediction"] == predict_world_state(world_service.state, 10).risk_score
