"""Tests for rust_bench tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from retrai.tools.rust_bench import (
    _parse_bench_output,
    _parse_criterion_text,
    _parse_libtest,
    _to_ns,
    rust_bench,
)


class TestToNs:
    def test_ps(self) -> None:
        assert _to_ns(1000.0, "ps") == 1.0

    def test_ns(self) -> None:
        assert _to_ns(100.0, "ns") == 100.0

    def test_us(self) -> None:
        assert _to_ns(1.0, "us") == 1_000.0

    def test_ms(self) -> None:
        assert _to_ns(1.0, "ms") == 1_000_000.0

    def test_s(self) -> None:
        assert _to_ns(1.0, "s") == 1_000_000_000.0


class TestParseCriterionText:
    def test_basic_ns(self) -> None:
        output = "sum_vec                 time:   [12.345 ns 12.456 ns 12.567 ns]\n"
        results = _parse_criterion_text(output)
        assert len(results) == 1
        assert results[0]["name"] == "sum_vec"
        assert abs(results[0]["ns_per_iter"] - 12.456) < 0.01
        assert results[0]["source"] == "criterion_text"

    def test_microsecond(self) -> None:
        output = "my_bench                time:   [1.234 µs 1.256 µs 1.278 µs]\n"
        results = _parse_criterion_text(output)
        assert len(results) == 1
        assert abs(results[0]["ns_per_iter"] - 1256.0) < 1.0

    def test_multiple_benchmarks(self) -> None:
        output = (
            "bench_a                 time:   [10.0 ns 11.0 ns 12.0 ns]\n"
            "bench_b                 time:   [20.0 ns 21.0 ns 22.0 ns]\n"
        )
        results = _parse_criterion_text(output)
        assert len(results) == 2

    def test_no_match(self) -> None:
        output = "No benchmark output here\n"
        results = _parse_criterion_text(output)
        assert results == []


class TestParseLibtest:
    def test_basic(self) -> None:
        output = "test sum_vec ... bench:         12,345 ns/iter (+/- 123)\n"
        results = _parse_libtest(output)
        assert len(results) == 1
        assert results[0]["name"] == "sum_vec"
        assert results[0]["ns_per_iter"] == 12345.0
        assert results[0]["lower_bound_ns"] == 12222.0
        assert results[0]["upper_bound_ns"] == 12468.0

    def test_no_match(self) -> None:
        output = "No benchmark output\n"
        results = _parse_libtest(output)
        assert results == []


class TestParseBenchOutput:
    def test_prefers_criterion_text(self) -> None:
        output = "sum_vec                 time:   [12.0 ns 12.5 ns 13.0 ns]\n"
        results = _parse_bench_output(output)
        assert len(results) == 1
        assert results[0]["source"] == "criterion_text"

    def test_falls_back_to_libtest(self) -> None:
        output = "test sum_vec ... bench:         12,345 ns/iter (+/- 123)\n"
        results = _parse_bench_output(output)
        assert len(results) == 1
        assert results[0]["source"] == "libtest"

    def test_empty_output(self) -> None:
        results = _parse_bench_output("")
        assert results == []


class TestRustBenchTool:
    def test_schema(self) -> None:
        from retrai.tools.builtins import RustBenchTool

        tool = RustBenchTool()
        schema = tool.get_schema()
        assert schema.name == "rust_bench"
        assert "bench_name" in schema.parameters["properties"]
        assert schema.parameters["required"] == []

    def test_not_parallel_safe(self) -> None:
        from retrai.tools.builtins import RustBenchTool

        tool = RustBenchTool()
        assert tool.parallel_safe is False

    @pytest.mark.asyncio
    async def test_no_cargo_toml(self, tmp_path: Path) -> None:
        result = await rust_bench(bench_name="sum_vec", cwd=str(tmp_path))
        data = json.loads(result)
        assert "error" in data
        assert "Cargo.toml" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_bench(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\n")

        bench_output = "sum_vec                 time:   [45.0 ns 48.0 ns 51.0 ns]\n"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(bench_output.encode(), b"")
        )

        with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
            result = await rust_bench(bench_name="sum_vec", cwd=str(tmp_path))

        assert "sum_vec" in result
        assert "Benchmark Results" in result

    @pytest.mark.asyncio
    async def test_failed_bench(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"\n")

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"error[E0308]: mismatched types")
        )

        with patch("asyncio.create_subprocess_shell", return_value=mock_proc):
            result = await rust_bench(bench_name="sum_vec", cwd=str(tmp_path))

        data = json.loads(result)
        assert "error" in data
        assert "failed" in data["error"]
