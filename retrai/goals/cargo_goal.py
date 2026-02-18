"""Cargo test goal: run cargo test and check if all tests pass."""

from __future__ import annotations

import json
import subprocess

from retrai.goals.base import GoalBase, GoalResult


class CargoTestGoal(GoalBase):
    name = "cargo-test"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run cargo test --message-format json and check for failures."""
        cmd = ["cargo", "test", "--message-format", "json", "--", "--test-output=immediate"]
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
                reason="cargo test timed out after 300s",
                details={"error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="cargo not found — is Rust installed?",
                details={"error": "cargo_not_found"},
            )

        failures = _parse_cargo_failures(result.stdout)

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason="All cargo tests passed",
                details={"stdout": result.stdout[:2000], "stderr": result.stderr[:1000]},
            )

        return GoalResult(
            achieved=False,
            reason=f"{len(failures)} cargo test(s) failed",
            details={
                "failures": failures,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
            },
        )

    def system_prompt(self) -> str:
        return (
            "Your goal is to make ALL cargo tests pass in the project.\n"
            "Strategy:\n"
            "1. Scan the project (list files, read Cargo.toml).\n"
            "2. Run `cargo test` to see the current state.\n"
            "3. Run `cargo build` to check for compilation errors first.\n"
            "4. Read failing test files and the source files they test.\n"
            "5. Fix the source code (not the tests, unless the test is wrong).\n"
            "6. Re-run `cargo test` to verify.\n"
            "7. Repeat until all tests pass.\n\n"
            "Rules:\n"
            "- Use idiomatic Rust: ownership, borrowing, error handling with Result<>.\n"
            "- Fix compilation errors before test failures.\n"
            "- Make minimal targeted changes.\n"
        )


def _parse_cargo_failures(stdout: str) -> list[dict]:
    """Parse JSON lines from cargo test output to find failures."""
    failures = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "test" and msg.get("event") == "failed":
            failures.append(
                {
                    "name": msg.get("name", ""),
                    "stdout": msg.get("stdout", "")[:1000],
                }
            )
    return failures
