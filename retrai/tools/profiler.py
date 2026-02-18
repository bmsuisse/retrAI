"""Profiler tool — profile Python code with cProfile or timeit.

Supports:
- ``profile_code``: Profile an inline Python snippet, return top hotspots.
- ``profile_file``: Profile a .py file (runs its __main__ block).
- ``timeit``: Micro-benchmark a Python expression.
"""

from __future__ import annotations

import json
import logging
import textwrap

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)


# ── Code builders ─────────────────────────────────────────────────────────────


def _build_profile_code(code: str, top_n: int) -> str:
    """Build sandbox code that profiles ``code`` with cProfile."""
    # Dedent user code to avoid IndentationError if passed with leading whitespace
    dedented = textwrap.dedent(code).strip()
    escaped = dedented.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return (
        "import cProfile\n"
        "import pstats\n"
        "import io\n"
        "import json\n"
        "\n"
        f'code_to_profile = """{escaped}"""\n'
        "\n"
        "pr = cProfile.Profile()\n"
        "pr.enable()\n"
        'exec(compile(code_to_profile, "<profiled>", "exec"))\n'
        "pr.disable()\n"
        "\n"
        "stream = io.StringIO()\n"
        'ps = pstats.Stats(pr, stream=stream).sort_stats("cumulative")\n'
        f"ps.print_stats({top_n})\n"
        "\n"
        "stats = ps.stats\n"
        "rows = []\n"
        "for (filename, lineno, funcname), (cc, nc, tt, ct, _callers) in stats.items():\n"
        "    rows.append({\n"
        '        "name": funcname,\n'
        '        "file": filename,\n'
        '        "line": lineno,\n'
        '        "ncalls": nc,\n'
        '        "tottime_ms": round(tt * 1000, 3),\n'
        '        "cumtime_ms": round(ct * 1000, 3),\n'
        "    })\n"
        "\n"
        'rows.sort(key=lambda r: r["cumtime_ms"], reverse=True)\n'
        'total_ms = sum(r["tottime_ms"] for r in rows)\n'
        "\n"
        "result = {\n"
        f'    "top_functions": rows[:{top_n}],\n'
        '    "total_time_ms": round(total_ms, 3),\n'
        '    "raw_output": stream.getvalue()[-3000:],\n'
        "}\n"
        "print(json.dumps(result, default=str))\n"
    )


def _build_profile_file(file_path: str, top_n: int) -> str:
    """Build sandbox code that profiles a .py file."""
    return (
        "import cProfile\n"
        "import pstats\n"
        "import io\n"
        "import json\n"
        "import runpy\n"
        "\n"
        "pr = cProfile.Profile()\n"
        "pr.enable()\n"
        "try:\n"
        f"    runpy.run_path({file_path!r}, run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "pr.disable()\n"
        "\n"
        "stream = io.StringIO()\n"
        'ps = pstats.Stats(pr, stream=stream).sort_stats("cumulative")\n'
        f"ps.print_stats({top_n})\n"
        "\n"
        "stats = ps.stats\n"
        "rows = []\n"
        "for (filename, lineno, funcname), (cc, nc, tt, ct, _callers) in stats.items():\n"
        "    rows.append({\n"
        '        "name": funcname,\n'
        '        "file": filename,\n'
        '        "line": lineno,\n'
        '        "ncalls": nc,\n'
        '        "tottime_ms": round(tt * 1000, 3),\n'
        '        "cumtime_ms": round(ct * 1000, 3),\n'
        "    })\n"
        "\n"
        'rows.sort(key=lambda r: r["cumtime_ms"], reverse=True)\n'
        'total_ms = sum(r["tottime_ms"] for r in rows)\n'
        "\n"
        "result = {\n"
        f'    "top_functions": rows[:{top_n}],\n'
        '    "total_time_ms": round(total_ms, 3),\n'
        '    "raw_output": stream.getvalue()[-3000:],\n'
        "}\n"
        "print(json.dumps(result, default=str))\n"
    )


def _build_timeit_code(expression: str, setup: str, number: int) -> str:
    """Build sandbox code that runs timeit on an expression."""
    return (
        "import timeit\n"
        "import json\n"
        "\n"
        "timer = timeit.Timer(\n"
        f"    stmt={expression!r},\n"
        f"    setup={setup!r},\n"
        ")\n"
        "\n"
        f"number = {number}\n"
        "if number == 0:\n"
        "    number, _ = timer.autorange()\n"
        "\n"
        "times = timer.repeat(repeat=5, number=number)\n"
        "best_s = min(times) / number\n"
        "avg_s = (sum(times) / len(times)) / number\n"
        "\n"
        "result = {\n"
        f'    "expression": {expression!r},\n'
        '    "number": number,\n'
        '    "best_time_ms": round(best_s * 1000, 6),\n'
        '    "avg_time_ms": round(avg_s * 1000, 6),\n'
        '    "all_runs_ms": [round(t / number * 1000, 6) for t in times],\n'
        '    "unit": "ms per call",\n'
        "}\n"
        "print(json.dumps(result))\n"
    )


# ── Public async API ──────────────────────────────────────────────────────────


async def profile_code(
    action: str,
    cwd: str,
    code: str = "",
    file_path: str = "",
    expression: str = "",
    setup: str = "pass",
    top_n: int = 20,
    number: int = 0,
    packages: list[str] | None = None,
    timeout: float = 60.0,
) -> str:
    """Profile Python code or run timeit benchmarks.

    Args:
        action: One of ``profile_code``, ``profile_file``, ``timeit``.
        cwd: Working directory.
        code: Python code snippet (for ``profile_code``).
        file_path: Path to .py file (for ``profile_file``).
        expression: Python expression (for ``timeit``).
        setup: Setup code for timeit (default ``"pass"``).
        top_n: Number of top functions to return (default 20).
        number: Iterations for timeit (0 = auto-calibrate).
        packages: Extra pip packages to install in sandbox.
        timeout: Sandbox timeout in seconds.

    Returns:
        JSON string with profiling results.
    """
    action = action.lower().strip()

    if action == "profile_code":
        if not code:
            return json.dumps({"error": "No code provided for profile_code"})
        sandbox_code = _build_profile_code(code, top_n)
    elif action == "profile_file":
        if not file_path:
            return json.dumps({"error": "No file_path provided for profile_file"})
        sandbox_code = _build_profile_file(file_path, top_n)
    elif action == "timeit":
        if not expression:
            return json.dumps({"error": "No expression provided for timeit"})
        sandbox_code = _build_timeit_code(expression, setup, number)
    else:
        return json.dumps(
            {
                "error": (
                    f"Unknown action '{action}'. "
                    "Use: profile_code, profile_file, timeit"
                )
            }
        )

    result = await python_exec(
        code=sandbox_code,
        cwd=cwd,
        packages=packages,
        timeout=timeout,
    )

    if result.timed_out:
        return json.dumps({"error": f"Profiling timed out after {timeout}s"})

    if result.returncode != 0:
        return json.dumps(
            {
                "error": f"Profiling failed (exit {result.returncode})",
                "stderr": result.stderr[:2000],
            }
        )

    stdout = result.stdout.strip()
    try:
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2, default=str)
    except json.JSONDecodeError:
        return json.dumps({"action": action, "raw_output": stdout[:4000]})
