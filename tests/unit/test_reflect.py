"""Tests for the reflect node — stuck detection and strategy shifting."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from retrai.agent.nodes.reflect import (
    _build_reflection_message,
    _detect_stuck_pattern,
    _extract_recent_failures,
    reflect_node,
)
from retrai.agent.state import AgentState


def _make_state(**overrides: object) -> AgentState:
    base: AgentState = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 5,
        "max_iterations": 10,
        "hitl_enabled": False,
        "model_name": "test-model",
        "cwd": "/tmp",
        "run_id": "test-reflect",
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }
    base.update(overrides)  # type: ignore[typeddict-unknown-key]
    return base


# ── Stuck detection ──────────────────────────────────────────


def test_detect_stuck_no_failures():
    assert _detect_stuck_pattern([]) is False


def test_detect_stuck_single_failure():
    assert _detect_stuck_pattern(["Something failed"]) is False


def test_detect_stuck_different_failures():
    failures = [
        "The parser could not read input file format ABC",
        "The database connection was refused on port 5432",
    ]
    assert _detect_stuck_pattern(failures) is False


def test_detect_stuck_similar_failures():
    failures = [
        "Goal NOT YET achieved: test_add failed with AssertionError expected 3 got 1",
        "Goal NOT YET achieved: test_add failed with AssertionError expected 3 got 2",
    ]
    assert _detect_stuck_pattern(failures) is True


# ── Failure extraction ───────────────────────────────────────


def test_extract_recent_failures_empty():
    state = _make_state()
    assert _extract_recent_failures(state) == []


def test_extract_recent_failures_finds_goal_messages():
    state = _make_state(
        messages=[
            HumanMessage(content="fix the bug"),
            HumanMessage(content="Goal NOT YET achieved: 2 tests failed"),
            HumanMessage(content="I'll try a different approach"),
            HumanMessage(content="Goal NOT YET achieved: 1 test failed"),
        ]
    )
    failures = _extract_recent_failures(state)
    assert len(failures) == 2
    assert "2 tests failed" in failures[0]


# ── Reflection message ───────────────────────────────────────


def test_reflection_message_basic():
    msg = _build_reflection_message(
        recent_failures=["test failed"],
        failed_strategies=[],
        consecutive_failures=2,
    )
    assert "REFLECTION" in msg
    assert "2 consecutive" in msg


def test_reflection_message_with_failed_strategies():
    msg = _build_reflection_message(
        recent_failures=["test failed"],
        failed_strategies=["tried editing calc.py"],
        consecutive_failures=3,
    )
    assert "DO NOT repeat" in msg
    assert "tried editing calc.py" in msg


def test_reflection_message_critical_escalation():
    msg = _build_reflection_message(
        recent_failures=["test still failing"],
        failed_strategies=["approach A", "approach B"],
        consecutive_failures=5,
    )
    assert "CRITICAL" in msg


# ── Reflect node ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reflect_node_skips_when_few_failures():
    """With < 2 consecutive failures, reflect should pass through."""
    state = _make_state(consecutive_failures=1)
    config = {"configurable": {"event_bus": None}}
    result = await reflect_node(state, config)
    # Should not inject any messages
    assert "messages" not in result


@pytest.mark.asyncio
async def test_reflect_node_injects_when_stuck():
    """With 2+ consecutive failures and similar errors, reflect should inject a message."""
    state = _make_state(
        consecutive_failures=3,
        messages=[
            HumanMessage(content="Goal NOT YET achieved: test_add failed assertion"),
            HumanMessage(content="Goal NOT YET achieved: test_add failed assertion"),
        ],
    )
    config = {"configurable": {"event_bus": None}}
    result = await reflect_node(state, config)
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert "REFLECTION" in str(result["messages"][0].content)
