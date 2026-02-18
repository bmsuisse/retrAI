"""Async event bus with fan-out to multiple subscribers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from retrai.events.types import AgentEvent


class AsyncEventBus:
    """Fan-out event bus. Each subscriber gets its own queue."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[AgentEvent | None]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[AgentEvent | None]:
        """Create and register a new subscriber queue."""
        q: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[AgentEvent | None]) -> None:
        async with self._lock:
            self._subscribers.remove(q)

    async def publish(self, event: AgentEvent) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            await q.put(event)

    async def close(self) -> None:
        """Signal all subscribers that the bus is closing."""
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            await q.put(None)

    async def iter_events(self, q: asyncio.Queue[AgentEvent | None]) -> AsyncIterator[AgentEvent]:
        """Async-iterate over events from a subscriber queue."""
        while True:
            event = await q.get()
            if event is None:
                break
            yield event
