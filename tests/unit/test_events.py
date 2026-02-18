"""Tests for the event system (types + bus)."""

from __future__ import annotations

import asyncio
import time

import pytest

from retrai.events.bus import AsyncEventBus
from retrai.events.types import AgentEvent

# ── AgentEvent ────────────────────────────────────────────────────────────────


def test_event_to_dict(sample_event: AgentEvent):
    d = sample_event.to_dict()
    assert d["kind"] == "tool_call"
    assert d["run_id"] == "test-run-1"
    assert d["iteration"] == 1
    assert d["payload"]["tool"] == "bash_exec"
    assert isinstance(d["ts"], float)


def test_event_ts_defaults_to_now():
    before = time.time()
    event = AgentEvent(kind="log", run_id="x", iteration=0, payload={})
    after = time.time()
    assert before <= event.ts <= after


def test_all_event_kinds_are_valid():
    kinds = [
        "step_start",
        "tool_call",
        "tool_result",
        "goal_check",
        "human_check_required",
        "human_check_response",
        "iteration_complete",
        "run_end",
        "error",
        "log",
    ]
    for kind in kinds:
        e = AgentEvent(kind=kind, run_id="x", iteration=0, payload={})  # type: ignore[arg-type]
        assert e.kind == kind


# ── AsyncEventBus ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_and_receive():
    bus = AsyncEventBus()
    q = await bus.subscribe()
    event = AgentEvent(kind="log", run_id="r1", iteration=0, payload={"msg": "hi"})
    await bus.publish(event)
    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received is event
    await bus.close()


@pytest.mark.asyncio
async def test_fan_out_to_multiple_subscribers():
    bus = AsyncEventBus()
    q1 = await bus.subscribe()
    q2 = await bus.subscribe()
    event = AgentEvent(kind="log", run_id="r1", iteration=0, payload={})
    await bus.publish(event)
    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert r1 is event
    assert r2 is event
    await bus.close()


@pytest.mark.asyncio
async def test_close_sends_none_sentinel():
    bus = AsyncEventBus()
    q = await bus.subscribe()
    await bus.close()
    sentinel = await asyncio.wait_for(q.get(), timeout=1.0)
    assert sentinel is None


@pytest.mark.asyncio
async def test_iter_events_stops_at_close():
    bus = AsyncEventBus()
    q = await bus.subscribe()

    events_seen = []

    async def consumer():
        async for e in bus.iter_events(q):
            events_seen.append(e)

    task = asyncio.create_task(consumer())
    e1 = AgentEvent(kind="log", run_id="r", iteration=0, payload={})
    e2 = AgentEvent(kind="log", run_id="r", iteration=1, payload={})
    await bus.publish(e1)
    await bus.publish(e2)
    await bus.close()
    await asyncio.wait_for(task, timeout=2.0)
    assert events_seen == [e1, e2]


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bus = AsyncEventBus()
    q = await bus.subscribe()
    await bus.unsubscribe(q)
    event = AgentEvent(kind="log", run_id="r", iteration=0, payload={})
    await bus.publish(event)
    assert q.empty()
    await bus.close()


@pytest.mark.asyncio
async def test_publish_multiple_events_in_order():
    bus = AsyncEventBus()
    q = await bus.subscribe()
    for i in range(5):
        await bus.publish(AgentEvent(kind="log", run_id="r", iteration=i, payload={}))
    await bus.close()

    received = []
    async for e in bus.iter_events(q):
        received.append(e.iteration)

    assert received == list(range(5))
