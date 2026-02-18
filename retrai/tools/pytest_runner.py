"""Run pytest and return structured results."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PytestRunResult:
    exit_code: int
    passed: int
    failed: int
    error: int
    total: int
    failures: list[dict]
    stdout: str
    stderr: str
    timed_out: bool = False


def run_pytest(cwd: str, timeout: float = 120.0) -> PytestRunResult:
    """Run pytest --json-report synchronously, return structured result."""
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
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return PytestRunResult(
            exit_code=-1,
            passed=0,
            failed=0,
            error=0,
            total=0,
            failures=[],
            stdout="",
            stderr="pytest timed out",
            timed_out=True,
        )
    except FileNotFoundError:
        return PytestRunResult(
            exit_code=-1,
            passed=0,
            failed=0,
            error=0,
            total=0,
            failures=[],
            stdout="",
            stderr="pytest not found",
        )

    report: dict = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text())
        except json.JSONDecodeError:
            pass

    summary = report.get("summary", {})
    failures = _extract_failures(report)

    return PytestRunResult(
        exit_code=result.returncode,
        passed=summary.get("passed", 0),
        failed=summary.get("failed", 0),
        error=summary.get("error", 0),
        total=summary.get("total", 0),
        failures=failures,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _extract_failures(report: dict) -> list[dict]:
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
