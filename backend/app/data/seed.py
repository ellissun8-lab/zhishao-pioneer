from __future__ import annotations

import random

from ..behavior.engine import BehaviorEngine
from ..ontology.models import Agent, BehaviorState, Place, Position, RiskLevel, Zone
from ..world.state import WorldState

GUANGZHOU_CENTER = Position(lng=113.2644, lat=23.1291)
DEMO_CENTER = GUANGZHOU_CENTER
DEFAULT_SEED = 20260817
# 广州演示场景坐标范围（含生成抖动余量）；用于自动测试校验全部 Synthetic 数据都在广州范围内
GUANGZHOU_DEMO_BOUNDS = {"lng_min": 113.20, "lng_max": 113.33, "lat_min": 23.08, "lat_max": 23.18}


def position_in_guangzhou(position: Position) -> bool:
    return (
        GUANGZHOU_DEMO_BOUNDS["lng_min"] <= position.lng <= GUANGZHOU_DEMO_BOUNDS["lng_max"]
        and GUANGZHOU_DEMO_BOUNDS["lat_min"] <= position.lat <= GUANGZHOU_DEMO_BOUNDS["lat_max"]
    )


def generate_synthetic_agents(count: int = 80, seed: int = DEFAULT_SEED) -> list[Agent]:
    randomizer = random.Random(seed)
    agents: list[Agent] = []
    for index in range(count):
        risk_level = RiskLevel.HIGH if index == 0 else RiskLevel.MEDIUM if index < 12 else RiskLevel.LOW
        base_risk = 25 if index == 0 else 16 if risk_level == RiskLevel.MEDIUM else 8
        position = Position(
            lng=GUANGZHOU_CENTER.lng + randomizer.uniform(-0.025, 0.025),
            lat=GUANGZHOU_CENTER.lat + randomizer.uniform(-0.018, 0.018),
        )
        if index < 15:
            # 前 15 个主体目的地指向学校敏感区周边，保证运行时能稳定演示 ZoneEntered/CrowdGathered 剧情
            destination = Position(
                lng=GUANGZHOU_CENTER.lng + randomizer.uniform(-0.002, 0.002),
                lat=GUANGZHOU_CENTER.lat + randomizer.uniform(-0.002, 0.002),
            )
        else:
            destination = Position(
                lng=GUANGZHOU_CENTER.lng + randomizer.uniform(-0.02, 0.02),
                lat=GUANGZHOU_CENTER.lat + randomizer.uniform(-0.015, 0.015),
            )
        agents.append(
            Agent(
                id=f"agent_{chr(65 + index) if index < 26 else index + 1}",
                risk_level=risk_level,
                position=position,
                destination=destination,
                home_zone=f"residential_{index % 6}",
                mobility_pattern=randomizer.choice(["commute", "leisure", "station_transfer"]),
                behavior_state=BehaviorState.MOVING if index < 3 else BehaviorState.IDLE,
                social_group=f"group_{index % 8}",
                base_risk=base_risk,
                risk_score=base_risk,
                history=[position],
            )
        )
    return agents


DEMO_PLACES = [
    Place(id="school_001", category="school", name="开放数据示例学校（广州演示）", position=Position(lng=113.2644, lat=23.1291)),
    Place(id="hospital_001", category="hospital", name="开放数据示例医院（广州演示）", position=Position(lng=113.2760, lat=23.1220)),
    Place(id="station_001", category="station", name="开放数据示例车站（广州演示）", position=Position(lng=113.2520, lat=23.1340)),
]


def create_demo_state(agent_count: int = 80, seed: int = DEFAULT_SEED) -> WorldState:
    agents = generate_synthetic_agents(agent_count, seed)
    zones = [Zone(id="school_zone_001", name="学校敏感区域", center=GUANGZHOU_CENTER, radius=500, sensitivity=0.9)]
    state = WorldState(
        agents={agent.id: agent for agent in agents},
        places={place.id: place for place in DEMO_PLACES},
        zones={zone.id: zone for zone in zones},
    )
    return BehaviorEngine().recalculate(state)
