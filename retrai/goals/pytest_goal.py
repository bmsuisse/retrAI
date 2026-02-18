"""Pytest goal: run pytest and check if all tests pass."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from retrai.goals.base import GoalBase, GoalResult


class PytestGoal(GoalBase):
    name = "pytest"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run pytest --json-report and check for failures."""
        report_path = Path(cwd) / ".pytest_report.json"
        cmd = [
            "python",
            "-m",
            "pytest",
            "--json-report",
            f"--json-report-file={report_path}",
            "--tb=short",
            "-q",
            "--no-header",
        ]
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
                reason="pytest timed out after 120s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="pytest not found in the project environment",
                details={"error": "pytest_not_found"},
            )

        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
            except json.JSONDecodeError:
                report = {}
        else:
            report = {}

        exit_code = result.returncode
        summary = report.get("summary", {})
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        error = summary.get("error", 0)
        total = summary.get("total", 0)

        if exit_code == 0:
            return GoalResult(
                achieved=True,
                reason=f"All {total} tests passed",
                details={"summary": summary, "report": report},
            )
        elif exit_code == 5:
            return GoalResult(
                achieved=False,
                reason="No tests were collected",
                details={"summary": summary, "stdout": result.stdout, "stderr": result.stderr},
            )
        else:
            failures = _extract_failures(report)
            return GoalResult(
                achieved=False,
                reason=f"{failed + error} test(s) failed out of {total} (passed: {passed})",
                details={
                    "summary": summary,
                    "failures": failures,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "report": report,
                },
            )

    def system_prompt(self) -> str:
        return (
            "Your goal is to make ALL pytest tests pass in the project.\n"
            "Strategy:\n"
            "1. First, scan the project structure (list files, read pyproject.toml/setup.py).\n"
            "2. Run pytest to see the current state of tests.\n"
            "3. Read failing test files and the source files they test.\n"
            "4. Fix the source code (not the tests, unless tests are genuinely wrong).\n"
            "5. Re-run pytest to verify your fix worked.\n"
            "6. Repeat until all tests pass.\n\n"
            "Rules:\n"
            "- Only modify source files, not test files (unless the test itself has a bug).\n"
            "- Make minimal targeted changes.\n"
            "- After each fix, always re-run pytest to confirm progress.\n"
            "- If you are stuck after 3 attempts on the same failure, try a different approach.\n"
        )


def _extract_failures(report: dict) -> list[dict]:
    """Extract structured failure information from a pytest-json-report."""
    failures = []
    for test in report.get("tests", []):
        if test.get("outcome") in ("failed", "error"):
            failure = {
                "nodeid": test.get("nodeid", ""),
                "outcome": test.get("outcome", ""),
            }
            call = test.get("call", {})
            if call:
                longrepr = call.get("longrepr", "")
                failure["longrepr"] = longrepr[:4000] if longrepr else ""
            failures.append(failure)
    return failures
