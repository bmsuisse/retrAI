"""Registry of active agent runs."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from retrai.config import RunConfig
from retrai.events.bus import AsyncEventBus


@dataclass
class RunEntry:
    run_id: str
    config: RunConfig
    bus: AsyncEventBus
    task: asyncio.Task | None = None
    status: str = "pending"  # pending | running | achieved | failed | aborted
    graph: Any = None
    final_state: dict | None = None
    error: str | None = None


class RunManager:
    """In-process registry for all active/completed runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RunEntry] = {}

    def create(self, config: RunConfig) -> RunEntry:
        entry = RunEntry(run_id=config.run_id, config=config, bus=AsyncEventBus())
        self._runs[config.run_id] = entry
        return entry

    def get(self, run_id: str) -> RunEntry | None:
        return self._runs.get(run_id)

    def get_or_raise(self, run_id: str) -> RunEntry:
        entry = self._runs.get(run_id)
        if not entry:
            raise KeyError(f"Run not found: {run_id}")
        return entry

    def list_runs(self) -> list[RunEntry]:
        return list(self._runs.values())

    async def start_run(self, run_id: str) -> None:
        """Launch the agent graph as a background asyncio task."""
        from retrai.agent.graph import build_graph
        from retrai.goals.registry import get_goal

        entry = self.get_or_raise(run_id)
        cfg = entry.config
        goal = get_goal(cfg.goal)
        graph = build_graph(hitl_enabled=cfg.hitl_enabled)
        entry.graph = graph
        entry.status = "running"

        initial_state = {
            "messages": [],
            "pending_tool_calls": [],
            "tool_results": [],
            "goal_achieved": False,
            "goal_reason": "",
            "iteration": 0,
            "max_iterations": cfg.max_iterations,
            "hitl_enabled": cfg.hitl_enabled,
            "model_name": cfg.model_name,
            "cwd": cfg.cwd,
            "run_id": cfg.run_id,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "failed_strategies": [],
            "consecutive_failures": 0,
        }

        run_config = {
            "configurable": {
                "thread_id": run_id,
                "event_bus": entry.bus,
                "goal": goal,
            }
        }

        started_at = time.time()

        async def _run() -> None:
            from retrai.events.types import AgentEvent
            from retrai.history import save_run_history

            try:
                final = await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]
                entry.final_state = final
                entry.status = "achieved" if final.get("goal_achieved") else "failed"
                await entry.bus.publish(
                    AgentEvent(
                        kind="run_end",
                        run_id=run_id,
                        iteration=final.get("iteration", 0),
                        payload={
                            "status": entry.status,
                            "reason": final.get("goal_reason", ""),
                            "total_tokens": final.get("total_tokens", 0),
                            "estimated_cost_usd": final.get("estimated_cost_usd", 0.0),
                        },
                    )
                )
                # Persist run history
                try:
                    save_run_history(
                        cwd=cfg.cwd,
                        run_id=run_id,
                        goal=cfg.goal,
                        model=cfg.model_name,
                        status=entry.status,
                        iterations=final.get("iteration", 0),
                        max_iterations=cfg.max_iterations,
                        total_tokens=final.get("total_tokens", 0),
                        estimated_cost_usd=final.get("estimated_cost_usd", 0.0),
                        started_at=started_at,
                        reason=final.get("goal_reason", ""),
                    )
                except Exception:
                    pass  # Don't let history IO crash a run
            except Exception as e:
                entry.status = "failed"
                entry.error = str(e)
                await entry.bus.publish(
                    AgentEvent(
                        kind="error",
                        run_id=run_id,
                        iteration=0,
                        payload={"error": str(e)},
                    )
                )
            finally:
                await entry.bus.close()

        entry.task = asyncio.create_task(_run())

    async def resume_run(self, run_id: str, human_input: Any) -> None:
        """Resume a HITL-paused run with human input."""
        entry = self.get_or_raise(run_id)
        if not entry.graph:
            raise RuntimeError("Run has no graph")

        run_config = {
            "configurable": {
                "thread_id": run_id,
                "event_bus": entry.bus,
                "goal": None,  # will be resolved by the graph state
            }
        }
        await entry.graph.ainvoke(
            {"messages": []},
            config=run_config,
            command={"resume": human_input},
        )


# Global singleton used by FastAPI
run_manager = RunManager()
