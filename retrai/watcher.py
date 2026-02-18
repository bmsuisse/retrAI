"""File watcher — auto-runs goals when project files change."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directories and extensions to ignore
IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "dist", "build", ".eggs", "target", ".retrai",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".o", ".a", ".dll",
    ".exe", ".bin", ".whl", ".egg-info",
}


def _should_ignore(path: Path) -> bool:
    """Check if a file path should be ignored."""
    parts = path.parts
    for part in parts:
        if part in IGNORE_DIRS:
            return True
    if path.suffix in IGNORE_EXTENSIONS:
        return True
    return False


class FileWatcher:
    """Watch a project directory for file changes and trigger goal runs.

    Uses polling-based watching for cross-platform compatibility.
    Debounces rapid changes to avoid running the agent multiple times.

    Usage:
        watcher = FileWatcher(
            cwd="/path/to/project",
            goal_name="pytest",
            model_name="claude-sonnet-4-6",
            debounce_ms=1000,
        )
        await watcher.run()  # Blocks until Ctrl+C
    """

    def __init__(
        self,
        cwd: str,
        goal_name: str | None = None,
        model_name: str = "claude-sonnet-4-6",
        max_iterations: int = 20,
        debounce_ms: int = 1000,
        poll_interval_ms: int = 500,
        on_change: Any = None,
        on_run_start: Any = None,
        on_run_end: Any = None,
    ) -> None:
        self.cwd = Path(cwd).resolve()
        self.goal_name = goal_name
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.debounce_seconds = debounce_ms / 1000.0
        self.poll_interval = poll_interval_ms / 1000.0
        self._on_change = on_change
        self._on_run_start = on_run_start
        self._on_run_end = on_run_end
        self._running = False
        self._agent_running = False
        self._snapshot: dict[str, float] = {}

    def _take_snapshot(self) -> dict[str, float]:
        """Take a snapshot of all file modification times."""
        snapshot: dict[str, float] = {}
        try:
            for path in self.cwd.rglob("*"):
                if not path.is_file():
                    continue
                if _should_ignore(path):
                    continue
                try:
                    rel = str(path.relative_to(self.cwd))
                    snapshot[rel] = path.stat().st_mtime
                except (OSError, ValueError):
                    pass
        except OSError:
            pass
        return snapshot

    def _detect_changes(
        self, old: dict[str, float], new: dict[str, float]
    ) -> list[str]:
        """Detect which files changed between two snapshots."""
        changed: list[str] = []

        # Modified or new files
        for path, mtime in new.items():
            if path not in old or old[path] != mtime:
                changed.append(path)

        # Deleted files
        for path in old:
            if path not in new:
                changed.append(path)

        return changed

    async def run(self) -> None:
        """Main watch loop. Blocks until stopped."""
        self._running = True
        self._snapshot = self._take_snapshot()

        logger.info(
            "Watching %s for changes (debounce: %dms)",
            self.cwd,
            int(self.debounce_seconds * 1000),
        )

        last_change_time: float = 0.0
        pending_changes: list[str] = []

        while self._running:
            await asyncio.sleep(self.poll_interval)

            new_snapshot = self._take_snapshot()
            changes = self._detect_changes(self._snapshot, new_snapshot)

            if changes:
                self._snapshot = new_snapshot
                pending_changes = changes
                last_change_time = time.monotonic()

                if self._on_change:
                    await self._on_change(changes)

            # Check if debounce period has elapsed and we have pending changes
            if (
                pending_changes
                and not self._agent_running
                and (time.monotonic() - last_change_time)
                >= self.debounce_seconds
            ):
                await self._trigger_run(pending_changes)
                pending_changes = []

    async def _trigger_run(self, changed_files: list[str]) -> None:
        """Trigger an agent run for the changed files."""
        self._agent_running = True

        try:
            if self._on_run_start:
                await self._on_run_start(changed_files)

            goal_name = self.goal_name or await self._auto_detect_goal()

            result = await self._run_agent(goal_name)

            if self._on_run_end:
                await self._on_run_end(goal_name, result)

            # Update snapshot after run (agent may have changed files)
            self._snapshot = self._take_snapshot()

        except Exception as e:
            logger.error("Watch run failed: %s", e)
        finally:
            self._agent_running = False

    async def _auto_detect_goal(self) -> str:
        """Auto-detect the best goal for this project."""
        try:
            from retrai.goals.detector import detect_goal
            return detect_goal(str(self.cwd))
        except Exception:
            return "pytest"  # Safe default

    async def _run_agent(self, goal_name: str) -> dict[str, Any]:
        """Run the agent with the given goal."""
        import uuid

        from retrai.agent.graph import build_graph
        from retrai.events.bus import AsyncEventBus
        from retrai.goals.registry import get_goal

        run_id = str(uuid.uuid4())
        goal = get_goal(goal_name)
        event_bus = AsyncEventBus()
        graph = build_graph(hitl_enabled=False)

        initial_state = {
            "messages": [],
            "pending_tool_calls": [],
            "tool_results": [],
            "goal_achieved": False,
            "goal_reason": "",
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "hitl_enabled": False,
            "model_name": self.model_name,
            "cwd": str(self.cwd),
            "run_id": run_id,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "failed_strategies": [],
            "consecutive_failures": 0,
        }

        config = {
            "configurable": {
                "thread_id": run_id,
                "event_bus": event_bus,
                "goal": goal,
            }
        }

        final_state: dict[str, Any] = {}
        async for state in graph.astream(initial_state, config=config):
            final_state = state

        # Get final snapshot
        snapshot = graph.get_state(config)
        if snapshot and snapshot.values:
            return dict(snapshot.values)
        return final_state

    def stop(self) -> None:
        """Stop the watch loop."""
        self._running = False
