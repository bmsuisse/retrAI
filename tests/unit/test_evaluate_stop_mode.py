"""Tests for soft/hard stop modes in the evaluate node."""

from __future__ import annotations

import pytest

from retrai.agent.nodes.evaluate import evaluate_node
from retrai.agent.state import AgentState


def _state(**overrides: object) -> AgentState:
    base: AgentState = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": 10,
        "stop_mode": "hard",
        "hitl_enabled": False,
        "model_name": "test-model",
        "cwd": "/tmp",
        "run_id": "test-run",
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }
    base.update(overrides)  # type: ignore[typeddict-unknown-key]
    return base


class _DummyGoal:
    async def check(
        self, state: AgentState, cwd: str
    ) -> object:
        class R:
            achieved = False
            reason = "Tests still failing"
            details: dict = {}
        return R()


class _AchievedGoal:
    async def check(
        self, state: AgentState, cwd: str
    ) -> object:
        class R:
            achieved = True
            reason = "All tests pass"
            details: dict = {}
        return R()


def _config(goal: object = None) -> dict:
    return {"configurable": {"event_bus": None, "goal": goal}}


# ── Hard stop (default) ───────────────────────────────────


@pytest.mark.asyncio
async def test_hard_stop_no_summary_on_penultimate():
    """Hard stop: no special message on penultimate iteration."""
    state = _state(iteration=8, max_iterations=10, stop_mode="hard")
    result = await evaluate_node(state, _config(_DummyGoal()))
    msg_content = result["messages"][0].content
    assert "SOFT STOP" not in msg_content
    assert "summary report" not in msg_content
    assert "Goal NOT YET achieved" in msg_content


@pytest.mark.asyncio
async def test_hard_stop_ends_at_max():
    """Hard stop: final iteration forces goal_achieved=False."""
    state = _state(iteration=9, max_iterations=10, stop_mode="hard")
    result = await evaluate_node(state, _config(_DummyGoal()))
    assert result["goal_achieved"] is False
    assert "Max iterations" in result["goal_reason"]
    msg_content = result["messages"][0].content
    assert "Max iterations reached" in msg_content


# ── Soft stop ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_stop_summary_on_penultimate():
    """Soft stop: penultimate iteration warns agent to write summary."""
    state = _state(iteration=8, max_iterations=10, stop_mode="soft")
    result = await evaluate_node(state, _config(_DummyGoal()))
    msg_content = result["messages"][0].content
    assert "SOFT STOP" in msg_content
    assert "summary report" in msg_content
    assert result["goal_achieved"] is False
    # The agent should still continue (not forced to end)
    assert "Max iterations" not in result["goal_reason"]


@pytest.mark.asyncio
async def test_soft_stop_ends_at_max():
    """Soft stop: final iteration forces stop just like hard."""
    state = _state(iteration=9, max_iterations=10, stop_mode="soft")
    result = await evaluate_node(state, _config(_DummyGoal()))
    assert result["goal_achieved"] is False
    assert "Max iterations" in result["goal_reason"]


@pytest.mark.asyncio
async def test_soft_stop_no_summary_when_not_penultimate():
    """Soft stop: regular iterations get normal message."""
    state = _state(iteration=5, max_iterations=10, stop_mode="soft")
    result = await evaluate_node(state, _config(_DummyGoal()))
    msg_content = result["messages"][0].content
    assert "SOFT STOP" not in msg_content
    assert "Goal NOT YET achieved" in msg_content


@pytest.mark.asyncio
async def test_soft_stop_achieved_skips_summary():
    """Soft stop: if goal is achieved, no summary prompt needed."""
    state = _state(iteration=8, max_iterations=10, stop_mode="soft")
    result = await evaluate_node(state, _config(_AchievedGoal()))
    msg_content = result["messages"][0].content
    assert "SOFT STOP" not in msg_content
    assert "ACHIEVED" in msg_content
    assert result["goal_achieved"] is True


# ── Default behavior ──────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_stop_mode_defaults_to_hard():
    """If stop_mode is missing from state, behave like hard stop."""
    state = _state(iteration=8, max_iterations=10)
    # Remove stop_mode to simulate old state
    del state["stop_mode"]  # type: ignore[misc]
    result = await evaluate_node(state, _config(_DummyGoal()))
    msg_content = result["messages"][0].content
    assert "SOFT STOP" not in msg_content
