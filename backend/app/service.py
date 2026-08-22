from __future__ import annotations

from threading import RLock

from .data.seed import DEFAULT_SEED, create_demo_state
from .database import init_database, record_event
from .ontology.models import Event, EventType, Position
from .simulation.runtime import SyntheticAgentRuntime
from .world.event_bus import EventBus

DEFAULT_RUNTIME_SEED = 42
ALERT_TRIGGER_SCORE = 60


class WorldService:
    def __init__(self) -> None:
        self._lock = RLock()
        init_database()
        self.reset()

    def reset(self, seed: int | None = None) -> None:
        with getattr(self, "_lock", RLock()):
            self.state = create_demo_state(seed=seed or DEFAULT_SEED)
            self.event_bus = EventBus(self.state)
            self.runtime = SyntheticAgentRuntime(seed=seed or DEFAULT_RUNTIME_SEED)
            self.demo_step = 0
            self._alert_active = False
            self._published_event_ids: set[str] = set()

    def add_agent(self, agent) -> object:
        with self._lock:
            if not agent.synthetic:
                raise ValueError("MVP only accepts synthetic agents")
            self.state.agents[agent.id] = agent
            return agent

    def _publish_unlocked(self, event: Event) -> None:
        if event.subject_id and event.subject_id not in self.state.agents:
            raise ValueError(f"Unknown subject_id: {event.subject_id}")
        if event.type in {EventType.ZONE_ENTERED, EventType.ZONE_EXITED}:
            if not event.object_id or event.object_id not in self.state.zones:
                raise ValueError(f"Unknown zone object_id: {event.object_id}")
        if event.id in self._published_event_ids:
            return
        self._published_event_ids.add(event.id)
        self.event_bus.publish(event)
        record_event(event)
        self._maybe_alert_unlocked()

    def _maybe_alert_unlocked(self) -> None:
        """风险进入 high 且当前无告警时，经 Event Bus 触发 AlertTriggered。"""
        score = self.state.risk_state.overall_score
        if score >= ALERT_TRIGGER_SCORE and not self._alert_active:
            self._alert_active = True
            alert = Event(
                type=EventType.ALERT_TRIGGERED,
                source="risk_engine",
                metadata={"risk_score": score, "reason": "risk_state.overall_score >= 60"},
            )
            self.event_bus.publish(alert)
            self._published_event_ids.add(alert.id)
            record_event(alert)
        elif score < ALERT_TRIGGER_SCORE:
            self._alert_active = False

    def publish(self, event: Event):
        with self._lock:
            self._publish_unlocked(event)
            return self.state

    def tick(self, steps: int = 1, dt_seconds: float = 15.0):
        """推进事件驱动仿真 N 个 tick；所有事件经 Event Bus 写入 World State。"""
        events: list[Event] = []
        with self._lock:
            for _ in range(steps):
                events.extend(self.runtime.tick(self.state, self._publish_unlocked, dt_seconds))
            return {"state": self.state, "events": events}

    def advance_demo(self):
        sequence = [
            Event(type=EventType.MOVE_STARTED, subject_id="agent_A", metadata={"position": {"lng": 113.2584, "lat": 23.1251}}),
            Event(type=EventType.ZONE_ENTERED, subject_id="agent_A", object_id="school_zone_001", metadata={"position": {"lng": 113.2644, "lat": 23.1291}}),
            Event(type=EventType.CROWD_GATHERED, subject_id="agent_A", object_id="school_zone_001", confidence=1, metadata={"agent_ids": ["agent_A", "agent_B", "agent_C"]}),
            Event(type=EventType.RISK_OBJECT_DETECTED, subject_id="agent_A", confidence=1, source="mock_cv"),
        ]
        with self._lock:
            if self.demo_step >= len(sequence):
                self.reset()
            event = sequence[self.demo_step]
            if self.demo_step == 2:
                for index, agent_id in enumerate(["agent_B", "agent_C"]):
                    agent = self.state.agents[agent_id]
                    agent.history.append(agent.position.model_copy())
                    agent.position = Position(lng=113.2644 + index * 0.0003, lat=23.1291 + index * 0.0002)
            self.demo_step += 1
            self._publish_unlocked(event)
            return {"step": self.demo_step, "event": event, "state": self.state}


world_service = WorldService()
