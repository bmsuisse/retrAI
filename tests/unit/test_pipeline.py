"""Tests for the Pipeline runner."""

from __future__ import annotations

import pytest

from retrai.pipeline import PipelineResult, PipelineRunner, StepResult

# ---------------------------------------------------------------------------
# StepResult / PipelineResult data classes
# ---------------------------------------------------------------------------


class TestStepResult:
    def test_fields(self):
        sr = StepResult(
            goal_name="pytest",
            achieved=True,
            reason="All tests pass",
            iterations_used=3,
            tokens_used=1000,
            cost_usd=0.01,
            duration_seconds=12.5,
        )
        assert sr.goal_name == "pytest"
        assert sr.achieved is True
        assert sr.error is None

    def test_with_error(self):
        sr = StepResult(
            goal_name="pyright",
            achieved=False,
            reason="Crashed",
            iterations_used=0,
            tokens_used=0,
            cost_usd=0.0,
            duration_seconds=0.1,
            error="ImportError",
        )
        assert sr.error == "ImportError"
        assert sr.achieved is False


class TestPipelineResult:
    def test_empty(self):
        pr = PipelineResult()
        assert pr.passed == 0
        assert pr.failed == 0
        assert pr.status == "pending"

    def test_passed_and_failed(self):
        pr = PipelineResult(
            steps=[
                StepResult("a", True, "ok", 1, 100, 0.01, 1.0),
                StepResult("b", False, "fail", 2, 200, 0.02, 2.0),
                StepResult("c", True, "ok", 1, 50, 0.005, 0.5),
            ],
            status="partial",
        )
        assert pr.passed == 2
        assert pr.failed == 1


# ---------------------------------------------------------------------------
# PipelineRunner validation
# ---------------------------------------------------------------------------


class TestPipelineRunnerValidation:
    def test_unknown_goal_raises(self):
        with pytest.raises(ValueError, match="Unknown goal"):
            PipelineRunner(
                steps=["nonexistent_goal"],
                cwd="/tmp",
            )

    def test_valid_goals_accepted(self):
        runner = PipelineRunner(
            steps=["pytest"],
            cwd="/tmp",
        )
        assert runner.steps == ["pytest"]

    def test_multiple_goals(self):
        runner = PipelineRunner(
            steps=["pytest", "pyright"],
            cwd="/tmp",
        )
        assert len(runner.steps) == 2

    def test_continue_on_error_default(self):
        runner = PipelineRunner(
            steps=["pytest"],
            cwd="/tmp",
        )
        assert runner.continue_on_error is False

    def test_continue_on_error_set(self):
        runner = PipelineRunner(
            steps=["pytest"],
            cwd="/tmp",
            continue_on_error=True,
        )
        assert runner.continue_on_error is True
