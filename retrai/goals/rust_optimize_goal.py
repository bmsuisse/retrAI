"""Rust optimization goal — run cargo bench and check ns/iter target.

Guides the agent to optimize Rust code until a named benchmark
hits a target nanoseconds-per-iteration threshold.

`.retrai.yml` config:
```yaml
goal: rust-optimize
bench_name: my_bench          # benchmark function name (substring match)
target_ns: 100                # target nanoseconds per iteration
iterations: 3                 # must pass N consecutive times (default 1)
bench_args: ""                # extra args passed to cargo bench
```
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from retrai.goals.base import GoalBase, GoalResult

_CONFIG_FILE = ".retrai.yml"


def _load_config(cwd: str) -> dict[str, Any]:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _parse_criterion_output(output: str, bench_name: str) -> float | None:
    """Parse Criterion benchmark output and return ns/iter for the named bench.

    Criterion format:
        my_bench            time:   [12.345 ns 12.456 ns 12.567 ns]

    libtest format:
        test my_bench ... bench:          12,345 ns/iter (+/- 123)
    """
    # Try Criterion format first
    # Match: bench_name ... time: [... X.XXX ns ...]
    criterion_pattern = re.compile(
        rf"{re.escape(bench_name)}.*?time:.*?\[\s*[\d.]+\s+\w+\s+([\d.]+)\s+(\w+)",
        re.DOTALL | re.IGNORECASE,
    )
    m = criterion_pattern.search(output)
    if m:
        value = float(m.group(1))
        unit = m.group(2).lower()
        return _to_ns(value, unit)

    # Try libtest format
    libtest_pattern = re.compile(
        rf"test\s+{re.escape(bench_name)}.*?bench:\s+([\d,]+)\s+ns/iter",
        re.IGNORECASE,
    )
    m = libtest_pattern.search(output)
    if m:
        return float(m.group(1).replace(",", ""))

    # Fuzzy: any line containing bench_name and a time value
    for line in output.splitlines():
        if bench_name.lower() in line.lower():
            # Look for patterns like "123.45 ns" or "1.23 µs"
            time_match = re.search(r"([\d.]+)\s*(ns|µs|us|ms|s)\b", line, re.IGNORECASE)
            if time_match:
                value = float(time_match.group(1))
                unit = time_match.group(2).lower()
                return _to_ns(value, unit)

    return None


def _to_ns(value: float, unit: str) -> float:
    """Convert a time value to nanoseconds."""
    multipliers: dict[str, float] = {
        "ns": 1.0,
        "µs": 1_000.0,
        "us": 1_000.0,
        "ms": 1_000_000.0,
        "s": 1_000_000_000.0,
    }
    return value * multipliers.get(unit, 1.0)


class RustOptimizeGoal(GoalBase):
    """Optimize Rust code until cargo bench hits a target ns/iter.

    The agent is done when the named benchmark runs in ≤ target_ns
    nanoseconds per iteration for N consecutive runs.
    """

    name = "rust-optimize"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        bench_name: str = cfg.get("bench_name", "")
        target_ns = float(cfg.get("target_ns", 100.0))
        required_passes = int(cfg.get("iterations", 1))
        bench_args: str = cfg.get("bench_args", "")

        if not bench_name:
            return GoalResult(
                achieved=False,
                reason="No bench_name specified in .retrai.yml",
                details={"config": cfg},
            )

        # Check that Cargo.toml exists
        if not (Path(cwd) / "Cargo.toml").exists():
            return GoalResult(
                achieved=False,
                reason="No Cargo.toml found — is this a Rust project?",
                details={"cwd": cwd},
            )

        times_ns: list[float] = []

        for i in range(required_passes):
            cmd = f"cargo bench {bench_name} {bench_args}".strip()
            start = time.monotonic()
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 min max per bench run
                )
            except subprocess.TimeoutExpired:
                return GoalResult(
                    achieved=False,
                    reason=f"cargo bench timed out on run {i + 1}/{required_passes}",
                    details={"bench_name": bench_name, "target_ns": target_ns},
                )
            elapsed = time.monotonic() - start

            if result.returncode != 0:
                return GoalResult(
                    achieved=False,
                    reason=f"cargo bench failed (exit {result.returncode})",
                    details={
                        "bench_name": bench_name,
                        "stderr": result.stderr[:2000],
                        "stdout": result.stdout[:2000],
                        "elapsed_s": elapsed,
                    },
                )

            output = result.stdout + result.stderr
            ns = _parse_criterion_output(output, bench_name)

            if ns is None:
                return GoalResult(
                    achieved=False,
                    reason=(
                        f"Could not parse benchmark output for '{bench_name}'. "
                        "Make sure the bench name matches exactly."
                    ),
                    details={
                        "bench_name": bench_name,
                        "output_sample": output[:2000],
                    },
                )

            times_ns.append(ns)

            if ns > target_ns:
                avg = sum(times_ns) / len(times_ns)
                return GoalResult(
                    achieved=False,
                    reason=(
                        f"Too slow: {ns:.1f} ns/iter (target: {target_ns} ns, "
                        f"avg so far: {avg:.1f} ns, run {i + 1}/{required_passes})"
                    ),
                    details={
                        "bench_name": bench_name,
                        "ns_per_iter": ns,
                        "target_ns": target_ns,
                        "times_ns": times_ns,
                        "speedup_needed": ns / target_ns,
                    },
                )

        avg = sum(times_ns) / len(times_ns)
        return GoalResult(
            achieved=True,
            reason=(
                f"🚀 Target reached! {bench_name} = {avg:.1f} ns/iter "
                f"(target: {target_ns} ns) — passed {required_passes}× consecutive"
            ),
            details={
                "bench_name": bench_name,
                "avg_ns": avg,
                "target_ns": target_ns,
                "times_ns": times_ns,
                "speedup_vs_target": target_ns / avg if avg > 0 else float("inf"),
            },
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        bench_name = cfg.get("bench_name", "<bench_name>")
        target_ns = cfg.get("target_ns", 100)
        custom = cfg.get("system_prompt", "")

        base = (
            f"## Goal: Rust Performance Optimization\n\n"
            f"Optimize the Rust code so that the `{bench_name}` benchmark "
            f"runs in **≤ {target_ns} ns/iter**.\n\n"
            "**Strategy**:\n"
            "1. Run `cargo bench` to see the current baseline timing.\n"
            "2. Use `rust_bench` tool to get structured benchmark results.\n"
            "3. Profile with `cargo flamegraph` or `perf` via `bash_exec` "
            "to find hotspots.\n"
            "4. Apply optimizations in order of impact:\n"
            "   - **Algorithmic**: better data structures, fewer allocations, "
            "SIMD, parallelism\n"
            "   - **Memory**: reduce heap allocations, use stack, avoid clones\n"
            "   - **Compiler hints**: `#[inline]`, `#[cold]`, `likely/unlikely`\n"
            "   - **SIMD**: use `std::simd` or `packed_simd` for vectorization\n"
            "   - **Parallelism**: `rayon` for data parallelism\n"
            "5. Re-run `cargo bench` after each change to measure improvement.\n"
            "6. Run `cargo test` to ensure correctness is preserved.\n\n"
            "**Rust optimization tactics**:\n"
            "- Prefer `Vec::with_capacity()` over push-heavy loops\n"
            "- Use iterators instead of index loops (LLVM optimizes better)\n"
            "- Avoid `Box<dyn Trait>` in hot paths — use generics\n"
            "- Use `unsafe` only when profiling proves it's the bottleneck\n"
            "- Check `cargo build --release` flags in Cargo.toml\n"
            "- Try `opt-level = 3`, `lto = true`, `codegen-units = 1`\n"
            "- Consider `mimalloc` or `jemalloc` for allocation-heavy code\n\n"
            "**Critical Rules**:\n"
            "- NEVER break correctness — `cargo test` must pass\n"
            "- Measure before and after EVERY change\n"
            "- If one approach doesn't work, try a completely different one\n"
            "- Use `web_search` to find Rust-specific optimization techniques\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base
