"""AI eval goal: run the AI-generated eval harness with pytest."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from retrai.goals.base import GoalBase, GoalResult
from retrai.goals.pytest_goal import _extract_failures


class AiEvalGoal(GoalBase):
    name = "ai-eval"

    def _load_config(self, cwd: str) -> dict:
        config_path = Path(cwd) / ".retrai" / "ai_eval_config.json"
        if config_path.exists():
            try:
                return json.loads(config_path.read_text())
            except json.JSONDecodeError:
                pass
        return {}

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run the AI-generated eval harness with pytest."""
        harness = Path(cwd) / ".retrai" / "eval_harness.py"
        if not harness.exists():
            return GoalResult(
                achieved=False,
                reason=(
                    "No eval harness found at .retrai/eval_harness.py. "
                    'Run `retrai generate-eval "<description>"` first.'
                ),
                details={"error": "no_harness"},
            )

        report_path = Path(cwd) / ".retrai" / ".eval_report.json"
        cmd = [
            "python",
            "-m",
            "pytest",
            str(harness),
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
                reason="eval harness timed out after 120s",
                details={"error": "timeout"},
            )

        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
            except json.JSONDecodeError:
                report = {}
        else:
            report = {}

        summary = report.get("summary", {})
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        error = summary.get("error", 0)
        total = summary.get("total", 0)

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason=f"All {total} eval test(s) passed",
                details={"summary": summary},
            )

        failures = _extract_failures(report)
        return GoalResult(
            achieved=False,
            reason=f"{failed + error} eval test(s) failed out of {total} (passed: {passed})",
            details={
                "failures": failures,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )

    def system_prompt(self, cwd: str = ".") -> str:
        meta = self._load_config(cwd)
        description = meta.get("description", "")
        harness_file = meta.get("harness_file", ".retrai/eval_harness.py")

        desc_section = f"\nOriginal goal description:\n  {description}\n" if description else ""

        return (
            f"Your goal is to make the AI-generated eval harness pass.\n"
            f"{desc_section}"
            f"\nThe eval harness is at: {harness_file}\n"
            "Strategy:\n"
            "1. Read the eval harness to understand exactly what is being tested.\n"
            "2. Identify which source files need to be changed.\n"
            "3. Run `python -m pytest .retrai/eval_harness.py -v` to see failures.\n"
            "4. Fix the source code to make the tests pass.\n"
            "5. Re-run the harness to verify progress.\n"
            "6. Repeat until all harness tests pass.\n\n"
            "Rules:\n"
            "- Do NOT modify the eval harness file itself.\n"
            "- Only change the source code being tested.\n"
            "- Make minimal targeted changes.\n"
        )
