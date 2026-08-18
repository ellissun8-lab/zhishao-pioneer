from collections.abc import Callable

from ..ontology.models import Event
from .state import WorldState
from .updater import WorldStateUpdater


class EventBus:
    def __init__(self, state: WorldState, updater: WorldStateUpdater | None = None) -> None:
        self.state = state
        self.updater = updater or WorldStateUpdater()
        self._subscribers: list[Callable[[Event, WorldState], None]] = []

    def subscribe(self, callback: Callable[[Event, WorldState], None]) -> None:
        self._subscribers.append(callback)

    def publish(self, event: Event) -> WorldState:
        self.updater.apply(self.state, event)
        for callback in self._subscribers:
            callback(event, self.state)
        return self.state

