"""Lint goal: fix all linter violations (ruff, eslint, clippy, golangci-lint)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import yaml

from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)

_CONFIG_FILE = ".retrai.yml"


def _load_config(cwd: str) -> dict:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _detect_linter(cwd: str, cfg: dict) -> tuple[str, list[str]]:
    """Auto-detect the linter from project files.

    Returns (linter_name, command_list).
    """
    root = Path(cwd)

    # Explicit override in .retrai.yml
    lint_cmd = cfg.get("lint_command")
    if lint_cmd:
        return "custom", lint_cmd.split()

    # Python: ruff
    if (root / ".ruff.toml").exists():
        return "ruff", ["ruff", "check", "."]
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            if "[tool.ruff]" in content:
                return "ruff", ["ruff", "check", "."]
        except OSError:
            pass

    # JavaScript/TypeScript: eslint
    for eslint_cfg in (".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
                       ".eslintrc.yaml", "eslint.config.js", "eslint.config.mjs"):
        if (root / eslint_cfg).exists():
            return "eslint", ["npx", "eslint", "."]

    # Rust: clippy
    if (root / "Cargo.toml").exists():
        return "clippy", ["cargo", "clippy", "--", "-D", "warnings"]

    # Go: golangci-lint
    if (root / ".golangci.yml").exists() or (root / ".golangci.yaml").exists():
        return "golangci-lint", ["golangci-lint", "run"]

    return "none", []


class LintGoal(GoalBase):
    """Fix all linter violations in the project.

    Auto-detects the linter (ruff, eslint, clippy, golangci-lint) from project files.

    `.retrai.yml` (optional):
    ```yaml
    goal: lint
    lint_command: "ruff check ."  # optional override
    ```
    """

    name = "lint"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        linter, cmd = _detect_linter(cwd, cfg)

        if linter == "none":
            return GoalResult(
                achieved=False,
                reason=(
                    "No linter config detected. Supported: ruff (.ruff.toml or [tool.ruff] in "
                    "pyproject.toml), eslint (.eslintrc*), clippy (Cargo.toml), "
                    "golangci-lint (.golangci.yml). Or set `lint_command` in .retrai.yml."
                ),
                details={"cwd": cwd},
            )

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
                reason=f"Linter timed out after 120s: {' '.join(cmd)}",
                details={"command": cmd, "error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason=f"Linter not found: {cmd[0]}. Install it first.",
                details={"error": "linter_not_found", "linter": linter},
            )

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason=f"No lint violations found ({linter})",
                details={"linter": linter, "command": cmd},
            )

        output = (result.stdout + result.stderr)[-4000:]
        # Count violations roughly
        violation_lines = [
            line for line in output.splitlines()
            if line.strip() and not line.startswith(" ")
        ]
        count = len(violation_lines)

        return GoalResult(
            achieved=False,
            reason=(
                f"{linter}: {count} violation(s) found (exit {result.returncode})\n\n"
                f"{output}"
            ),
            details={
                "linter": linter,
                "command": cmd,
                "returncode": result.returncode,
                "output": output,
                "violation_count": count,
            },
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        linter, cmd = _detect_linter(cwd, cfg)
        cmd_str = " ".join(cmd) if cmd else "ruff check . / eslint . / cargo clippy"

        return (
            f"## Goal: Fix All Lint Violations\n\n"
            f"Make the following command exit with code 0 (zero violations):\n"
            f"```\n{cmd_str}\n```\n\n"
            "**Strategy**:\n"
            "1. Run the linter via `bash_exec` to see all current violations.\n"
            "2. Group violations by file and fix them in batches.\n"
            "3. For auto-fixable violations, try running the linter with `--fix` flag first.\n"
            "4. For manual fixes, read each file, understand the violation, and fix it.\n"
            "5. Re-run the linter after each batch to track progress.\n\n"
            "**Tips**:\n"
            "- `ruff check . --fix` auto-fixes many violations\n"
            "- `eslint . --fix` auto-fixes many JS/TS violations\n"
            "- `cargo clippy --fix` auto-fixes some Rust violations\n"
            "- Focus on errors first, then warnings\n"
            "- Don't suppress violations with `# noqa` unless genuinely necessary\n"
        )
