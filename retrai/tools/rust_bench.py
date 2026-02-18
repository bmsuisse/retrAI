"""Rust benchmark tool — run cargo bench and parse Criterion/libtest output.

Returns structured JSON with benchmark name, ns/iter, throughput, and
confidence intervals so the agent can track performance improvements
across iterations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT = 300  # 5 minutes max for a bench run


def _parse_criterion_json(output: str) -> list[dict[str, Any]]:
    """Parse Criterion's machine-readable JSON output (--output-format bencher).

    Criterion can emit JSON lines when run with the right flags.
    """
    results: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if "id" in obj and "typical" in obj:
                typical = obj["typical"]
                results.append(
                    {
                        "name": obj["id"],
                        "ns_per_iter": typical.get("estimate", 0),
                        "lower_bound_ns": typical.get("lower_bound", 0),
                        "upper_bound_ns": typical.get("upper_bound", 0),
                        "unit": typical.get("unit", "ns"),
                        "throughput": obj.get("throughput"),
                        "source": "criterion_json",
                    }
                )
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def _parse_criterion_text(output: str) -> list[dict[str, Any]]:
    """Parse Criterion's human-readable text output.

    Format:
        bench_name          time:   [12.345 ns 12.456 ns 12.567 ns]
                            thrpt:  [1.2345 GiB/s 1.2456 GiB/s 1.2567 GiB/s]
    """
    results: list[dict[str, Any]] = []
    # Match benchmark blocks
    pattern = re.compile(
        r"^(\S.*?)\s+time:\s+\[\s*([\d.]+)\s+(\w+)\s+([\d.]+)\s+(\w+)\s+([\d.]+)\s+(\w+)\s*\]",
        re.MULTILINE,
    )
    for m in pattern.finditer(output):
        name = m.group(1).strip()
        lower = float(m.group(2))
        lower_unit = m.group(3)
        estimate = float(m.group(4))
        est_unit = m.group(5)
        upper = float(m.group(6))
        upper_unit = m.group(7)

        results.append(
            {
                "name": name,
                "ns_per_iter": _to_ns(estimate, est_unit),
                "lower_bound_ns": _to_ns(lower, lower_unit),
                "upper_bound_ns": _to_ns(upper, upper_unit),
                "unit": "ns",
                "throughput": None,
                "source": "criterion_text",
            }
        )
    return results


def _parse_libtest(output: str) -> list[dict[str, Any]]:
    """Parse libtest benchmark output.

    Format:
        test bench_name ... bench:      12,345 ns/iter (+/- 123)
    """
    results: list[dict[str, Any]] = []
    pattern = re.compile(
        r"test\s+(\S+)\s+\.\.\.\s+bench:\s+([\d,]+)\s+ns/iter\s+\(\+/-\s+([\d,]+)\)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(output):
        name = m.group(1)
        ns = float(m.group(2).replace(",", ""))
        variance = float(m.group(3).replace(",", ""))
        results.append(
            {
                "name": name,
                "ns_per_iter": ns,
                "lower_bound_ns": ns - variance,
                "upper_bound_ns": ns + variance,
                "unit": "ns",
                "throughput": None,
                "source": "libtest",
            }
        )
    return results


def _to_ns(value: float, unit: str) -> float:
    """Convert a time value to nanoseconds."""
    multipliers: dict[str, float] = {
        "ps": 0.001,
        "ns": 1.0,
        "µs": 1_000.0,
        "us": 1_000.0,
        "ms": 1_000_000.0,
        "s": 1_000_000_000.0,
    }
    return value * multipliers.get(unit.lower(), 1.0)


def _parse_bench_output(output: str) -> list[dict[str, Any]]:
    """Try all parsers and return the best result."""
    # Try JSON first (most precise)
    results = _parse_criterion_json(output)
    if results:
        return results

    # Try Criterion text
    results = _parse_criterion_text(output)
    if results:
        return results

    # Fall back to libtest
    return _parse_libtest(output)


async def rust_bench(
    bench_name: str | None = None,
    extra_args: str = "",
    cwd: str = ".",
) -> str:
    """Run cargo bench and return structured benchmark results as JSON.

    Args:
        bench_name: Optional benchmark name filter (substring match)
        extra_args: Extra arguments to pass to cargo bench
        cwd: Project directory (must contain Cargo.toml)
    """
    if not (Path(cwd) / "Cargo.toml").exists():
        return json.dumps(
            {"error": "No Cargo.toml found — is this a Rust project?", "cwd": cwd},
            indent=2,
        )

    # Build command
    cmd_parts = ["cargo", "bench"]
    if bench_name:
        cmd_parts.append(bench_name)
    if extra_args:
        cmd_parts.extend(extra_args.split())

    cmd = " ".join(cmd_parts)
    logger.debug("Running: %s in %s", cmd, cwd)

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT
            )
        except TimeoutError:
            proc.kill()
            return json.dumps(
                {"error": f"cargo bench timed out after {_TIMEOUT}s", "command": cmd},
                indent=2,
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        combined = stdout + stderr

    except Exception as e:
        return json.dumps({"error": f"Failed to run cargo bench: {e}"}, indent=2)

    if proc.returncode != 0:
        return json.dumps(
            {
                "error": f"cargo bench failed (exit {proc.returncode})",
                "command": cmd,
                "stderr": stderr[:3000],
                "stdout": stdout[:1000],
            },
            indent=2,
        )

    benchmarks = _parse_bench_output(combined)

    # Filter by bench_name if specified
    if bench_name and benchmarks:
        filtered = [b for b in benchmarks if bench_name.lower() in b["name"].lower()]
        if filtered:
            benchmarks = filtered

    if not benchmarks:
        return json.dumps(
            {
                "warning": "No benchmarks parsed from output",
                "command": cmd,
                "output_sample": combined[:3000],
            },
            indent=2,
        )

    # Format output: JSON + human-readable summary
    summary_lines = [f"## Benchmark Results: {cmd}\n"]
    for b in benchmarks:
        ns = b["ns_per_iter"]
        lo = b.get("lower_bound_ns", ns)
        hi = b.get("upper_bound_ns", ns)

        # Human-readable unit
        if ns >= 1_000_000_000:
            human = f"{ns / 1_000_000_000:.3f} s"
        elif ns >= 1_000_000:
            human = f"{ns / 1_000_000:.3f} ms"
        elif ns >= 1_000:
            human = f"{ns / 1_000:.3f} µs"
        else:
            human = f"{ns:.1f} ns"

        summary_lines.append(
            f"- **{b['name']}**: {human}/iter "
            f"[{lo:.1f} ns .. {hi:.1f} ns] ({b['source']})"
        )

    summary = "\n".join(summary_lines)
    json_output = json.dumps({"benchmarks": benchmarks, "command": cmd}, indent=2)

    return f"{summary}\n\n```json\n{json_output}\n```"
