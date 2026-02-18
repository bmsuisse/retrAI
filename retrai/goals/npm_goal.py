"""npm test goal: run npm test and check if all tests pass."""

from __future__ import annotations

import subprocess

from retrai.goals.base import GoalBase, GoalResult


class NpmTestGoal(GoalBase):
    name = "npm-test"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run npm test and check for failures."""
        cmd = ["npm", "test", "--", "--passWithNoTests"]
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=180,
                env={**__import__("os").environ, "CI": "true", "FORCE_COLOR": "0"},
            )
        except subprocess.TimeoutExpired:
            return GoalResult(
                achieved=False,
                reason="npm test timed out after 180s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="npm not found — is Node.js installed?",
                details={"error": "npm_not_found"},
            )

        output = result.stdout + result.stderr
        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason="All npm tests passed",
                details={"stdout": result.stdout, "stderr": result.stderr},
            )

        failures = [line.strip() for line in output.splitlines() if "FAIL" in line or "✕" in line]
        return GoalResult(
            achieved=False,
            reason="npm test failed",
            details={"failures": failures[:20], "stdout": result.stdout, "stderr": result.stderr},
        )

    def system_prompt(self) -> str:
        return (
            "Your goal is to make ALL npm/Jest/Vitest tests pass in the project.\n"
            "Strategy:\n"
            "1. Scan the project (list files, read package.json to understand test framework).\n"
            "2. Run `npm test` to see the current state.\n"
            "3. Read failing test files and the source files they test.\n"
            "4. Fix the source code (not the tests, unless the test is wrong).\n"
            "5. Re-run `npm test` to verify.\n"
            "6. Repeat until all tests pass.\n\n"
            "Rules:\n"
            "- Use TypeScript/JavaScript best practices.\n"
            "- Make minimal targeted changes.\n"
        )
