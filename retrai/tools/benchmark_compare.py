"""Benchmark comparison tool — compare two Python implementations head-to-head.

Runs both snippets with timeit (speed) and tracemalloc (memory), then
produces a structured comparison with speedup ratio and verdict.
"""

from __future__ import annotations

import json
import logging
import textwrap

from retrai.tools.python_exec import python_exec

logger = logging.getLogger(__name__)


def _build_compare_code(
    code_a: str,
    code_b: str,
    setup: str,
    label_a: str,
    label_b: str,
    number: int,
) -> str:
    """Build sandbox code that benchmarks two implementations."""
    da = textwrap.dedent(code_a).strip()
    db = textwrap.dedent(code_b).strip()
    ds = textwrap.dedent(setup).strip()

    return (
        "import timeit\n"
        "import tracemalloc\n"
        "import json\n"
        "\n"
        "def measure_time(stmt, setup, number):\n"
        "    timer = timeit.Timer(stmt=stmt, setup=setup)\n"
        "    if number == 0:\n"
        "        number, _ = timer.autorange()\n"
        "    times = timer.repeat(repeat=5, number=number)\n"
        "    best_ms = min(times) / number * 1000\n"
        "    avg_ms = (sum(times) / len(times)) / number * 1000\n"
        "    return best_ms, avg_ms, number\n"
        "\n"
        "def measure_memory(code_str, setup_str):\n"
        "    ns = {}\n"
        "    tracemalloc.start()\n"
        "    if setup_str:\n"
        '        exec(compile(setup_str, "<setup>", "exec"), ns)\n'
        '    exec(compile(code_str, "<bench>", "exec"), ns)\n'
        "    _, peak = tracemalloc.get_traced_memory()\n"
        "    tracemalloc.stop()\n"
        "    return peak / 1024\n"
        "\n"
        f"setup = {ds!r}\n"
        f"code_a = {da!r}\n"
        f"code_b = {db!r}\n"
        f"number = {number}\n"
        "\n"
        "best_a, avg_a, n_a = measure_time(code_a, setup, number)\n"
        "best_b, avg_b, n_b = measure_time(code_b, setup, number)\n"
        "mem_a = measure_memory(code_a, setup)\n"
        "mem_b = measure_memory(code_b, setup)\n"
        "\n"
        "speedup = best_a / best_b if best_b > 0 else float('inf')\n"
        "mem_ratio = mem_b / mem_a if mem_a > 0 else float('inf')\n"
        "\n"
        "if speedup > 1.05:\n"
        f"    verdict = f'{{round(speedup, 2)}}x faster: {label_b} wins'\n"
        "elif speedup < 0.95:\n"
        f"    verdict = f'{{round(1/speedup, 2)}}x faster: {label_a} wins'\n"
        "else:\n"
        "    verdict = 'roughly equivalent speed'\n"
        "\n"
        "result = {\n"
        f'    "{label_a}": {{\n'
        '        "best_ms": round(best_a, 6),\n'
        '        "avg_ms": round(avg_a, 6),\n'
        '        "peak_memory_kb": round(mem_a, 3),\n'
        '        "iterations": n_a,\n'
        "    },\n"
        f'    "{label_b}": {{\n'
        '        "best_ms": round(best_b, 6),\n'
        '        "avg_ms": round(avg_b, 6),\n'
        '        "peak_memory_kb": round(mem_b, 3),\n'
        '        "iterations": n_b,\n'
        "    },\n"
        '    "speedup": round(speedup, 4),\n'
        '    "memory_ratio": round(mem_ratio, 4),\n'
        '    "verdict": verdict,\n'
        "}\n"
        "print(json.dumps(result))\n"
    )


async def benchmark_compare(
    code_a: str,
    code_b: str,
    cwd: str,
    setup: str = "",
    label_a: str = "baseline",
    label_b: str = "candidate",
    number: int = 0,
    packages: list[str] | None = None,
    timeout: float = 120.0,
) -> str:
    """Compare two Python implementations for speed and memory.

    Args:
        code_a: First (baseline) implementation.
        code_b: Second (candidate) implementation.
        cwd: Working directory.
        setup: Shared setup code (imports, data creation).
        label_a: Label for the first implementation.
        label_b: Label for the second implementation.
        number: Timeit iterations (0 = auto-calibrate).
        packages: Extra pip packages to install in sandbox.
        timeout: Sandbox timeout in seconds.

    Returns:
        JSON string with per-implementation stats and a verdict.
    """
    if not code_a or not code_b:
        return json.dumps({"error": "Both code_a and code_b are required"})

    sandbox_code = _build_compare_code(
        code_a=code_a,
        code_b=code_b,
        setup=setup,
        label_a=label_a,
        label_b=label_b,
        number=number,
    )

    result = await python_exec(
        code=sandbox_code,
        cwd=cwd,
        packages=packages,
        timeout=timeout,
    )

    if result.timed_out:
        return json.dumps({"error": f"Benchmark timed out after {timeout}s"})

    if result.returncode != 0:
        return json.dumps(
            {
                "error": f"Benchmark failed (exit {result.returncode})",
                "stderr": result.stderr[:2000],
            }
        )

    stdout = result.stdout.strip()
    try:
        parsed = json.loads(stdout)
        return json.dumps(parsed, indent=2, default=str)
    except json.JSONDecodeError:
        return json.dumps({"raw_output": stdout[:4000]})
