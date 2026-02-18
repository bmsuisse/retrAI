"""Pyright goal: run pyright and fix all type errors."""

from __future__ import annotations

import json
import subprocess

from retrai.goals.base import GoalBase, GoalResult


class PyrightGoal(GoalBase):
    name = "pyright"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run pyright --outputjson and check for errors."""
        cmd = ["pyright", "--outputjson"]
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
                reason="pyright timed out after 120s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="pyright not found — install with: pip install pyright",
                details={"error": "pyright_not_found"},
            )

        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Pyright may fail to produce JSON for fatal errors
            return GoalResult(
                achieved=False,
                reason="pyright failed to produce output",
                details={"stdout": result.stdout[:2000], "stderr": result.stderr[:500]},
            )

        summary = report.get("summary", {})
        error_count = summary.get("errorCount", 0)
        warning_count = summary.get("warningCount", 0)

        if error_count == 0:
            return GoalResult(
                achieved=True,
                reason=f"pyright: 0 errors, {warning_count} warnings",
                details={"summary": summary},
            )

        diagnostics = _extract_errors(report)
        return GoalResult(
            achieved=False,
            reason=f"pyright: {error_count} error(s), {warning_count} warning(s)",
            details={"diagnostics": diagnostics, "summary": summary},
        )

    def system_prompt(self) -> str:
        return (
            "Your goal is to fix all pyright type errors in the project.\n"
            "Strategy:\n"
            "1. Scan the project (list files, read pyproject.toml or pyrightconfig.json).\n"
            "2. Run `pyright` to see all current type errors.\n"
            "3. Fix each error systematically — start with the files with the most errors.\n"
            "4. Re-run `pyright` after each batch of fixes to track progress.\n"
            "5. Repeat until 0 errors remain.\n\n"
            "Rules:\n"
            "- Add proper type annotations rather than using 'Any' everywhere.\n"
            "- Use 'from __future__ import annotations' for forward references.\n"
            "- Prefer Optional[T] or T | None for nullable types.\n"
            "- Make minimal targeted changes — don't refactor what isn't necessary.\n"
        )


def _extract_errors(report: dict) -> list[dict]:
    """Extract error diagnostics from pyright JSON output."""
    errors = []
    for diag in report.get("generalDiagnostics", []):
        if diag.get("severity") == "error":
            rng = diag.get("range", {})
            start = rng.get("start", {})
            errors.append(
                {
                    "file": diag.get("file", ""),
                    "line": start.get("line", 0) + 1,
                    "message": diag.get("message", ""),
                    "rule": diag.get("rule", ""),
                }
            )
    return errors[:50]
