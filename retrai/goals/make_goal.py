"""Make test goal: run make test and check if it exits successfully."""

from __future__ import annotations

import subprocess

from retrai.goals.base import GoalBase, GoalResult


class MakeTestGoal(GoalBase):
    name = "make-test"

    def __init__(self, make_target: str = "test") -> None:
        self.make_target = make_target

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run make <target> and check for success."""
        cmd = ["make", self.make_target]
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
                reason=f"make {self.make_target} timed out after 300s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="make not found",
                details={"error": "make_not_found"},
            )

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason=f"make {self.make_target} passed",
                details={"stdout": result.stdout[:2000]},
            )

        return GoalResult(
            achieved=False,
            reason=f"make {self.make_target} failed (exit {result.returncode})",
            details={"stdout": result.stdout[:2000], "stderr": result.stderr[:1000]},
        )

    def system_prompt(self) -> str:
        return (
            f"Your goal is to make `make {self.make_target}` exit with code 0.\n"
            "Strategy:\n"
            "1. Scan the project structure (list files, read Makefile).\n"
            f"2. Run `make {self.make_target}` to see the current state.\n"
            "3. Read the relevant source files and understand the failures.\n"
            "4. Fix the source code to make the target pass.\n"
            f"5. Re-run `make {self.make_target}` to verify.\n"
            "6. Repeat until it passes.\n\n"
            "Rules:\n"
            "- Understand the Makefile targets and their dependencies.\n"
            "- Make minimal targeted changes.\n"
        )
