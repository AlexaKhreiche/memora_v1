from __future__ import annotations

from queue import Queue
from typing import Optional

from agent.core.rules import Event


class EventBus:
    def __init__(self) -> None:
        self._q: Queue[Event] = Queue()

    def publish(self, event: Event) -> None:
        self._q.put(event)

    def get(self, timeout: Optional[float] = None) -> Event:
        return self._q.get(timeout=timeout)
