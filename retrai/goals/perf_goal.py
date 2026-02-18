"""Performance goal: run a script/command and check it finishes under a time limit."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import yaml

from retrai.goals.base import GoalBase, GoalResult

_CONFIG_FILE = ".retrai.yml"


def _load_config(cwd: str) -> dict:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


class PerfCheckGoal(GoalBase):
    """Optimise until a command completes under a time threshold.

    `.retrai.yml`:

    ```yaml
    goal: perf-check
    check_command: "python bench.py"
    max_seconds: 0.5
    iterations: 3          # must pass N consecutive times (default 1)
    ```
    """

    name = "perf-check"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        command = cfg.get("check_command", "python bench.py")
        max_seconds = float(cfg.get("max_seconds", 1.0))
        required_passes = int(cfg.get("iterations", 1))

        times: list[float] = []
        last_stdout = ""

        for _ in range(required_passes):
            start = time.monotonic()
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=max_seconds * 10,
                )
            except subprocess.TimeoutExpired:
                return GoalResult(
                    achieved=False,
                    reason=f"Command timed out (limit: {max_seconds}s × 10)",
                    details={"command": command},
                )
            elapsed = time.monotonic() - start
            times.append(elapsed)
            last_stdout = result.stdout + result.stderr

            if result.returncode != 0:
                return GoalResult(
                    achieved=False,
                    reason=f"Command exited with code {result.returncode}",
                    details={
                        "command": command,
                        "elapsed": elapsed,
                        "stdout": last_stdout[:2000],
                    },
                )

            if elapsed > max_seconds:
                avg = sum(times) / len(times)
                return GoalResult(
                    achieved=False,
                    reason=(
                        f"Too slow: {elapsed:.3f}s (limit: {max_seconds}s, avg so far: {avg:.3f}s)"
                    ),
                    details={
                        "command": command,
                        "elapsed": elapsed,
                        "times": times,
                        "stdout": last_stdout[:2000],
                    },
                )

        avg = sum(times) / len(times)
        return GoalResult(
            achieved=True,
            reason=(
                f"Passed {required_passes}× consecutive in avg {avg:.3f}s (limit: {max_seconds}s)"
            ),
            details={"command": command, "times": times, "avg": avg},
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        custom = cfg.get("system_prompt", "")
        command = cfg.get("check_command", "python bench.py")
        max_sec = cfg.get("max_seconds", 1.0)
        base = (
            f"Your goal is to optimise the code so that `{command}` completes "
            f"in under {max_sec} seconds.\n\n"
            "Strategy:\n"
            "1. Run the benchmark to see the current timing.\n"
            "2. Profile where time is spent (cProfile, line_profiler, etc.).\n"
            "3. Apply targeted optimisations: algorithmic improvements first,\n"
            "   then implementation details (caching, vectorisation, etc.).\n"
            "4. Re-run to verify the improvement.\n"
            "5. Do NOT break correctness — the command must still exit 0.\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base
