"""Smoke tests for the LangGraph agent (mocked LLM)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from retrai.agent.graph import build_graph
from retrai.agent.state import AgentState
from retrai.events.bus import AsyncEventBus
from retrai.events.types import AgentEvent
from retrai.goals.pytest_goal import PytestGoal


def _make_ai_message_no_tools(content: str = "I'm done.") -> AIMessage:
    """An AIMessage with no tool calls → triggers evaluate immediately."""
    msg = AIMessage(content=content)
    msg.tool_calls = []  # type: ignore[attr-defined]
    return msg


@pytest.fixture
def mock_llm():
    """Return a mock LLM that immediately says 'done' with no tool calls."""
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=_make_ai_message_no_tools())
    return llm


@pytest.fixture
def passing_goal(passing_project: Path) -> PytestGoal:
    return PytestGoal()


@pytest.mark.asyncio
async def test_graph_compiles_without_hitl():
    graph = build_graph(hitl_enabled=False)
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_compiles_with_hitl():
    graph = build_graph(hitl_enabled=True)
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_runs_to_end_when_goal_passes(passing_project: Path, mock_llm: MagicMock):
    """Graph should terminate when goal is achieved on first evaluate."""
    bus = AsyncEventBus()
    goal = PytestGoal()
    graph = build_graph(hitl_enabled=False)

    initial_state: AgentState = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": 5,
        "hitl_enabled": False,
        "model_name": "claude-sonnet-4-6",
        "cwd": str(passing_project),
        "run_id": "smoke-test-1",
        "total_tokens": 0,
    }
    run_config = {
        "configurable": {
            "thread_id": "smoke-test-1",
            "event_bus": bus,
            "goal": goal,
        }
    }

    with patch("retrai.agent.nodes.plan.get_llm", return_value=mock_llm):
        final = await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]

    await bus.close()
    assert final["goal_achieved"] is True


@pytest.mark.asyncio
async def test_graph_stops_at_max_iterations(failing_project: Path, mock_llm: MagicMock):
    """With a persistently failing goal and max_iterations=2, graph ends."""
    bus = AsyncEventBus()
    goal = PytestGoal()
    graph = build_graph(hitl_enabled=False)

    initial_state: AgentState = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": 2,
        "hitl_enabled": False,
        "model_name": "claude-sonnet-4-6",
        "cwd": str(failing_project),
        "run_id": "smoke-test-2",
        "total_tokens": 0,
    }
    run_config = {
        "configurable": {
            "thread_id": "smoke-test-2",
            "event_bus": bus,
            "goal": goal,
        }
    }

    with patch("retrai.agent.nodes.plan.get_llm", return_value=mock_llm):
        final = await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]

    await bus.close()
    assert final["goal_achieved"] is False
    assert final["iteration"] >= 2


@pytest.mark.asyncio
async def test_graph_emits_events(passing_project: Path, mock_llm: MagicMock):
    """Graph should emit at minimum step_start, goal_check, run_end events."""
    bus = AsyncEventBus()
    q = await bus.subscribe()
    goal = PytestGoal()
    graph = build_graph(hitl_enabled=False)

    initial_state: AgentState = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": 3,
        "hitl_enabled": False,
        "model_name": "claude-sonnet-4-6",
        "cwd": str(passing_project),
        "run_id": "smoke-test-3",
        "total_tokens": 0,
    }
    run_config = {
        "configurable": {
            "thread_id": "smoke-test-3",
            "event_bus": bus,
            "goal": goal,
        }
    }

    events_seen: list[AgentEvent] = []

    async def consume():
        async for e in bus.iter_events(q):
            events_seen.append(e)

    consumer = asyncio.create_task(consume())
    with patch("retrai.agent.nodes.plan.get_llm", return_value=mock_llm):
        await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]
    await bus.close()
    await consumer

    kinds = {e.kind for e in events_seen}
    assert "step_start" in kinds
    assert "goal_check" in kinds
