"""Git integration tools — diff, status, and log for the agent."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass


@dataclass
class GitResult:
    output: str
    error: str
    is_git_repo: bool


async def git_diff(cwd: str, staged: bool = False) -> str:
    """Show uncommitted file changes.

    Args:
        cwd: Project root directory.
        staged: If True, show staged changes (``git diff --staged``).

    Returns:
        Unified diff output, or a message if no changes or not a git repo.
    """
    result = await _run_git(
        ["git", "diff", "--staged"] if staged else ["git", "diff"],
        cwd,
    )
    if not result.is_git_repo:
        return "Not a git repository."
    if not result.output.strip():
        label = "staged" if staged else "unstaged"
        return f"No {label} changes."
    return result.output[:8000]


async def git_status(cwd: str) -> str:
    """Show working tree status (short format).

    Args:
        cwd: Project root directory.

    Returns:
        Short git status output.
    """
    result = await _run_git(["git", "status", "--short"], cwd)
    if not result.is_git_repo:
        return "Not a git repository."
    if not result.output.strip():
        return "Working tree clean."
    return result.output[:4000]


async def git_log(cwd: str, count: int = 10) -> str:
    """Show recent commit log.

    Args:
        cwd: Project root directory.
        count: Number of recent commits to show.

    Returns:
        Formatted git log.
    """
    result = await _run_git(
        [
            "git",
            "log",
            f"-{count}",
            "--oneline",
            "--no-decorate",
        ],
        cwd,
    )
    if not result.is_git_repo:
        return "Not a git repository."
    if not result.output.strip():
        return "No commits yet."
    return result.output[:4000]


async def _run_git(cmd: list[str], cwd: str) -> GitResult:
    """Execute a git command asynchronously."""

    def _run() -> GitResult:
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return GitResult(
                output=proc.stdout,
                error=proc.stderr,
                is_git_repo=True,
            )
        except FileNotFoundError:
            return GitResult(
                output="",
                error="git not installed",
                is_git_repo=False,
            )
        except subprocess.TimeoutExpired:
            return GitResult(
                output="",
                error="git command timed out",
                is_git_repo=True,
            )

    result = await asyncio.get_event_loop().run_in_executor(None, _run)

    # Detect "not a git repository" from stderr
    if "not a git repository" in result.error.lower():
        result.is_git_repo = False

    return result
