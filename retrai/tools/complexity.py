"""Complexity analyzer tool — cyclomatic complexity, Halstead metrics, nested-loop detection.

Uses:
- ``radon`` for cyclomatic complexity (CC) and Halstead metrics (optional dep)
- Python ``ast`` module for nested-loop detection (no extra deps)
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_RADON_INSTALL_HINT = (
    "radon is not installed. Install with: uv pip install 'retrai[optimize]'"
)


# ── AST-based nested loop detection ──────────────────────────────────────────


class _NestedLoopVisitor(ast.NodeVisitor):
    """Detect nested loops in function bodies."""

    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []
        self._loop_depth = 0
        self._current_func: str = "<module>"
        self._current_func_line: int = 0

    def _visit_loop(self, node: ast.For | ast.While | ast.AsyncFor) -> None:
        self._loop_depth += 1
        if self._loop_depth >= 2:
            self.findings.append(
                {
                    "function": self._current_func,
                    "line": node.lineno,
                    "depth": self._loop_depth,
                    "type": type(node).__name__,
                    "message": (
                        f"Nested loop (depth {self._loop_depth}) at line {node.lineno} "
                        f"in '{self._current_func}' — potential O(n^{self._loop_depth}) complexity"
                    ),
                }
            )
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self._visit_loop(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        old_func = self._current_func
        old_line = self._current_func_line
        old_depth = self._loop_depth
        self._current_func = node.name
        self._current_func_line = node.lineno
        self._loop_depth = 0  # reset depth per function
        self.generic_visit(node)
        self._current_func = old_func
        self._current_func_line = old_line
        self._loop_depth = old_depth

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self.visit_FunctionDef(node)  # type: ignore[arg-type]


def _detect_nested_loops(source: str) -> list[dict[str, Any]]:
    """Return a list of nested-loop findings from Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [{"error": f"Syntax error: {e}"}]
    visitor = _NestedLoopVisitor()
    visitor.visit(tree)
    return visitor.findings


# ── Cyclomatic Complexity (radon) ─────────────────────────────────────────────


def _cyclomatic_complexity(source: str) -> list[dict[str, Any]]:
    """Return per-function cyclomatic complexity using radon."""
    try:
        from radon.complexity import cc_visit  # type: ignore[import-untyped]
    except ImportError:
        return [{"error": _RADON_INSTALL_HINT}]

    try:
        results = cc_visit(source)
    except SyntaxError as e:
        return [{"error": f"Syntax error: {e}"}]

    output = []
    for block in results:
        rank = _cc_rank(block.complexity)
        output.append(
            {
                "name": block.name,
                "type": block.type,
                "line": block.lineno,
                "complexity": block.complexity,
                "rank": rank,
                "flagged": block.complexity > 10,
            }
        )
    return sorted(output, key=lambda x: x["complexity"], reverse=True)


def _cc_rank(cc: int) -> str:
    """Map cyclomatic complexity to a letter rank (A–F)."""
    if cc <= 5:
        return "A"
    if cc <= 10:
        return "B"
    if cc <= 15:
        return "C"
    if cc <= 20:
        return "D"
    if cc <= 25:
        return "E"
    return "F"


# ── Halstead Metrics (radon) ──────────────────────────────────────────────────


def _halstead_metrics(source: str) -> dict[str, Any]:
    """Return Halstead metrics for the entire module."""
    try:
        from radon.metrics import h_visit  # type: ignore[import-untyped]
    except ImportError:
        return {"error": _RADON_INSTALL_HINT}

    try:
        results = h_visit(source)
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}

    if not results:
        return {"error": "No Halstead metrics computed (empty source?)"}

    # h_visit returns a list of HalsteadReport per function/module
    output = []
    for report in results:
        output.append(
            {
                "name": getattr(report, "name", "<module>"),
                "h1": report.h1,  # distinct operators
                "h2": report.h2,  # distinct operands
                "N1": report.N1,  # total operators
                "N2": report.N2,  # total operands
                "vocabulary": report.vocabulary,
                "length": report.length,
                "volume": round(report.volume, 2),
                "difficulty": round(report.difficulty, 2),
                "effort": round(report.effort, 2),
                "time_s": round(report.time, 2),
                "bugs": round(report.bugs, 4),
            }
        )
    return {"functions": output}


# ── Public async API ──────────────────────────────────────────────────────────


async def analyze_complexity(
    action: str,
    cwd: str,
    source: str = "",
    file_path: str = "",
    cc_threshold: int = 10,
) -> str:
    """Analyze Python code complexity.

    Args:
        action: One of ``cyclomatic``, ``halstead``, ``nested_loops``, ``summary``.
        cwd: Working directory.
        source: Inline Python source code (alternative to file_path).
        file_path: Path to .py file relative to cwd (alternative to source).
        cc_threshold: Flag functions with CC above this value (default 10).

    Returns:
        JSON string with complexity analysis results.
    """
    action = action.lower().strip()

    # Resolve source
    if not source and file_path:
        full_path = Path(cwd) / file_path
        try:
            source = full_path.read_text(encoding="utf-8")
        except OSError as e:
            return json.dumps({"error": f"Cannot read file '{file_path}': {e}"})

    if not source:
        return json.dumps({"error": "No source code provided. Pass 'source' or 'file_path'."})

    if action == "cyclomatic":
        results = _cyclomatic_complexity(source)
        flagged = [r for r in results if r.get("flagged")]
        return json.dumps(
            {
                "action": "cyclomatic",
                "functions": results,
                "flagged_count": len(flagged),
                "threshold": cc_threshold,
            },
            indent=2,
        )

    elif action == "halstead":
        results_h = _halstead_metrics(source)
        return json.dumps({"action": "halstead", **results_h}, indent=2)

    elif action == "nested_loops":
        findings = _detect_nested_loops(source)
        return json.dumps(
            {
                "action": "nested_loops",
                "findings": findings,
                "count": len(findings),
                "has_nested_loops": len(findings) > 0,
            },
            indent=2,
        )

    elif action == "summary":
        cc_results = _cyclomatic_complexity(source)
        halstead_results = _halstead_metrics(source)
        loop_findings = _detect_nested_loops(source)

        flagged_cc = [r for r in cc_results if isinstance(r, dict) and r.get("flagged")]

        # Build a prioritized list of issues
        issues: list[str] = []
        for r in flagged_cc:
            issues.append(
                f"High complexity: '{r['name']}' CC={r['complexity']} (rank {r['rank']})"
            )
        for f in loop_findings:
            if "message" in f:
                issues.append(f["message"])

        return json.dumps(
            {
                "action": "summary",
                "cyclomatic": {
                    "functions": cc_results,
                    "flagged_count": len(flagged_cc),
                },
                "halstead": halstead_results,
                "nested_loops": {
                    "findings": loop_findings,
                    "count": len(loop_findings),
                },
                "issues": issues,
                "issue_count": len(issues),
            },
            indent=2,
            default=str,
        )

    else:
        return json.dumps(
            {
                "error": (
                    f"Unknown action '{action}'. "
                    "Use: cyclomatic, halstead, nested_loops, summary"
                )
            }
        )
