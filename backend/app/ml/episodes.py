"""Synthetic Episode 生成器。

每个 Episode 通过参数采样构造一个真实 WorldState，随后标签完全来自现有
World Behavior Model（predict_world_state）与 What-if Simulation
（SimulationEngine），禁止随机编造标签。

所有数据 100% Synthetic：不含任何真实居民、监控或警务数据。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterator

import numpy as np

from ..behavior.prediction import predict_world_state
from ..ontology.models import Agent, BehaviorState, Event, EventType, Position, RiskLevel, Zone
from ..simulation.engine import SimulationEngine
from ..simulation.strategies import Strategy
from ..world.state import WorldState
from .features import FEATURE_SCHEMA, extract_features

# 使不同策略在不同风险带胜出（w=2.5 时大致：risk<14 none；<19 warn；<50 guide_leave；>=50 intervene）
DEFAULT_INTERVENTION_COST_WEIGHT = 2.5
DEFAULT_SEED = 42
TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.70, 0.15, 0.15
RISK_LABEL_HORIZONS = (5, 10, 30)
DEFAULT_HORIZON = 10

# 分层场景原型：均匀采样保证标签与特征分布多样，避免 >90% 样本雷同
ARCHETYPES: list[str] = [
    "quiet",
    "commute",
    "zone_activity",
    "crowd_detected",
    "crowd_gathered",
    "risk_object",
    "vehicle",
    "high_risk",
    "dispersing",
]

# 每个原型的 (风险下界, 风险上界, 进入敏感区概率, 主体数上限)
ARCHETYPE_PARAMS: dict[str, tuple[float, float, float, int]] = {
    "quiet": (3.0, 20.0, 0.05, 14),
    "commute": (8.0, 38.0, 0.15, 26),
    "zone_activity": (24.0, 56.0, 0.65, 28),
    "crowd_detected": (34.0, 70.0, 0.75, 30),
    "crowd_gathered": (46.0, 86.0, 0.85, 30),
    "risk_object": (38.0, 80.0, 0.45, 26),
    "vehicle": (5.0, 26.0, 0.10, 22),
    "high_risk": (56.0, 96.0, 0.90, 30),
    "dispersing": (28.0, 64.0, 0.35, 24),
}

DEMO_POSITION = Position(lng=113.2644, lat=23.1291)


def _risk_level(score: float) -> RiskLevel:
    if score >= 55:
        return RiskLevel.HIGH
    if score >= 30:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def build_state(rng: np.random.Generator, archetype: str) -> WorldState:
    """按场景原型 + 随机参数构造一个 Synthetic WorldState。"""
    risk_lo, risk_hi, zone_prob, population_cap = ARCHETYPE_PARAMS[archetype]
    hour = int(rng.integers(0, 24))
    minute = int(rng.integers(0, 60))
    timestamp = datetime(2026, 8, 18, hour, minute)

    population = int(rng.integers(3, population_cap + 1))
    current_risk = float(rng.uniform(risk_lo, risk_hi))
    sensitivity = float(rng.uniform(0.5, 1.0))

    zones: dict[str, Zone] = {
        "zone_demo_0": Zone(
            id="zone_demo_0",
            name="synthetic_zone_demo",
            center=DEMO_POSITION,
            radius=500,
            sensitivity=sensitivity,
        )
    }
    agents: dict[str, Agent] = {}
    behavior_pool: list[BehaviorState] = {
        "quiet": [BehaviorState.IDLE, BehaviorState.IDLE, BehaviorState.MOVING],
        "commute": [BehaviorState.MOVING, BehaviorState.MOVING, BehaviorState.ENTERING_SENSITIVE_ZONE, BehaviorState.IDLE],
        "zone_activity": [BehaviorState.ENTERING_SENSITIVE_ZONE, BehaviorState.MOVING, BehaviorState.GATHERING],
        "crowd_detected": [BehaviorState.MOVING, BehaviorState.GATHERING, BehaviorState.GATHERING, BehaviorState.MOVING],
        "crowd_gathered": [BehaviorState.GATHERING, BehaviorState.GATHERING, BehaviorState.RISK_ESCALATING],
        "risk_object": [BehaviorState.IDLE, BehaviorState.MOVING, BehaviorState.RISK_ESCALATING],
        "vehicle": [BehaviorState.MOVING, BehaviorState.IDLE, BehaviorState.MOVING],
        "high_risk": [BehaviorState.RISK_ESCALATING, BehaviorState.GATHERING, BehaviorState.RISK_ESCALATING],
        "dispersing": [BehaviorState.DISPERSING, BehaviorState.MOVING, BehaviorState.IDLE],
    }[archetype]
    for index in range(population):
        agent_risk = float(np.clip(current_risk * rng.uniform(0.4, 1.4) + rng.normal(0, 6), 0, 100))
        in_zone = bool(rng.random() < zone_prob)
        agents[f"synthetic_agent_{index:03d}"] = Agent(
            id=f"synthetic_agent_{index:03d}",
            position=DEMO_POSITION,
            risk_score=round(agent_risk, 1),
            risk_level=_risk_level(agent_risk),
            behavior_state=behavior_pool[int(rng.integers(0, len(behavior_pool)))],
            active_zone_ids=["zone_demo_0"] if in_zone else [],
        )

    events: list[Event] = []
    crowd_size = int(rng.integers(3, 41))

    def add_event(event_type: EventType, age_range: tuple[float, float], **kwargs: object) -> None:
        age_minutes = float(rng.uniform(*age_range))
        confidence = float(rng.uniform(0.55, 1.0))
        events.append(
            Event(
                type=event_type,
                subject_id="synthetic_agent_000",
                timestamp=timestamp - timedelta(minutes=age_minutes),
                confidence=confidence,
                source="synthetic_training",
                **kwargs,
            )
        )

    if archetype in {"commute", "zone_activity", "crowd_detected", "crowd_gathered", "risk_object", "high_risk", "dispersing"}:
        add_event(EventType.PERSON_DETECTED, (0, 60))
    if archetype == "vehicle":
        add_event(EventType.VEHICLE_DETECTED, (0, 45))
    if archetype == "zone_activity":
        add_event(EventType.ZONE_ENTERED, (0, 40), object_id="zone_demo_0")
    if archetype == "crowd_detected":
        add_event(EventType.CROWD_DETECTED, (0, 45), metadata={"crowd_size": crowd_size})
    if archetype in {"crowd_gathered", "high_risk"}:
        add_event(EventType.CROWD_GATHERED, (0, 45), object_id="zone_demo_0", metadata={"crowd_size": crowd_size})
    if archetype in {"risk_object", "high_risk"}:
        add_event(EventType.RISK_OBJECT_DETECTED, (0, 45))
    if archetype == "dispersing":
        add_event(EventType.CROWD_DISPERSED, (0, 50))

    state = WorldState(
        timestamp=timestamp,
        agents=agents,
        zones=zones,
        active_events=events,
    )
    state.risk_state.overall_score = round(current_risk, 1)
    state.risk_state.level = _risk_level(current_risk).value
    return state


def compute_labels(state: WorldState, intervention_cost_weight: float = DEFAULT_INTERVENTION_COST_WEIGHT) -> dict[str, object]:
    """标签只来自现有 World Behavior Model 与 What-if Simulation。"""
    risk_labels = {f"risk_{h}m": predict_world_state(state, h).risk_score for h in RISK_LABEL_HORIZONS}
    simulations = SimulationEngine().compare(state, DEFAULT_HORIZON)
    utilities: dict[str, float] = {}
    for result in simulations:
        risk_reduction = result.before.risk - result.after.risk
        utilities[result.strategy.value] = round(risk_reduction - intervention_cost_weight * result.action_cost, 4)
    best_strategy = Strategy.NONE.value
    best_utility = utilities[best_strategy]
    for strategy in (Strategy.WARN, Strategy.GUIDE_LEAVE, Strategy.INTERVENE):
        if utilities[strategy.value] > best_utility:
            best_strategy, best_utility = strategy.value, utilities[strategy.value]
    return {**risk_labels, **{f"utility_{key}": value for key, value in utilities.items()}, "best_strategy": best_strategy}


def make_episode_record(episode_id: int, state: WorldState, intervention_cost_weight: float) -> dict[str, object]:
    features = extract_features(state)
    labels = compute_labels(state, intervention_cost_weight)
    event_types = ",".join(sorted({event.type.value for event in state.active_events}))
    dominant_behavior = max({agent.behavior_state.value for agent in state.agents.values()}, key=lambda value: sum(1 for a in state.agents.values() if a.behavior_state.value == value)) if state.agents else "idle"
    return {
        "episode_id": episode_id,
        "synthetic": True,
        "archetype": "",
        "split": "",
        "event_types": event_types,
        "dominant_behavior": dominant_behavior,
        **features,
        **labels,
    }


def split_plan(episodes: int, seed: int = DEFAULT_SEED) -> np.ndarray:
    """按 episode_id 切分 train/val/test（70/15/15），seed 固定则可复现。"""
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(episodes)
    train_count = int(round(episodes * TRAIN_RATIO))
    val_count = int(round(episodes * VAL_RATIO))
    splits = np.empty(episodes, dtype="object")
    splits[permutation[:train_count]] = "train"
    splits[permutation[train_count:train_count + val_count]] = "validation"
    splits[permutation[train_count + val_count:]] = "test"
    return splits


def iter_episode_records(
    episodes: int,
    seed: int = DEFAULT_SEED,
    intervention_cost_weight: float = DEFAULT_INTERVENTION_COST_WEIGHT,
) -> Iterator[dict[str, object]]:
    """流式生成 episode 记录；每次只保留当前记录，支持 12 万级规模。"""
    rng = np.random.default_rng(seed)
    archetype_index = np.random.default_rng(seed + 1)
    splits = split_plan(episodes, seed)
    for episode_id in range(episodes):
        archetype = ARCHETYPES[int(archetype_index.integers(0, len(ARCHETYPES)))]
        state = build_state(rng, archetype)
        record = make_episode_record(episode_id, state, intervention_cost_weight)
        record["archetype"] = archetype
        record["split"] = str(splits[episode_id])
        yield record


@dataclass
class DistributionStats:
    episodes: int = 0
    risk_histogram: dict[str, int] = field(default_factory=lambda: {f"{i * 10}-{(i + 1) * 10}": 0 for i in range(10)})
    event_type_counts: dict[str, int] = field(default_factory=dict)
    strategy_counts: dict[str, int] = field(default_factory=dict)
    behavior_counts: dict[str, int] = field(default_factory=dict)
    zone_active_ratio: float = 0.0
    risk_object_ratio: float = 0.0
    crowd_ratio: float = 0.0

    def update(self, record: dict[str, object]) -> None:
        self.episodes += 1
        bucket = min(9, int(float(record["current_risk"]) // 10))
        self.risk_histogram[f"{bucket * 10}-{(bucket + 1) * 10}"] += 1
        for event_type in str(record["event_types"]).split(","):
            if event_type:
                self.event_type_counts[event_type] = self.event_type_counts.get(event_type, 0) + 1
        strategy = str(record["best_strategy"])
        self.strategy_counts[strategy] = self.strategy_counts.get(strategy, 0) + 1
        behavior = str(record["dominant_behavior"])
        self.behavior_counts[behavior] = self.behavior_counts.get(behavior, 0) + 1
        self.zone_active_ratio += float(record["sensitive_zone_active"])
        self.risk_object_ratio += float(record["risk_object_detected"])
        self.crowd_ratio += max(float(record["crowd_detected"]), float(record["crowd_gathered"]))

    def to_dict(self) -> dict[str, object]:
        total = self.episodes or 1
        return {
            "episodes": self.episodes,
            "risk_score_distribution": dict(sorted(self.risk_histogram.items())),
            "event_type_distribution": dict(sorted(self.event_type_counts.items())),
            "strategy_label_distribution": dict(sorted(self.strategy_counts.items())),
            "behavior_state_distribution": dict(sorted(self.behavior_counts.items())),
            "zone_active_ratio": round(self.zone_active_ratio / total, 4),
            "risk_object_ratio": round(self.risk_object_ratio / total, 4),
            "crowd_ratio": round(self.crowd_ratio / total, 4),
        }


def canonical_record_hash(records: list[dict[str, object]]) -> str:
    """对记录列表做确定性 sha256（sort_keys + 紧凑分隔符），用于复现性校验。"""
    import hashlib

    payload = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
