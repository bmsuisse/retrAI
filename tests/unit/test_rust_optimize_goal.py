"""Tests for RustOptimizeGoal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from retrai.goals.rust_optimize_goal import (
    RustOptimizeGoal,
    _parse_criterion_output,
    _to_ns,
)


class TestToNs:
    def test_ns(self) -> None:
        assert _to_ns(100.0, "ns") == 100.0

    def test_us(self) -> None:
        assert _to_ns(1.0, "us") == 1_000.0

    def test_ms(self) -> None:
        assert _to_ns(1.0, "ms") == 1_000_000.0

    def test_s(self) -> None:
        assert _to_ns(1.0, "s") == 1_000_000_000.0

    def test_unknown_unit(self) -> None:
        assert _to_ns(42.0, "xyz") == 42.0


class TestParseCriterionOutput:
    def test_criterion_text_format(self) -> None:
        output = "sum_vec                 time:   [12.345 ns 12.456 ns 12.567 ns]\n"
        result = _parse_criterion_output(output, "sum_vec")
        assert result is not None
        assert abs(result - 12.456) < 0.01

    def test_libtest_format(self) -> None:
        output = "test sum_vec ... bench:         12,345 ns/iter (+/- 123)\n"
        result = _parse_criterion_output(output, "sum_vec")
        assert result is not None
        assert result == 12345.0

    def test_microsecond_unit(self) -> None:
        output = "my_bench                time:   [1.234 µs 1.256 µs 1.278 µs]\n"
        result = _parse_criterion_output(output, "my_bench")
        assert result is not None
        assert abs(result - 1256.0) < 1.0  # 1.256 µs = 1256 ns

    def test_no_match_returns_none(self) -> None:
        output = "some other output\n"
        result = _parse_criterion_output(output, "sum_vec")
        assert result is None

    def test_fuzzy_match(self) -> None:
        output = "sum_vec: 45.6 ns per iteration\n"
        result = _parse_criterion_output(output, "sum_vec")
        assert result is not None
        assert abs(result - 45.6) < 0.1


class TestRustOptimizeGoalCheck:
    @pytest.mark.asyncio
    async def test_no_bench_name_in_config(self, tmp_path: Path) -> None:
        goal = RustOptimizeGoal()
        state: dict = {}
        result = await goal.check(state, str(tmp_path))
        assert result.achieved is False
        assert "bench_name" in result.reason

    @pytest.mark.asyncio
    async def test_no_cargo_toml(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text("goal: rust-optimize\nbench_name: sum_vec\ntarget_ns: 100\n")
        goal = RustOptimizeGoal()
        state: dict = {}
        result = await goal.check(state, str(tmp_path))
        assert result.achieved is False
        assert "Cargo.toml" in result.reason

    @pytest.mark.asyncio
    async def test_target_achieved(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text(
            "goal: rust-optimize\nbench_name: sum_vec\ntarget_ns: 100\niterations: 1\n"
        )
        (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "sum_vec                 time:   [45.0 ns 48.0 ns 51.0 ns]\n"
        )
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            goal = RustOptimizeGoal()
            state: dict = {}
            result = await goal.check(state, str(tmp_path))

        assert result.achieved is True
        assert "Target reached" in result.reason

    @pytest.mark.asyncio
    async def test_target_not_achieved(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text(
            "goal: rust-optimize\nbench_name: sum_vec\ntarget_ns: 10\niterations: 1\n"
        )
        (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "sum_vec                 time:   [45.0 ns 48.0 ns 51.0 ns]\n"
        )
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            goal = RustOptimizeGoal()
            state: dict = {}
            result = await goal.check(state, str(tmp_path))

        assert result.achieved is False
        assert "Too slow" in result.reason

    @pytest.mark.asyncio
    async def test_cargo_bench_failure(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text(
            "goal: rust-optimize\nbench_name: sum_vec\ntarget_ns: 100\n"
        )
        (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\n")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error[E0308]: mismatched types"

        with patch("subprocess.run", return_value=mock_result):
            goal = RustOptimizeGoal()
            state: dict = {}
            result = await goal.check(state, str(tmp_path))

        assert result.achieved is False
        assert "failed" in result.reason.lower()


class TestRustOptimizeGoalSystemPrompt:
    def test_system_prompt_contains_key_terms(self) -> None:
        goal = RustOptimizeGoal()
        prompt = goal.system_prompt()
        assert "cargo bench" in prompt.lower()
        assert "ns/iter" in prompt

    def test_system_prompt_loads_config(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text(
            "goal: rust-optimize\nbench_name: my_bench\ntarget_ns: 50\n"
        )
        goal = RustOptimizeGoal()
        prompt = goal.system_prompt(str(tmp_path))
        assert "my_bench" in prompt
        assert "50" in prompt


class TestRustOptimizeGoalRegistry:
    def test_registered_in_registry(self) -> None:
        from retrai.goals.registry import get_goal

        goal = get_goal("rust-optimize")
        assert isinstance(goal, RustOptimizeGoal)
