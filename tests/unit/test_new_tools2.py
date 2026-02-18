"""Tests for memory_profile, benchmark_compare, and dependency_graph tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrai.tools.benchmark_compare import benchmark_compare
from retrai.tools.dependency_graph import (
    _build_call_graph,
    _build_import_graph,
    _detect_cycles,
    _to_mermaid,
    dependency_graph,
)
from retrai.tools.memory_profile import memory_profile


# ══════════════════════════════════════════════════════════════════════════════
# memory_profile
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_memory_profile_basic(tmp_path: Path) -> None:
    """Profile a simple allocation and verify top_allocations is present."""
    code = "data = [i for i in range(10000)]"
    result_str = await memory_profile(
        action="profile_code",
        cwd=str(tmp_path),
        code=code,
        top_n=5,
    )
    result = json.loads(result_str)
    assert "top_allocations" in result
    assert "total_traced_kb" in result
    assert isinstance(result["top_allocations"], list)


@pytest.mark.asyncio
async def test_memory_profile_file(tmp_path: Path) -> None:
    """Profile a .py file and verify structured output."""
    script = tmp_path / "alloc.py"
    script.write_text(
        "if __name__ == '__main__':\n"
        "    data = [i * 2 for i in range(50000)]\n"
    )
    result_str = await memory_profile(
        action="profile_file",
        cwd=str(tmp_path),
        file_path=str(script),
        top_n=5,
    )
    result = json.loads(result_str)
    assert "top_allocations" in result
    assert result["total_traced_kb"] >= 0


@pytest.mark.asyncio
async def test_memory_profile_compare(tmp_path: Path) -> None:
    """Compare two snippets — list vs generator."""
    code_a = "x = list(range(100000))"
    code_b = "x = sum(range(100000))"  # generator, much less memory
    result_str = await memory_profile(
        action="compare",
        cwd=str(tmp_path),
        code_a=code_a,
        code_b=code_b,
    )
    result = json.loads(result_str)
    assert "peak_a_kb" in result
    assert "peak_b_kb" in result
    assert "verdict" in result
    assert result["peak_a_kb"] >= 0
    assert result["peak_b_kb"] >= 0


@pytest.mark.asyncio
async def test_memory_profile_missing_code(tmp_path: Path) -> None:
    result_str = await memory_profile(action="profile_code", cwd=str(tmp_path))
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_memory_profile_unknown_action(tmp_path: Path) -> None:
    result_str = await memory_profile(action="unknown", cwd=str(tmp_path), code="x=1")
    result = json.loads(result_str)
    assert "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# benchmark_compare
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_benchmark_compare_basic(tmp_path: Path) -> None:
    """Compare list comprehension vs loop — both should produce structured output."""
    result_str = await benchmark_compare(
        code_a="result = [i * 2 for i in range(1000)]",
        code_b="result = list(map(lambda x: x * 2, range(1000)))",
        cwd=str(tmp_path),
        label_a="listcomp",
        label_b="map",
        number=100,
    )
    result = json.loads(result_str)
    assert "listcomp" in result
    assert "map" in result
    assert "speedup" in result
    assert "verdict" in result
    assert result["listcomp"]["best_ms"] >= 0
    assert result["map"]["best_ms"] >= 0


@pytest.mark.asyncio
async def test_benchmark_compare_with_setup(tmp_path: Path) -> None:
    """Compare with shared setup code."""
    result_str = await benchmark_compare(
        setup="data = list(range(1000))",
        code_a="sorted(data)",
        code_b="sorted(data, reverse=True)",
        cwd=str(tmp_path),
        number=50,
    )
    result = json.loads(result_str)
    assert "baseline" in result
    assert "candidate" in result
    assert result["speedup"] > 0


@pytest.mark.asyncio
async def test_benchmark_compare_missing_code(tmp_path: Path) -> None:
    result_str = await benchmark_compare(
        code_a="",
        code_b="x = 1",
        cwd=str(tmp_path),
    )
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_benchmark_compare_memory_ratio(tmp_path: Path) -> None:
    """Memory ratio should be present and positive."""
    result_str = await benchmark_compare(
        code_a="x = list(range(1000))",
        code_b="x = tuple(range(1000))",
        cwd=str(tmp_path),
        number=10,
    )
    result = json.loads(result_str)
    assert "memory_ratio" in result


# ══════════════════════════════════════════════════════════════════════════════
# dependency_graph — _build_call_graph
# ══════════════════════════════════════════════════════════════════════════════


def test_call_graph_basic() -> None:
    source = """
def foo():
    bar()
    baz()

def bar():
    pass

def baz():
    bar()
"""
    graph = _build_call_graph(source)
    assert "foo" in graph
    assert "bar" in graph["foo"]
    assert "baz" in graph["foo"]
    assert "bar" in graph["baz"]


def test_call_graph_no_functions() -> None:
    source = "x = 1 + 2\nprint(x)\n"
    graph = _build_call_graph(source)
    assert graph == {}


def test_call_graph_invalid_syntax() -> None:
    source = "def foo(: pass"
    graph = _build_call_graph(source)
    assert "__error__" in graph


def test_call_graph_async_function() -> None:
    source = """
