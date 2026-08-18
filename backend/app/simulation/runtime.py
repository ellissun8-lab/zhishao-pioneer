"""事件驱动的 Synthetic Agent 仿真运行时。

每个 tick 的标准链路：
Position Update -> Spatial Detection -> Event -> Event Bus -> World State -> Risk Engine

运行时负责移动主体与空间检测；行为状态、活跃事件与风险全部经由
Event -> Event Bus -> WorldStateUpdater 更新，绝不直接改写风险值。
位置推进本身不是事件（Position Update），只有状态语义变化才发布 Event：
出行开始发 MoveStarted，到达发 MoveStopped，进出敏感区发 ZoneEntered/ZoneExited，
聚集形成/解除发 CrowdGathered/CrowdDispersed。
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from ..ontology.models import Agent, Event, EventType, Position
from ..world.state import WorldState

METERS_PER_DEGREE_LAT = 111_320.0
WALK_SPEED_METERS_PER_SECOND = 1.4
ARRIVAL_RADIUS_METERS = 20.0
CROWD_MIN_SIZE = 3
START_MOVING_PROBABILITY = 0.18
HISTORY_LIMIT = 60
SCHOOL_TRIP_PROBABILITY = 0.35


def distance_meters(a: Position, b: Position) -> float:
    mid_lat = math.radians((a.lat + b.lat) / 2)
    dx = (a.lng - b.lng) * METERS_PER_DEGREE_LAT * math.cos(mid_lat)
    dy = (a.lat - b.lat) * METERS_PER_DEGREE_LAT
    return math.hypot(dx, dy)


def step_toward(origin: Position, target: Position, travel_meters: float) -> Position:
    total = distance_meters(origin, target)
    if total <= travel_meters or total == 0:
        return Position(lng=target.lng, lat=target.lat)
    ratio = travel_meters / total
    return Position(
        lng=origin.lng + (target.lng - origin.lng) * ratio,
        lat=origin.lat + (target.lat - origin.lat) * ratio,
    )


class SyntheticAgentRuntime:
    """驱动 Synthetic Agents 自主移动并产生 Ontology 事件的仿真引擎。

    使用固定 seed 的 RNG，保证 Demo 模式下同一输入得到相同的推演过程。
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._moving: set[str] = set()
        self._idle_until_tick: dict[str, int] = {}
        self._crowd_members: dict[str, list[str]] = {}
        self._tick_count = 0

    def _next_destination(self, state: WorldState) -> Position:
        if self._rng.random() < SCHOOL_TRIP_PROBABILITY:
            zone = next(iter(state.zones.values()))
            return Position(
                lng=zone.center.lng + self._rng.uniform(-0.002, 0.002),
                lat=zone.center.lat + self._rng.uniform(-0.002, 0.002),
            )
        anchor = next(iter(state.places.values()), None)
        base = anchor.position if anchor else next(iter(state.agents.values())).position
        return Position(lng=base.lng + self._rng.uniform(-0.015, 0.015), lat=base.lat + self._rng.uniform(-0.012, 0.012))

    def tick(self, state: WorldState, publish: Callable[[Event], None], dt_seconds: float = 15.0) -> list[Event]:
        """推进一个仿真 tick，返回本 tick 发布的全部事件。"""
        self._tick_count += 1
        events: list[Event] = []
        travel = WALK_SPEED_METERS_PER_SECOND * dt_seconds

        def emit(event: Event) -> None:
            events.append(event)
            publish(event)

        for agent in list(state.agents.values()):
            if agent.id not in self._moving:
                if agent.behavior_state.value == "moving" and agent.destination is not None:
                    self._moving.add(agent.id)
                elif (
                    self._idle_until_tick.get(agent.id, 0) <= self._tick_count
                    and self._rng.random() < START_MOVING_PROBABILITY
                ):
                    if agent.destination is None:
                        agent.destination = self._next_destination(state)
                    self._moving.add(agent.id)
                    emit(Event(type=EventType.MOVE_STARTED, subject_id=agent.id, source="synthetic_runtime"))
                else:
                    continue
            if agent.destination is None:
                self._moving.discard(agent.id)
                continue
            previous = agent.position.model_copy()
            agent.position = step_toward(previous, agent.destination, travel)
            agent.history.append(previous)
            if len(agent.history) > HISTORY_LIMIT:
                del agent.history[: len(agent.history) - HISTORY_LIMIT]
            if distance_meters(agent.position, agent.destination) <= ARRIVAL_RADIUS_METERS:
                agent.destination = None
                self._moving.discard(agent.id)
                self._idle_until_tick[agent.id] = self._tick_count + self._rng.randint(2, 6)
                emit(Event(type=EventType.MOVE_STOPPED, subject_id=agent.id, source="synthetic_runtime"))

        for zone in state.zones.values():
            inside = [agent for agent in state.agents.values() if distance_meters(agent.position, zone.center) <= zone.radius]
            inside_ids = [agent.id for agent in inside]
            for agent in inside:
                if zone.id not in agent.active_zone_ids:
                    emit(Event(type=EventType.ZONE_ENTERED, subject_id=agent.id, object_id=zone.id, source="synthetic_runtime"))
            for agent in state.agents.values():
                if zone.id in agent.active_zone_ids and agent.id not in inside_ids:
                    emit(Event(type=EventType.ZONE_EXITED, subject_id=agent.id, object_id=zone.id, source="synthetic_runtime"))
            if len(inside) >= CROWD_MIN_SIZE:
                if zone.id not in self._crowd_members:
                    self._crowd_members[zone.id] = inside_ids
                    emit(
                        Event(
                            type=EventType.CROWD_GATHERED,
                            subject_id=inside_ids[0],
                            object_id=zone.id,
                            source="synthetic_runtime",
                            metadata={"agent_ids": inside_ids, "size": len(inside_ids)},
                        )
                    )
                else:
                    self._crowd_members[zone.id] = inside_ids
            elif zone.id in self._crowd_members:
                members = self._crowd_members.pop(zone.id)
                emit(
                    Event(
                        type=EventType.CROWD_DISPERSED,
                        subject_id=members[0] if members else None,
                        object_id=zone.id,
                        source="synthetic_runtime",
                        metadata={"zone_id": zone.id, "previous_members": members},
                    )
                )
        return events
