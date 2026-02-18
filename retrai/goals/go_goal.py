"""Go test goal: run go test and check if all tests pass."""

from __future__ import annotations

import json
import subprocess

from retrai.goals.base import GoalBase, GoalResult


class GoTestGoal(GoalBase):
    name = "go-test"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run go test ./... -json and check for failures."""
        cmd = ["go", "test", "./...", "-json", "-count=1"]
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return GoalResult(
                achieved=False,
                reason="go test timed out after 300s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="go not found — is Go installed?",
                details={"error": "go_not_found"},
            )

        failures = _parse_go_failures(result.stdout)

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason="All go tests passed",
                details={"stdout": result.stdout[:2000]},
            )

        return GoalResult(
            achieved=False,
            reason=f"{len(failures)} go test(s) failed",
            details={
                "failures": failures,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
            },
        )

    def system_prompt(self) -> str:
        return (
            "Your goal is to make ALL go tests pass in the project.\n"
            "Strategy:\n"
            "1. Scan the project (list files, read go.mod).\n"
            "2. Run `go build ./...` to check for compilation errors.\n"
            "3. Run `go test ./...` to see the current test state.\n"
            "4. Read failing test files and the source files they test.\n"
            "5. Fix the source code (not the tests, unless the test is wrong).\n"
            "6. Re-run `go test ./...` to verify.\n"
            "7. Repeat until all tests pass.\n\n"
            "Rules:\n"
            "- Use idiomatic Go: error returns, interfaces, goroutines where appropriate.\n"
            "- Fix build errors before test failures.\n"
            "- Make minimal targeted changes.\n"
        )


def _parse_go_failures(stdout: str) -> list[dict]:
    """Parse JSON lines from go test -json output to find failures."""
    failures = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("Action") == "fail" and entry.get("Test"):
            failures.append(
                {
                    "package": entry.get("Package", ""),
                    "test": entry.get("Test", ""),
                    "elapsed": entry.get("Elapsed", 0),
                }
            )
    return failures