async def fetch():
    await process()

async def process():
    pass
"""
    graph = _build_call_graph(source)
    assert "fetch" in graph
    assert "process" in graph["fetch"]


# ══════════════════════════════════════════════════════════════════════════════
# dependency_graph — _build_import_graph
# ══════════════════════════════════════════════════════════════════════════════


def test_import_graph_basic(tmp_path: Path) -> None:
    """Build import graph for a simple package."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("from mypkg import utils\n")
    (pkg / "utils.py").write_text("def helper(): pass\n")
    (pkg / "main.py").write_text("from mypkg import utils\n")

    graph = _build_import_graph(pkg, max_depth=3)
    # Should have edges from __init__ and main to utils
    assert isinstance(graph, dict)


def test_import_graph_empty_package(tmp_path: Path) -> None:
    pkg = tmp_path / "empty"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    graph = _build_import_graph(pkg, max_depth=3)
    assert isinstance(graph, dict)


# ══════════════════════════════════════════════════════════════════════════════
# dependency_graph — _detect_cycles
# ══════════════════════════════════════════════════════════════════════════════


def test_detect_cycles_simple() -> None:
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycles = _detect_cycles(graph)
    assert len(cycles) >= 1
    # Cycle should contain a, b, c
    cycle_nodes = {n for cycle in cycles for n in cycle}
    assert "a" in cycle_nodes or "b" in cycle_nodes


def test_detect_cycles_no_cycle() -> None:
    graph = {"a": ["b"], "b": ["c"], "c": []}
    cycles = _detect_cycles(graph)
    assert cycles == []


def test_detect_cycles_self_loop() -> None:
    graph = {"a": ["a"]}
    cycles = _detect_cycles(graph)
    assert len(cycles) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# dependency_graph — _to_mermaid
# ══════════════════════════════════════════════════════════════════════════════


def test_to_mermaid_basic() -> None:
    graph = {"a": ["b", "c"], "b": ["c"]}
    diagram = _to_mermaid(graph)
    assert "graph TD" in diagram
    assert "-->" in diagram


def test_to_mermaid_empty() -> None:
    diagram = _to_mermaid({})
    assert "graph TD" in diagram


# ══════════════════════════════════════════════════════════════════════════════
# dependency_graph — async wrapper
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_dependency_graph_calls(tmp_path: Path) -> None:
    """Test 'calls' action on a .py file."""
    py_file = tmp_path / "code.py"
    py_file.write_text(
        "def foo():\n"
        "    bar()\n"
        "\n"
        "def bar():\n"
        "    pass\n"
    )
    result_str = await dependency_graph(
        action="calls",
        path="code.py",
        cwd=str(tmp_path),
    )
    result = json.loads(result_str)
    assert result["action"] == "calls"
    assert "graph" in result
    assert "foo" in result["graph"]


@pytest.mark.asyncio
async def test_dependency_graph_calls_mermaid(tmp_path: Path) -> None:
    py_file = tmp_path / "code.py"
    py_file.write_text("def foo():\n    bar()\ndef bar():\n    pass\n")
    result_str = await dependency_graph(
        action="calls",
        path="code.py",
        cwd=str(tmp_path),
        fmt="mermaid",
    )
    result = json.loads(result_str)
    assert "diagram" in result
    assert "graph TD" in result["diagram"]


@pytest.mark.asyncio
async def test_dependency_graph_imports(tmp_path: Path) -> None:
    """Test 'imports' action on a package."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("from mypkg import utils\n")
    (pkg / "utils.py").write_text("def helper(): pass\n")

    result_str = await dependency_graph(
        action="imports",
        path="mypkg",
        cwd=str(tmp_path),
    )
    result = json.loads(result_str)
    assert result["action"] == "imports"
    assert "graph" in result


@pytest.mark.asyncio
async def test_dependency_graph_cycles(tmp_path: Path) -> None:
    """Test 'cycles' action."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from mypkg import b\n")
    (pkg / "b.py").write_text("from mypkg import a\n")

    result_str = await dependency_graph(
        action="cycles",
        path="mypkg",
        cwd=str(tmp_path),
    )
    result = json.loads(result_str)
    assert result["action"] == "cycles"
    assert "has_cycles" in result
    assert "cycle_count" in result


@pytest.mark.asyncio
async def test_dependency_graph_path_not_found(tmp_path: Path) -> None:
    result_str = await dependency_graph(
        action="calls",
        path="nonexistent.py",
        cwd=str(tmp_path),
    )
    result = json.loads(result_str)
    assert "error" in result


@pytest.mark.asyncio
async def test_dependency_graph_unknown_action(tmp_path: Path) -> None:
    py_file = tmp_path / "code.py"
    py_file.write_text("x = 1\n")
    result_str = await dependency_graph(
        action="unknown",
        path="code.py",
        cwd=str(tmp_path),
    )
    result = json.loads(result_str)
    assert "error" in result
