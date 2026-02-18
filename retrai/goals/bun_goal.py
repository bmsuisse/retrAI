"""Bun test goal: run bun test and check if all tests pass."""

from __future__ import annotations

import re
import subprocess

from retrai.goals.base import GoalBase, GoalResult


class BunTestGoal(GoalBase):
    name = "bun-test"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run bun test and check for failures."""
        cmd = ["bun", "test", "--reporter", "verbose"]
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return GoalResult(
                achieved=False,
                reason="bun test timed out after 120s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="bun not found — is it installed?",
                details={"error": "bun_not_found"},
            )

        output = result.stdout + result.stderr
        if result.returncode == 0:
            # Parse summary: "X tests passed"
            m = re.search(r"(\d+)\s+pass", output, re.IGNORECASE)
            passed = int(m.group(1)) if m else 0
            return GoalResult(
                achieved=True,
                reason=f"All{f' {passed}' if passed else ''} bun tests passed",
                details={"stdout": result.stdout, "stderr": result.stderr},
            )

        # Extract failure count
        failed_m = re.search(r"(\d+)\s+fail", output, re.IGNORECASE)
        failed = int(failed_m.group(1)) if failed_m else "?"
        failures = _extract_bun_failures(output)
        return GoalResult(
            achieved=False,
            reason=f"{failed} bun test(s) failed",
            details={"failures": failures, "stdout": result.stdout, "stderr": result.stderr},
        )

    def system_prompt(self) -> str:
        return (
            "Your goal is to make ALL bun tests pass in the project.\n"
            "Strategy:\n"
            "1. Scan the project structure (list files, read package.json).\n"
            "2. Run `bun test` to see the current state.\n"
            "3. Read failing test files and the source files they test.\n"
            "4. Fix the source code (not the tests, unless the test has a genuine bug).\n"
            "5. Re-run `bun test` to verify your fix.\n"
            "6. Repeat until all tests pass.\n\n"
            "Rules:\n"
            "- Use TypeScript/JavaScript best practices.\n"
            "- Make minimal targeted changes.\n"
            "- After each fix, always re-run the tests to confirm progress.\n"
        )


def _extract_bun_failures(output: str) -> list[str]:
    """Extract failing test names from bun test verbose output."""
    failures = []
    for line in output.splitlines():
        if "✗" in line or "× " in line or "FAIL" in line:
            failures.append(line.strip())
    return failures[:20]
