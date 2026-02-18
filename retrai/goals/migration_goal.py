"""Migration goal: run DB migrations without errors (alembic, prisma)."""

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


def _detect_migration_tool(cwd: str, cfg: dict) -> tuple[str, list[str]]:
    """Auto-detect the migration tool from project files.

    Returns (tool_name, command_list).
    """
    root = Path(cwd)

    # Explicit override in .retrai.yml
    migrate_cmd = cfg.get("migrate_command")
    if migrate_cmd:
        return "custom", migrate_cmd.split()

    # Alembic
    if (root / "alembic.ini").exists():
        return "alembic", ["alembic", "upgrade", "head"]

    # Prisma
    if (root / "prisma" / "schema.prisma").exists():
        return "prisma", ["npx", "prisma", "migrate", "dev", "--name", "auto"]

    # Django
    if (root / "manage.py").exists():
        return "django", ["python", "manage.py", "migrate"]

    # Flyway
    if (root / "flyway.conf").exists() or (root / "flyway.toml").exists():
        return "flyway", ["flyway", "migrate"]

    return "none", []


class MigrationGoal(GoalBase):
    """Fix database migration errors.

    Auto-detects the migration tool (alembic, prisma, django, flyway) from project files.

    `.retrai.yml` (optional):
    ```yaml
    goal: db-migrate
    migrate_command: "alembic upgrade head"  # optional override
    ```
    """

    name = "db-migrate"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        tool, cmd = _detect_migration_tool(cwd, cfg)

        if tool == "none":
            return GoalResult(
                achieved=False,
                reason=(
                    "No migration tool detected. Supported: alembic (alembic.ini), "
                    "prisma (prisma/schema.prisma), django (manage.py), flyway (flyway.conf). "
                    "Or set `migrate_command` in .retrai.yml."
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
                reason=f"Migration timed out after 120s: {' '.join(cmd)}",
                details={"command": cmd, "error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason=f"Migration tool not found: {cmd[0]}. Install it first.",
                details={"error": "tool_not_found", "tool": tool},
            )

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason=f"Migrations applied successfully ({tool})",
                details={"tool": tool, "command": cmd, "stdout": result.stdout[-1000:]},
            )

        stderr = (result.stderr or result.stdout or "")[-3000:]
        return GoalResult(
            achieved=False,
            reason=(
                f"Migration failed (exit {result.returncode}) with {tool}:\n\n{stderr}"
            ),
            details={
                "tool": tool,
                "command": cmd,
                "returncode": result.returncode,
                "stderr": stderr,
                "stdout": result.stdout[-2000:],
            },
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        tool, cmd = _detect_migration_tool(cwd, cfg)
        cmd_str = " ".join(cmd) if cmd else "alembic upgrade head / npx prisma migrate dev"

        return (
            f"## Goal: Fix Database Migration Errors\n\n"
            f"Make the following command succeed with exit code 0:\n"
            f"```\n{cmd_str}\n```\n\n"
            "**Strategy**:\n"
            "1. Run the migration command via `bash_exec` to see the current error.\n"
            "2. Read the migration files to understand the schema changes.\n"
            "3. Identify the root cause (schema conflict, missing table, bad SQL, etc.).\n"
            "4. Fix the migration file(s) or create a new migration to resolve the conflict.\n"
            "5. Re-run to verify the fix.\n\n"
            "**Common issues**:\n"
            "- Column already exists → check if migration was partially applied\n"
            "- Foreign key constraint → ensure referenced table/column exists first\n"
            "- Alembic head conflict → run `alembic heads` to see diverged heads\n"
            "- Prisma schema error → fix `prisma/schema.prisma` syntax\n"
            "- Django migration conflict → run `python manage.py showmigrations`\n"
            "- Connection error → check DATABASE_URL env var is set correctly\n"
        )
