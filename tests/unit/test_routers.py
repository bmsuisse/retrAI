"""Tests for graph routing functions."""

from __future__ import annotations

from retrai.agent.routers import (
    route_after_evaluate,
    route_after_human_check,
    should_call_tools,
)
from retrai.agent.state import AgentState


def _state(**overrides) -> AgentState:
    base: AgentState = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": 10,
        "hitl_enabled": False,
        "model_name": "claude-sonnet-4-6",
        "cwd": "/tmp",
        "run_id": "test-run",
        "total_tokens": 0,
    }
    base.update(overrides)  # type: ignore[typeddict-unknown-key]
    return base


# ── should_call_tools ─────────────────────────────────────────────────────────


def test_should_call_tools_with_pending():
    state = _state(pending_tool_calls=[{"id": "1", "name": "bash_exec", "args": {}}])
    assert should_call_tools(state) == "act"


def test_should_call_tools_empty():
    state = _state(pending_tool_calls=[])
    assert should_call_tools(state) == "evaluate"


# ── route_after_evaluate ──────────────────────────────────────────────────────


def test_route_after_evaluate_goal_achieved():
    state = _state(goal_achieved=True)
    assert route_after_evaluate(state) == "end"


def test_route_after_evaluate_max_iterations_reached():
    state = _state(goal_achieved=False, iteration=10, max_iterations=10)
    assert route_after_evaluate(state) == "end"


def test_route_after_evaluate_continue_no_hitl():
    state = _state(goal_achieved=False, iteration=3, max_iterations=10, hitl_enabled=False)
    assert route_after_evaluate(state) == "plan"


def test_route_after_evaluate_continue_with_hitl():
    state = _state(goal_achieved=False, iteration=3, max_iterations=10, hitl_enabled=True)
    assert route_after_evaluate(state) == "human_check"


def test_route_after_evaluate_exactly_at_max():
    state = _state(goal_achieved=False, iteration=10, max_iterations=10)
    assert route_after_evaluate(state) == "end"


def test_route_after_evaluate_one_before_max():
    state = _state(goal_achieved=False, iteration=9, max_iterations=10, hitl_enabled=False)
    assert route_after_evaluate(state) == "plan"


# ── route_after_human_check ───────────────────────────────────────────────────


def test_route_after_human_check_continues():
    state = _state(iteration=3, max_iterations=10)
    assert route_after_human_check(state) == "plan"


def test_route_after_human_check_max_iter():
    state = _state(iteration=10, max_iterations=10)
    assert route_after_human_check(state) == "end"
