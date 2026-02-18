"""Docker goal: build a Docker image or bring up docker-compose without errors."""

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


def _detect_docker_command(cwd: str, cfg: dict) -> tuple[str, list[str]]:
    """Detect which docker command to run.

    Returns (mode, command_list).
    mode is 'compose' or 'build'.
    """
    root = Path(cwd)

    # Explicit override in .retrai.yml
    docker_cmd = cfg.get("docker_command")
    if docker_cmd:
        return "custom", docker_cmd.split()

    # Prefer docker-compose / docker compose
    for compose_file in (
        "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"
    ):
        if (root / compose_file).exists():
            return "compose", ["docker", "compose", "up", "--build", "--no-start"]

    # Fall back to plain docker build
    if (root / "Dockerfile").exists():
        return "build", ["docker", "build", "."]

    return "none", []


class DockerGoal(GoalBase):
    """Fix Docker build or docker-compose errors.

    `.retrai.yml` (optional):
    ```yaml
    goal: docker-build
    docker_command: "docker compose up --build --no-start"  # optional override
    ```

    The agent is done when the docker command exits with code 0.
    """

    name = "docker-build"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        mode, cmd = _detect_docker_command(cwd, cfg)

        if mode == "none":
            return GoalResult(
                achieved=False,
                reason=(
                    "No Dockerfile or docker-compose.yml found in the project. "
                    "Create one or set `docker_command` in .retrai.yml."
                ),
                details={"cwd": cwd},
            )

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
                reason=f"Docker command timed out after 300s: {' '.join(cmd)}",
                details={"command": cmd, "error": "timeout"},
            )
        except FileNotFoundError:
            return GoalResult(
                achieved=False,
                reason="Docker not found. Install Docker Desktop or Docker Engine.",
                details={"error": "docker_not_found"},
            )

        if result.returncode == 0:
            return GoalResult(
                achieved=True,
                reason=f"Docker command succeeded: {' '.join(cmd)}",
                details={"command": cmd, "mode": mode},
            )

        # Extract last 3000 chars of stderr for the agent
        stderr = (result.stderr or result.stdout or "")[-3000:]
        return GoalResult(
            achieved=False,
            reason=(
                f"Docker command failed (exit {result.returncode}): {' '.join(cmd)}\n\n"
                f"Error output:\n{stderr}"
            ),
            details={
                "command": cmd,
                "returncode": result.returncode,
                "stderr": stderr,
                "stdout": result.stdout[-2000:],
            },
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        mode, cmd = _detect_docker_command(cwd, cfg)
        cmd_str = " ".join(cmd) if cmd else "docker build . / docker compose up --build"

        return (
            f"## Goal: Fix Docker Build Errors\n\n"
            f"Make the following command succeed with exit code 0:\n"
            f"```\n{cmd_str}\n```\n\n"
            "**Strategy**:\n"
            "1. Read the `Dockerfile` and/or `docker-compose.yml` to understand the setup.\n"
            "2. Run the docker command via `bash_exec` to see the current errors.\n"
            "3. Identify the root cause (missing files, wrong base image, bad ENV, etc.).\n"
            "4. Fix the `Dockerfile`, `docker-compose.yml`, or referenced files.\n"
            "5. Re-run to verify the fix.\n\n"
            "**Common issues**:\n"
            "- `COPY` fails → file doesn't exist at build context path\n"
            "- `RUN pip install` fails → wrong package name, missing system deps\n"
            "- Port conflicts → change the host port mapping\n"
            "- Missing env vars → add them to `docker-compose.yml` or `.env`\n"
            "- Base image not found → check image name and tag on Docker Hub\n"
        )
