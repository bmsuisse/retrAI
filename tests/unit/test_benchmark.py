"""Tests for the Benchmark runner."""

from __future__ import annotations

import pytest

from retrai.benchmark import (
    BenchmarkResult,
    BenchmarkRun,
    ModelScore,
    format_benchmark_table,
)

# ---------------------------------------------------------------------------
# BenchmarkRun
# ---------------------------------------------------------------------------


class TestBenchmarkRun:
    def test_fields(self):
        run = BenchmarkRun(
            model_name="claude-sonnet-4-6",
            round_num=1,
            achieved=True,
            iterations_used=5,
            tokens_used=2000,
            cost_usd=0.05,
            duration_seconds=30.0,
        )
        assert run.model_name == "claude-sonnet-4-6"
        assert run.achieved is True
        assert run.error is None

    def test_with_error(self):
        run = BenchmarkRun(
            model_name="gpt-4o",
            round_num=1,
            achieved=False,
            iterations_used=0,
            tokens_used=0,
            cost_usd=0.0,
            duration_seconds=0.1,
            error="API error",
        )
        assert run.error == "API error"


# ---------------------------------------------------------------------------
# ModelScore
# ---------------------------------------------------------------------------


class TestModelScore:
    def test_empty(self):
        ms = ModelScore(model_name="test")
        assert ms.success_rate == 0.0
        assert ms.avg_iterations == 0.0
        assert ms.avg_tokens == 0.0
        assert ms.total_cost == 0.0
        assert ms.avg_duration == 0.0

    def test_computed_properties(self):
        ms = ModelScore(
            model_name="claude-sonnet-4-6",
            runs=[
                BenchmarkRun("claude-sonnet-4-6", 1, True, 5, 1000, 0.01, 10.0),
                BenchmarkRun("claude-sonnet-4-6", 2, True, 3, 800, 0.008, 8.0),
                BenchmarkRun("claude-sonnet-4-6", 3, False, 10, 2000, 0.02, 20.0),
            ],
        )
        assert ms.success_rate == pytest.approx(2.0 / 3.0)
        assert ms.avg_iterations == pytest.approx(6.0)
        assert ms.avg_tokens == pytest.approx(1266.666, abs=1)
        assert ms.total_cost == pytest.approx(0.038)
        assert ms.avg_duration == pytest.approx(12.666, abs=1)

    def test_all_success(self):
        ms = ModelScore(
            model_name="test",
            runs=[
                BenchmarkRun("test", 1, True, 1, 100, 0.01, 1.0),
                BenchmarkRun("test", 2, True, 2, 200, 0.02, 2.0),
            ],
        )
        assert ms.success_rate == 1.0

    def test_all_failure(self):
        ms = ModelScore(
            model_name="test",
            runs=[
                BenchmarkRun("test", 1, False, 10, 500, 0.05, 5.0),
            ],
        )
        assert ms.success_rate == 0.0


# ---------------------------------------------------------------------------
# BenchmarkResult
# ---------------------------------------------------------------------------


class TestBenchmarkResult:
    def test_winner(self):
        result = BenchmarkResult(
            goal_name="pytest",
            models=[
                ModelScore(
                    "gpt-4o",
                    [BenchmarkRun("gpt-4o", 1, False, 10, 500, 0.05, 5.0)],
                ),
                ModelScore(
                    "claude-sonnet-4-6",
                    [BenchmarkRun("claude-sonnet-4-6", 1, True, 3, 1000, 0.01, 10.0)],
                ),
            ],
        )
        assert result.winner == "claude-sonnet-4-6"

    def test_winner_empty(self):
        result = BenchmarkResult(goal_name="pytest")
        assert result.winner is None

    def test_winner_tiebreak_by_iterations(self):
        result = BenchmarkResult(
            goal_name="pytest",
            models=[
                ModelScore(
                    "a",
                    [BenchmarkRun("a", 1, True, 10, 500, 0.05, 5.0)],
                ),
                ModelScore(
                    "b",
                    [BenchmarkRun("b", 1, True, 3, 500, 0.05, 5.0)],
                ),
            ],
        )
        # Both 100% success, b uses fewer iterations → winner
        assert result.winner == "b"


# ---------------------------------------------------------------------------
# format_benchmark_table
# ---------------------------------------------------------------------------


class TestFormatBenchmarkTable:
    def test_format(self):
        result = BenchmarkResult(
            goal_name="pytest",
            models=[
                ModelScore(
                    "gpt-4o",
                    [BenchmarkRun("gpt-4o", 1, True, 5, 1000, 0.01, 10.0)],
                ),
                ModelScore(
                    "claude-sonnet-4-6",
                    [BenchmarkRun("claude-sonnet-4-6", 1, True, 3, 800, 0.008, 8.0)],
                ),
            ],
        )
        table = format_benchmark_table(result)
        assert "pytest" in table
        assert "gpt-4o" in table
        assert "claude-sonnet-4-6" in table
        assert "🏆" in table
        assert "100%" in table
