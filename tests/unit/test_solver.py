"""Tests for SolverGoal — LLM-as-judge evaluation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from retrai.goals.solver import SolverGoal

# ── System prompt ────────────────────────────────────────────


def test_solver_system_prompt():
    goal = SolverGoal(description="add input validation")
    prompt = goal.system_prompt()
    assert "add input validation" in prompt
    assert "Goal" in prompt
    assert "Strategy" in prompt


def test_solver_name():
    goal = SolverGoal(description="test")
    assert goal.name == "solve"


# ── Evaluation behavior ─────────────────────────────────────


@pytest.mark.asyncio
async def test_solver_skips_first_iteration():
    """On iteration 0, solver should not call the LLM judge."""
    goal = SolverGoal(description="fix the bug")
    state = {"iteration": 0, "model_name": "test-model"}
    result = await goal.check(state, "/tmp")
    assert result.achieved is False
    assert "Initial" in result.reason


@pytest.mark.asyncio
async def test_solver_needs_diff():
    """If no git diff, solver should report no changes."""
    goal = SolverGoal(description="fix the bug")
    state = {"iteration": 2, "model_name": "test-model"}

    with patch.object(goal, "_get_diff", new_callable=AsyncMock) as mock_diff:
        mock_diff.return_value = ""
        result = await goal.check(state, "/tmp")

    assert result.achieved is False
    assert "No changes" in result.reason


@pytest.mark.asyncio
async def test_solver_calls_judge_with_diff():
    """When there are changes, solver should call the LLM judge."""
    goal = SolverGoal(description="add a hello world function")
    state = {"iteration": 2, "model_name": "test-model"}

    judge_response = json.dumps(
        {
            "achieved": True,
            "reason": "A hello_world function was added to main.py",
            "confidence": 0.95,
        }
    )

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = judge_response
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with (
        patch.object(goal, "_get_diff", new_callable=AsyncMock) as mock_diff,
        patch("retrai.llm.factory.get_llm", return_value=mock_llm),
    ):
        mock_diff.return_value = "+def hello_world():\n+    return 'Hello, World!'\n"
        result = await goal.check(state, "/tmp")

    assert result.achieved is True
    assert "hello_world" in result.reason
    assert result.details["confidence"] == 0.95


@pytest.mark.asyncio
async def test_solver_handles_judge_failure():
    """If the judge LLM fails, solver should not crash."""
    goal = SolverGoal(description="fix something")
    state = {"iteration": 2, "model_name": "test-model"}

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with (
        patch.object(goal, "_get_diff", new_callable=AsyncMock) as mock_diff,
        patch("retrai.llm.factory.get_llm", return_value=mock_llm),
    ):
        mock_diff.return_value = "+some change\n"
        result = await goal.check(state, "/tmp")

    assert result.achieved is False
    assert "failed" in result.reason.lower()


@pytest.mark.asyncio
async def test_solver_handles_malformed_judge_response():
    """If the judge returns invalid JSON, solver should handle gracefully."""
    goal = SolverGoal(description="fix something")
    state = {"iteration": 2, "model_name": "test-model"}

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "This is not JSON at all"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with (
        patch.object(goal, "_get_diff", new_callable=AsyncMock) as mock_diff,
        patch("retrai.llm.factory.get_llm", return_value=mock_llm),
    ):
        mock_diff.return_value = "+some change\n"
        result = await goal.check(state, "/tmp")

    assert result.achieved is False  # Should fail gracefully
