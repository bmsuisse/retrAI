"""Tests for goal implementations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from retrai.goals.base import GoalBase, GoalResult
from retrai.goals.perf_goal import PerfCheckGoal
from retrai.goals.pytest_goal import PytestGoal, _extract_failures
from retrai.goals.registry import get_goal, list_goals
from retrai.goals.shell_goal import ShellGoal
from retrai.goals.sql_goal import SqlBenchmarkGoal

# ── GoalBase ──────────────────────────────────────────────────────────────────


def test_goal_result_fields():
    r = GoalResult(achieved=True, reason="done", details={"k": "v"})
    assert r.achieved is True
    assert r.reason == "done"
    assert r.details == {"k": "v"}


def test_goal_base_is_abstract():
    with pytest.raises(TypeError):
        GoalBase()  # type: ignore[abstract]


# ── Registry ──────────────────────────────────────────────────────────────────


def test_list_goals_returns_known_goals():
    goals = list_goals()
    assert "pytest" in goals
    assert "shell-goal" in goals
    assert "perf-check" in goals
    assert "sql-benchmark" in goals
    # Non-coding / LLM-scored goals
    assert "text-improve" in goals
    assert "creative" in goals
    assert "score" in goals


def test_get_goal_returns_correct_instance():
    g = get_goal("pytest")
    assert isinstance(g, PytestGoal)


def test_get_goal_raises_for_unknown():
    with pytest.raises(KeyError, match="Unknown goal"):
        get_goal("nonexistent-goal-xyz")


# ── PytestGoal ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pytest_goal_passes_on_passing_project(passing_project: Path):
    goal = PytestGoal()
    result = await goal.check({}, str(passing_project))
    assert result.achieved is True
    assert "passed" in result.reason.lower()


@pytest.mark.asyncio
async def test_pytest_goal_fails_on_failing_project(failing_project: Path):
    goal = PytestGoal()
    result = await goal.check({}, str(failing_project))
    assert result.achieved is False
    assert "failed" in result.reason.lower() or "1" in result.reason


@pytest.mark.asyncio
async def test_pytest_goal_handles_timeout(tmp_path: Path):
    goal = PytestGoal()
    # Patch subprocess.run to raise TimeoutExpired
    with patch("retrai.goals.pytest_goal.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=120)
        result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "timed out" in result.reason.lower()


@pytest.mark.asyncio
async def test_pytest_goal_handles_missing_pytest(tmp_path: Path):
    goal = PytestGoal()
    with patch("retrai.goals.pytest_goal.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("pytest not found")
        result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "not found" in result.reason.lower()


def test_extract_failures_empty():
    assert _extract_failures({}) == []


def test_extract_failures_with_data():
    report = {
        "tests": [
            {
                "nodeid": "test_a.py::test_x",
                "outcome": "failed",
                "call": {"longrepr": "AssertionError"},
            },
            {"nodeid": "test_a.py::test_y", "outcome": "passed"},
        ]
    }
    failures = _extract_failures(report)
    assert len(failures) == 1
    assert failures[0]["nodeid"] == "test_a.py::test_x"
    assert failures[0]["longrepr"] == "AssertionError"


def test_pytest_goal_system_prompt_contains_strategy():
    goal = PytestGoal()
    prompt = goal.system_prompt()
    assert "pytest" in prompt.lower()
    assert "fix" in prompt.lower() or "pass" in prompt.lower()


# ── ShellGoal ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shell_goal_succeeds_with_exit_0(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: shell-goal\ncheck_command: 'echo OK'\nsuccess_condition:\n  exit_code: 0\n"
    )
    goal = ShellGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is True


@pytest.mark.asyncio
async def test_shell_goal_fails_on_nonzero_exit(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: shell-goal\ncheck_command: 'exit 1'\nsuccess_condition:\n  exit_code: 0\n"
    )
    goal = ShellGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False


@pytest.mark.asyncio
async def test_shell_goal_output_contains_check(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: shell-goal\ncheck_command: 'echo PASS'\n"
        "success_condition:\n  exit_code: 0\n  output_contains: PASS\n"
    )
    goal = ShellGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is True


@pytest.mark.asyncio
async def test_shell_goal_output_missing_string_fails(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: shell-goal\ncheck_command: 'echo FAIL'\n"
        "success_condition:\n  exit_code: 0\n  output_contains: PASS\n"
    )
    goal = ShellGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "PASS" in result.reason


@pytest.mark.asyncio
async def test_shell_goal_max_seconds_too_slow(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: shell-goal\ncheck_command: 'echo hi'\n"
        "success_condition:\n  exit_code: 0\n  max_seconds: 0.00001\n"
    )
    goal = ShellGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "slow" in result.reason.lower() or "s" in result.reason


def test_shell_goal_system_prompt_no_config(tmp_path: Path):
    goal = ShellGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "make" in prompt.lower() or "command" in prompt.lower()


def test_shell_goal_system_prompt_with_custom(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: shell-goal\ncheck_command: 'make lint'\nsystem_prompt: 'Fix all linting errors.'\n"
    )
    goal = ShellGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "Fix all linting errors" in prompt


# ── PerfCheckGoal ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_perf_goal_fast_command_passes(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: perf-check\ncheck_command: 'echo fast'\nmax_seconds: 10\n"
    )
    goal = PerfCheckGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is True


@pytest.mark.asyncio
async def test_perf_goal_slow_command_fails(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: perf-check\ncheck_command: 'echo done'\nmax_seconds: 0.000001\n"
    )
    goal = PerfCheckGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    # Either "too slow" or "timed out" — both mean the time limit was exceeded
    assert "slow" in result.reason.lower() or "timed out" in result.reason.lower()


@pytest.mark.asyncio
async def test_perf_goal_nonzero_exit_fails(tmp_path: Path):
    (tmp_path / ".retrai.yml").write_text(
        "goal: perf-check\n"
        "check_command: 'python -c \"import sys; sys.exit(1)\"'\n"
        "max_seconds: 10\n"
    )
    goal = PerfCheckGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "code 1" in result.reason or "exit" in result.reason.lower()


# ── SqlBenchmarkGoal ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sql_goal_missing_dsn(tmp_path: Path):
    goal = SqlBenchmarkGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "dsn" in result.reason.lower()


@pytest.mark.asyncio
async def test_sql_goal_sqlite_fast_query(tmp_path: Path):
    pytest.importorskip("sqlalchemy")
    db_path = tmp_path / "test.db"
    (tmp_path / ".retrai.yml").write_text(
        f"goal: sql-benchmark\ndsn: 'sqlite:///{db_path}'\nquery: 'SELECT 1'\nmax_ms: 5000\n"
    )
    goal = SqlBenchmarkGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is True


@pytest.mark.asyncio
async def test_sql_goal_sqlite_too_slow(tmp_path: Path):
    pytest.importorskip("sqlalchemy")
    db_path = tmp_path / "test.db"
    (tmp_path / ".retrai.yml").write_text(
        f"goal: sql-benchmark\ndsn: 'sqlite:///{db_path}'\nquery: 'SELECT 1'\nmax_ms: 0.000001\n"
    )
    goal = SqlBenchmarkGoal()
    result = await goal.check({}, str(tmp_path))
    assert result.achieved is False
    assert "ms" in result.reason
