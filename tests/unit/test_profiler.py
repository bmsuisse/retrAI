"""Tests for the profiler tool — cProfile and timeit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrai.tools.profiler import _build_profile_code, _build_timeit_code, profile_code


# ── _build_profile_code ───────────────────────────────────────────────────────


def test_build_profile_code_contains_cprofile() -> None:
    code = _build_profile_code("x = 1 + 1", top_n=5)
    assert "cProfile" in code
    assert "cumulative" in code


def test_build_timeit_code_contains_timeit() -> None:
    code = _build_timeit_code("1 + 1", setup="pass", number=100)
    assert "timeit" in code
    assert "best_time_ms" in code


# ── profile_code (sandbox) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_code_basic(tmp_path: Path) -> None:
    """Profile a simple loop and verify top_functions is present."""
    code = """
total = 0
for i in range(10000):
    total += i
"""
    result_str = await profile_code(
        action="profile_code",
        cwd=str(tmp_path),
        code=code,
        top_n=10,
    )
    result = json.loads(result_str)
    assert "top_functions" in result
    assert "total_time_ms" in result
    assert isinstance(result["top_functions"], list)


@pytest.mark.asyncio
async def test_profile_code_returns_numeric_times(tmp_path: Path) -> None:
    """All time values in top_functions should be numeric."""
    code = "sum(range(5000))"
    result_str = await profile_code(
        action="profile_code",
        cwd=str(tmp_path),
        code=code,
    )
    result = json.loads(result_str)
    for fn in result.get("top_functions", []):
        assert isinstance(fn["cumtime_ms"], (int, float))
        assert isinstance(fn["tottime_ms"], (int, float))


@pytest.mark.asyncio
async def test_profile_file(tmp_path: Path) -> None:
    """Profile a .py file and verify structured output."""
    script = tmp_path / "slow.py"
    script.write_text(
        "def work():\n"
        "    return sum(range(50000))\n"
        "if __name__ == '__main__':\n"
        "    work()\n"
    )
    result_str = await profile_code(
        action="profile_file",
        cwd=str(tmp_path),
        file_path=str(script),
        top_n=5,
    )
    result = json.loads(result_str)
    assert "top_functions" in result
    assert "total_time_ms" in result


# ── timeit ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeit_basic(tmp_path: Path) -> None:
    """timeit on a simple expression returns best_time_ms."""
    result_str = await profile_code(
        action="timeit",
        cwd=str(tmp_path),
        expression="1 + 1",
        number=1000,
    )
    result = json.loads(result_str)
    assert "best_time_ms" in result
    assert result["best_time_ms"] >= 0
    assert result["number"] == 1000


@pytest.mark.asyncio
async def test_timeit_auto_calibrate(tmp_path: Path) -> None:
    """timeit with number=0 auto-calibrates."""
    result_str = await profile_code(
        action="timeit",
        cwd=str(tmp_path),
        expression="sum(range(100))",
        number=0,
    )
    result = json.loads(result_str)
    assert "best_time_ms" in result
    assert result["number"] > 0  # auto-calibrated


@pytest.mark.asyncio
async def test_timeit_with_setup(tmp_path: Path) -> None:
    """timeit with setup code works correctly."""
    result_str = await profile_code(
        action="timeit",
        cwd=str(tmp_path),
        expression="sorted(data)",
        setup="import random; data = [random.random() for _ in range(100)]",
        number=100,
    )
    result = json.loads(result_str)
    assert "best_time_ms" in result


# ── Error handling ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_code_missing_code(tmp_path: Path) -> None:
    result_str = await profile_code(action="profile_code", cwd=str(tmp_path))
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_timeit_missing_expression(tmp_path: Path) -> None:
    result_str = await profile_code(action="timeit", cwd=str(tmp_path))
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_unknown_action(tmp_path: Path) -> None:
    result_str = await profile_code(action="unknown_action", cwd=str(tmp_path))
    result = json.loads(result_str)
    assert "error" in result
