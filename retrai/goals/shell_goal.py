"""Shell goal: run any command and check exit code / output / timing."""

from __future__ import annotations

import re
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


class ShellGoal(GoalBase):
    """Run any shell command and check the result.

    Configured via `.retrai.yml` in the project root:

    ```yaml
    goal: shell-goal
    check_command: "make check"
    success_condition:
      exit_code: 0            # require this exit code (default: 0)
      output_contains: "PASS" # require this string in stdout
      output_regex: "^OK"     # require this regex in stdout
      max_seconds: 10         # require completion under N seconds
    system_prompt: |
      Optimise the code until 'make check' outputs PASS.
    ```
    """

    name = "shell-goal"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        command = cfg.get("check_command", "make check")
        cond = cfg.get("success_condition", {})

        expected_exit = cond.get("exit_code", 0)
        output_contains = cond.get("output_contains")
        output_regex = cond.get("output_regex")
        max_seconds = cond.get("max_seconds")

        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=max(120.0, (max_seconds or 120) * 2),
            )
        except subprocess.TimeoutExpired:
            return GoalResult(
                achieved=False,
                reason="Command timed out",
                details={"command": command},
            )
        elapsed = time.monotonic() - start
        stdout = result.stdout + result.stderr

        # Evaluate conditions
        failures = []

        if result.returncode != expected_exit:
            failures.append(f"exit_code={result.returncode} (expected {expected_exit})")

        if output_contains and output_contains not in stdout:
            failures.append(f"stdout does not contain {output_contains!r}")

        if output_regex and not re.search(output_regex, stdout, re.MULTILINE):
            failures.append(f"stdout does not match regex {output_regex!r}")

        if max_seconds and elapsed > max_seconds:
            failures.append(f"took {elapsed:.2f}s (limit: {max_seconds}s)")

        if failures:
            return GoalResult(
                achieved=False,
                reason="; ".join(failures),
                details={
                    "command": command,
                    "elapsed": elapsed,
                    "exit_code": result.returncode,
                    "stdout": stdout[:3000],
                },
            )

        return GoalResult(
            achieved=True,
            reason=f"Command succeeded in {elapsed:.2f}s",
            details={"command": command, "elapsed": elapsed},
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        custom = cfg.get("system_prompt", "")
        command = cfg.get("check_command", "make check")
        cond = cfg.get("success_condition", {})
        base = (
            f"Your goal is to make the command `{command}` succeed.\n"
            f"Success conditions: {cond}\n\n"
            "Strategy:\n"
            "1. Run the check command to see the current state.\n"
            "2. Read the output and identify what needs to change.\n"
            "3. Modify source files (not scripts/configs unless necessary).\n"
            "4. Re-run the check command to verify progress.\n"
            "5. Repeat until all conditions are met.\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base
