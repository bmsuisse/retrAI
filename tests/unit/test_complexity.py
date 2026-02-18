"""Tests for the complexity tool — cyclomatic complexity, Halstead, nested loops."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrai.tools.complexity import (
    _cc_rank,
    _cyclomatic_complexity,
    _detect_nested_loops,
    _halstead_metrics,
    analyze_complexity,
)

# ── _detect_nested_loops ──────────────────────────────────────────────────────


def test_no_nested_loops_single_loop() -> None:
    source = """
def process(items):
    for item in items:
        print(item)
"""
    findings = _detect_nested_loops(source)
    assert findings == []


def test_nested_loops_detected() -> None:
    source = """
def find_pairs(items):
    for i in items:
        for j in items:
            if i != j:
                print(i, j)
"""
    findings = _detect_nested_loops(source)
    assert len(findings) >= 1
    assert any("depth" in f and f["depth"] >= 2 for f in findings)


def test_triple_nested_loop() -> None:
    source = """
def matrix_multiply(a, b, c):
    for i in a:
        for j in b:
            for k in c:
                pass
"""
    findings = _detect_nested_loops(source)
    # Should detect depth 2 and depth 3
    depths = [f["depth"] for f in findings if "depth" in f]
    assert max(depths) >= 3


def test_nested_loops_in_module_scope() -> None:
    source = """
for i in range(10):
    for j in range(10):
        pass
"""
    findings = _detect_nested_loops(source)
    assert len(findings) >= 1


def test_nested_loops_invalid_syntax() -> None:
    source = "def foo(: pass"
    findings = _detect_nested_loops(source)
    assert any("error" in f for f in findings)


def test_while_nested_in_for() -> None:
    source = """
def process(items):
    for item in items:
        while True:
            break
"""
    findings = _detect_nested_loops(source)
    assert len(findings) >= 1


# ── _cyclomatic_complexity ────────────────────────────────────────────────────


_RADON_MISSING = False
try:
    import radon  # noqa: F401
except ImportError:
    _RADON_MISSING = True

skip_radon = pytest.mark.skipif(_RADON_MISSING, reason="radon not installed")


@skip_radon
def test_cyclomatic_simple_function() -> None:
    """A function with no branches has CC=1."""
    source = """
def greet(name):
    return f"Hello, {name}"
"""
    results = _cyclomatic_complexity(source)
    assert len(results) == 1
    assert results[0]["name"] == "greet"
    assert results[0]["complexity"] == 1
    assert results[0]["rank"] == "A"
    assert results[0]["flagged"] is False


@skip_radon
def test_cyclomatic_complex_function() -> None:
    """A function with many branches has higher CC."""
    source = """
def classify(x):
    if x < 0:
        return "negative"
    elif x == 0:
        return "zero"
    elif x < 10:
        return "small"
    elif x < 100:
        return "medium"
    elif x < 1000:
        return "large"
    else:
        return "huge"
"""
    results = _cyclomatic_complexity(source)
    assert len(results) == 1
    assert results[0]["complexity"] >= 6


@skip_radon
def test_cyclomatic_flagged_above_threshold() -> None:
    """Functions with CC > 10 are flagged."""
    # Build a function with many branches
    branches = "\n".join(f"    elif x == {i}: return {i}" for i in range(12))
    source = f"def complex_fn(x):\n    if x == 0: return 0\n{branches}\n    else: return -1\n"
    results = _cyclomatic_complexity(source)
    assert len(results) == 1
    assert results[0]["flagged"] is True


# ── _cc_rank ──────────────────────────────────────────────────────────────────


def test_cc_rank_a() -> None:
    assert _cc_rank(1) == "A"
    assert _cc_rank(5) == "A"


def test_cc_rank_b() -> None:
    assert _cc_rank(6) == "B"
    assert _cc_rank(10) == "B"


def test_cc_rank_f() -> None:
    assert _cc_rank(26) == "F"


# ── _halstead_metrics ─────────────────────────────────────────────────────────


@skip_radon
def test_halstead_basic() -> None:
    source = """
def add(a, b):
    return a + b
"""
    result = _halstead_metrics(source)
    assert "functions" in result
    assert len(result["functions"]) >= 1
    fn = result["functions"][0]
    assert "volume" in fn
    assert "difficulty" in fn
    assert fn["volume"] > 0


@skip_radon
def test_halstead_empty_source() -> None:
    result = _halstead_metrics("")
    # Either empty functions list or an error
    assert "functions" in result or "error" in result


# ── analyze_complexity (async) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_nested_loops_action(tmp_path: Path) -> None:
    source = """
def slow(items):
    for i in items:
        for j in items:
            pass
"""
    result_str = await analyze_complexity(
        action="nested_loops",
        cwd=str(tmp_path),
        source=source,
    )
    result = json.loads(result_str)
    assert result["action"] == "nested_loops"
    assert result["has_nested_loops"] is True
    assert result["count"] >= 1


@pytest.mark.asyncio
async def test_analyze_no_nested_loops(tmp_path: Path) -> None:
    source = """
def fast(items):
    return [x * 2 for x in items]
"""
    result_str = await analyze_complexity(
        action="nested_loops",
        cwd=str(tmp_path),
        source=source,
    )
    result = json.loads(result_str)
    assert result["has_nested_loops"] is False


@pytest.mark.asyncio
async def test_analyze_from_file(tmp_path: Path) -> None:
    """analyze_complexity reads from file_path."""
    py_file = tmp_path / "code.py"
    py_file.write_text(
        "def foo(x):\n"
        "    for i in x:\n"
        "        for j in x:\n"
        "            pass\n"
    )
    result_str = await analyze_complexity(
        action="nested_loops",
        cwd=str(tmp_path),
        file_path="code.py",
    )
    result = json.loads(result_str)
    assert result["has_nested_loops"] is True


@pytest.mark.asyncio
async def test_analyze_missing_source(tmp_path: Path) -> None:
    result_str = await analyze_complexity(action="nested_loops", cwd=str(tmp_path))
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_analyze_unknown_action(tmp_path: Path) -> None:
    result_str = await analyze_complexity(
        action="unknown",
        cwd=str(tmp_path),
        source="x = 1",
    )
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
@skip_radon
async def test_analyze_summary_action(tmp_path: Path) -> None:
    source = """
def simple(x):
    return x + 1

def nested(items):
    for i in items:
        for j in items:
            pass
"""
    result_str = await analyze_complexity(
        action="summary",
        cwd=str(tmp_path),
        source=source,
    )
    result = json.loads(result_str)
    assert result["action"] == "summary"
    assert "cyclomatic" in result
    assert "nested_loops" in result
    assert "halstead" in result
    assert "issues" in result
