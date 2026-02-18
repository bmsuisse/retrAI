"""Tests for AgentState structure and reducer behaviour."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from retrai.agent.state import AgentState, ToolCall, ToolResult


def _make_state(**overrides) -> AgentState:
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
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }
    base.update(overrides)  # type: ignore[typeddict-unknown-key]
    return base


def test_state_has_required_keys():
    state = _make_state()
    required = [
        "messages",
        "pending_tool_calls",
        "tool_results",
        "goal_achieved",
        "goal_reason",
        "iteration",
        "max_iterations",
        "hitl_enabled",
        "model_name",
        "cwd",
        "run_id",
    ]
    for key in required:
        assert key in state


def test_tool_call_fields():
    tc: ToolCall = {"id": "call-1", "name": "bash_exec", "args": {"command": "ls"}}
    assert tc["name"] == "bash_exec"
    assert tc["args"]["command"] == "ls"


def test_tool_result_fields():
    tr: ToolResult = {
        "tool_call_id": "call-1",
        "name": "bash_exec",
        "content": "output",
        "error": False,
    }
    assert tr["error"] is False
    assert tr["content"] == "output"


def test_state_messages_accept_various_types():
    state = _make_state(
        messages=[
            SystemMessage(content="system"),
            HumanMessage(content="human"),
            AIMessage(content="ai"),
        ]
    )
    assert len(state["messages"]) == 3
