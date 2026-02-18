"""Memory profiling tool — trace Python allocations with tracemalloc.

Supports:
- ``profile_code``: Trace allocations in an inline snippet.
- ``profile_file``: Trace allocations in a .py file.
- ``compare``: Compare peak memory of two code snippets side-by-side.
"""

from __future__ import annotations

import json
import logging
import textwrap

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)


# ── Code builders ─────────────────────────────────────────────────────────────


def _build_memory_profile_code(code: str, top_n: int) -> str:
    """Build sandbox code that traces allocations with tracemalloc."""
    dedented = textwrap.dedent(code).strip()
    escaped = dedented.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return (
        "import tracemalloc\n"
        "import json\n"
        "\n"
        "tracemalloc.start()\n"
        f'code_to_run = """{escaped}"""\n'
        'exec(compile(code_to_run, "<memory_profiled>", "exec"))\n'
        "snapshot = tracemalloc.take_snapshot()\n"
        "tracemalloc.stop()\n"
        "\n"
        "stats = snapshot.statistics('lineno')\n"
        "peak_kb = tracemalloc.get_traced_memory()[1] / 1024\n"
        "\n"
        "rows = []\n"
        f"for stat in stats[:{top_n}]:\n"
        "    frame = stat.traceback[0]\n"
        "    rows.append({\n"
        '        "file": frame.filename,\n'
        '        "line": frame.lineno,\n'
        '        "size_kb": round(stat.size / 1024, 3),\n'
        '        "count": stat.count,\n'
        "    })\n"
        "\n"
        "result = {\n"
        '    "top_allocations": rows,\n'
        '    "total_traced_kb": round(sum(s.size for s in stats) / 1024, 3),\n'
        "}\n"
        "print(json.dumps(result, default=str))\n"
    )


def _build_memory_profile_file(file_path: str, top_n: int) -> str:
    """Build sandbox code that traces allocations for a .py file."""
    return (
        "import tracemalloc\n"
        "import json\n"
        "import runpy\n"
        "\n"
        "tracemalloc.start()\n"
        "try:\n"
        f"    runpy.run_path({file_path!r}, run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "snapshot = tracemalloc.take_snapshot()\n"
        "tracemalloc.stop()\n"
        "\n"
        "stats = snapshot.statistics('lineno')\n"
        "\n"
        "rows = []\n"
        f"for stat in stats[:{top_n}]:\n"
        "    frame = stat.traceback[0]\n"
        "    rows.append({\n"
        '        "file": frame.filename,\n'
        '        "line": frame.lineno,\n'
        '        "size_kb": round(stat.size / 1024, 3),\n'
        '        "count": stat.count,\n'
        "    })\n"
        "\n"
        "result = {\n"
        '    "top_allocations": rows,\n'
        '    "total_traced_kb": round(sum(s.size for s in stats) / 1024, 3),\n'
        "}\n"
        "print(json.dumps(result, default=str))\n"
    )


def _build_memory_compare_code(code_a: str, code_b: str) -> str:
    """Build sandbox code that compares peak memory of two snippets."""
    da = textwrap.dedent(code_a).strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    db = textwrap.dedent(code_b).strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return (
        "import tracemalloc\n"
        "import json\n"
        "\n"
        "def measure(code_str):\n"
        "    tracemalloc.start()\n"
        '    exec(compile(code_str, "<mem_compare>", "exec"))\n'
        "    _, peak = tracemalloc.get_traced_memory()\n"
        "    tracemalloc.stop()\n"
        "    return peak / 1024\n"
        "\n"
        f'peak_a = measure("""{da}""")\n'
        f'peak_b = measure("""{db}""")\n'
        "\n"
        "delta_kb = peak_b - peak_a\n"
        "ratio = peak_b / peak_a if peak_a > 0 else float('inf')\n"
        "\n"
        "result = {\n"
        '    "peak_a_kb": round(peak_a, 3),\n'
        '    "peak_b_kb": round(peak_b, 3),\n'
        '    "delta_kb": round(delta_kb, 3),\n'
        '    "ratio": round(ratio, 4),\n'
        '    "verdict": "b uses less memory" if delta_kb < 0 else '
        '"a uses less memory" if delta_kb > 0 else "equal",\n'
        "}\n"
        "print(json.dumps(result))\n"
    )


# ── Public async API ──────────────────────────────────────────────────────────


async def memory_profile(
    action: str,
    cwd: str,
    code: str = "",
    code_a: str = "",
    code_b: str = "",
    file_path: str = "",
    top_n: int = 10,
    packages: list[str] | None = None,
    timeout: float = 60.0,
) -> str:
    """Profile memory allocations using tracemalloc.

    Args:
        action: One of ``profile_code``, ``profile_file``, ``compare``.
        cwd: Working directory.
        code: Python code snippet (for ``profile_code``).
        code_a: First snippet (for ``compare``).
        code_b: Second snippet (for ``compare``).
        file_path: Path to .py file (for ``profile_file``).
        top_n: Top N allocation sites to return.
        packages: Extra pip packages to install in sandbox.
        timeout: Sandbox timeout in seconds.

    Returns:
        JSON string with allocation data.
    """
    action = action.lower().strip()

    if action == "profile_code":
        if not code:
            return json.dumps({"error": "No code provided for profile_code"})
        sandbox_code = _build_memory_profile_code(code, top_n)
    elif action == "profile_file":
        if not file_path:
            return json.dumps({"error": "No file_path provided for profile_file"})
        sandbox_code = _build_memory_profile_file(file_path, top_n)
    elif action == "compare":
        if not code_a or not code_b:
            return json.dumps({"error": "Both code_a and code_b required for compare"})
        sandbox_code = _build_memory_compare_code(code_a, code_b)
    else:
        return json.dumps(
            {
                "error": (
                    f"Unknown action '{action}'. "
                    "Use: profile_code, profile_file, compare"
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
        return json.dumps({"error": f"Memory profiling timed out after {timeout}s"})

    if result.returncode != 0:
        return json.dumps(
            {
                "error": f"Memory profiling failed (exit {result.returncode})",
                "stderr": result.stderr[:2000],
            }
        )

    stdout = result.stdout.strip()
    try:
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2, default=str)
    except json.JSONDecodeError:
        return json.dumps({"action": action, "raw_output": stdout[:4000]})
