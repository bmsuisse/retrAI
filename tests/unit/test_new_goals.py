"""Tests for new goals: docker-build, lint, db-migrate, and cost budget guard."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# DockerGoal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_goal_no_dockerfile(tmp_path):
    """DockerGoal returns achieved=False with a helpful message when no Dockerfile exists."""
    from retrai.goals.docker_goal import DockerGoal

    goal = DockerGoal()
    result = await goal.check({}, str(tmp_path))

    assert result.achieved is False
    assert "Dockerfile" in result.reason or "docker-compose" in result.reason


@pytest.mark.asyncio
async def test_docker_goal_system_prompt_no_docker(tmp_path):
    """DockerGoal system_prompt returns a non-empty string even with no Dockerfile."""
    from retrai.goals.docker_goal import DockerGoal

    goal = DockerGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "Docker" in prompt
    assert len(prompt) > 50


# ---------------------------------------------------------------------------
# LintGoal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lint_goal_no_linter(tmp_path):
    """LintGoal returns achieved=False with a helpful message when no linter config exists."""
    from retrai.goals.lint_goal import LintGoal

    goal = LintGoal()
    result = await goal.check({}, str(tmp_path))

    assert result.achieved is False
    assert "ruff" in result.reason.lower() or "eslint" in result.reason.lower()


@pytest.mark.asyncio
async def test_lint_goal_detects_ruff(tmp_path):
    """LintGoal detects ruff from .ruff.toml."""
    from retrai.goals.lint_goal import LintGoal, _detect_linter

    (tmp_path / ".ruff.toml").write_text("[lint]\nselect = ['E', 'F']\n")
    linter, cmd = _detect_linter(str(tmp_path), {})
    assert linter == "ruff"
    assert "ruff" in cmd


@pytest.mark.asyncio
async def test_lint_goal_detects_eslint(tmp_path):
    """LintGoal detects eslint from .eslintrc.json."""
    from retrai.goals.lint_goal import _detect_linter

    (tmp_path / ".eslintrc.json").write_text('{"rules": {}}')
    linter, cmd = _detect_linter(str(tmp_path), {})
    assert linter == "eslint"
    assert "eslint" in cmd


@pytest.mark.asyncio
async def test_lint_goal_custom_command(tmp_path):
    """LintGoal respects lint_command override in config."""
    from retrai.goals.lint_goal import _detect_linter

    linter, cmd = _detect_linter(str(tmp_path), {"lint_command": "flake8 ."})
    assert linter == "custom"
    assert cmd == ["flake8", "."]


@pytest.mark.asyncio
async def test_lint_goal_system_prompt(tmp_path):
    """LintGoal system_prompt returns a non-empty string."""
    from retrai.goals.lint_goal import LintGoal

    goal = LintGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "lint" in prompt.lower() or "violation" in prompt.lower()


# ---------------------------------------------------------------------------
# MigrationGoal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_goal_no_config(tmp_path):
    """MigrationGoal returns achieved=False with a helpful message when no migration config."""
    from retrai.goals.migration_goal import MigrationGoal

    goal = MigrationGoal()
    result = await goal.check({}, str(tmp_path))

    assert result.achieved is False
    assert "alembic" in result.reason.lower() or "prisma" in result.reason.lower()


@pytest.mark.asyncio
async def test_migration_goal_detects_alembic(tmp_path):
    """MigrationGoal detects alembic from alembic.ini."""
    from retrai.goals.migration_goal import _detect_migration_tool

    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = alembic\n")
    tool, cmd = _detect_migration_tool(str(tmp_path), {})
    assert tool == "alembic"
    assert "alembic" in cmd


@pytest.mark.asyncio
async def test_migration_goal_detects_prisma(tmp_path):
    """MigrationGoal detects prisma from prisma/schema.prisma."""
    from retrai.goals.migration_goal import _detect_migration_tool

    (tmp_path / "prisma").mkdir()
    (tmp_path / "prisma" / "schema.prisma").write_text("datasource db { provider = \"sqlite\" }")
    tool, cmd = _detect_migration_tool(str(tmp_path), {})
    assert tool == "prisma"
    assert "prisma" in cmd


@pytest.mark.asyncio
async def test_migration_goal_custom_command(tmp_path):
    """MigrationGoal respects migrate_command override in config."""
    from retrai.goals.migration_goal import _detect_migration_tool

    tool, cmd = _detect_migration_tool(str(tmp_path), {"migrate_command": "flask db upgrade"})
    assert tool == "custom"
    assert cmd == ["flask", "db", "upgrade"]


# ---------------------------------------------------------------------------
# Cost budget guard in evaluate_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_budget_not_exceeded():
    """evaluate_node does NOT abort when cost is below budget."""
    from unittest.mock import AsyncMock, MagicMock

    from retrai.agent.nodes.evaluate import evaluate_node

    mock_goal = MagicMock()
    mock_goal.check = AsyncMock(
        return_value=MagicMock(achieved=False, reason="not done", details={})
    )

    state = {
        "iteration": 1,
        "max_iterations": 10,
        "max_cost_usd": 1.0,
        "estimated_cost_usd": 0.50,
        "cwd": "/tmp",
        "run_id": "test-run",
        "stop_mode": "hard",
        "total_tokens": 100,
        "consecutive_failures": 0,
        "failed_strategies": [],
    }
    config = {"configurable": {"goal": mock_goal, "event_bus": None}}

    result = await evaluate_node(state, config)
    # Should NOT have budget-exceeded message
    assert "budget" not in result["goal_reason"].lower()


@pytest.mark.asyncio
async def test_cost_budget_exceeded():
    """evaluate_node aborts with a budget-exceeded message when cost >= max_cost_usd."""
    from unittest.mock import AsyncMock, MagicMock

    from retrai.agent.nodes.evaluate import evaluate_node

    mock_goal = MagicMock()
    mock_goal.check = AsyncMock(
        return_value=MagicMock(achieved=False, reason="not done", details={})
    )

    state = {
        "iteration": 1,
        "max_iterations": 10,
        "max_cost_usd": 0.10,
        "estimated_cost_usd": 0.15,  # exceeds budget
        "cwd": "/tmp",
        "run_id": "test-run",
        "stop_mode": "hard",
        "total_tokens": 100,
        "consecutive_failures": 0,
        "failed_strategies": [],
    }
    config = {"configurable": {"goal": mock_goal, "event_bus": None}}

    result = await evaluate_node(state, config)
    assert "budget" in result["goal_reason"].lower() or "cost" in result["goal_reason"].lower()
    assert result["goal_achieved"] is False


@pytest.mark.asyncio
async def test_cost_budget_zero_means_no_limit():
    """evaluate_node does NOT abort when max_cost_usd=0 (no limit)."""
    from unittest.mock import AsyncMock, MagicMock

    from retrai.agent.nodes.evaluate import evaluate_node

    mock_goal = MagicMock()
    mock_goal.check = AsyncMock(
        return_value=MagicMock(achieved=False, reason="not done", details={})
    )

    state = {
        "iteration": 1,
        "max_iterations": 10,
        "max_cost_usd": 0.0,  # no limit
        "estimated_cost_usd": 999.99,
        "cwd": "/tmp",
        "run_id": "test-run",
        "stop_mode": "hard",
        "total_tokens": 100,
        "consecutive_failures": 0,
        "failed_strategies": [],
    }
    config = {"configurable": {"goal": mock_goal, "event_bus": None}}

    result = await evaluate_node(state, config)
    assert "budget" not in result["goal_reason"].lower()


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def test_detector_finds_docker(tmp_path):
    """detect_goal returns 'docker-build' for a project with a Dockerfile."""
    from retrai.goals.detector import detect_goal

    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    result = detect_goal(str(tmp_path))
    assert result == "docker-build"


def test_detector_finds_lint_ruff(tmp_path):
    """detect_goal returns 'lint' for a project with .ruff.toml."""
    from retrai.goals.detector import detect_goal

    (tmp_path / ".ruff.toml").write_text("[lint]\n")
    result = detect_goal(str(tmp_path))
    assert result == "lint"


def test_detector_finds_migration_alembic(tmp_path):
    """detect_goal returns 'db-migrate' for a project with alembic.ini."""
    from retrai.goals.detector import detect_goal

    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    result = detect_goal(str(tmp_path))
    assert result == "db-migrate"
