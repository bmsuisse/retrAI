"""Worker agent — runs a focused sub-task within the swarm."""

from __future__ import annotations

import logging
import time

from retrai.swarm.types import SubTask, WorkerResult

logger = logging.getLogger(__name__)


async def run_worker(
    subtask: SubTask,
    cwd: str,
    model_name: str = "claude-sonnet-4-6",
    max_iterations: int = 10,
) -> WorkerResult:
    """Run a single worker agent on a focused sub-task.

    Each worker gets its own LangGraph instance, event bus, and scoped
    system prompt. The worker's goal is to complete the sub-task and
    report its findings.
    """
    from retrai.agent.graph import build_graph
    from retrai.events.bus import AsyncEventBus
    from retrai.goals.solver import SolverGoal

    goal = SolverGoal(description=subtask.description)
    bus = AsyncEventBus()
    graph = build_graph(hitl_enabled=False)

    initial_state = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": max_iterations,
        "hitl_enabled": False,
        "model_name": model_name,
        "cwd": cwd,
        "run_id": f"swarm-{subtask.id}",
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }

    run_config = {
        "configurable": {
            "thread_id": f"swarm-{subtask.id}",
            "event_bus": bus,
            "goal": goal,
        }
    }

    started = time.time()
    try:
        final = await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]
        await bus.close()

        status = "achieved" if final.get("goal_achieved") else "failed"
        return WorkerResult(
            task_id=subtask.id,
            description=subtask.description,
            status=status,
            findings=final.get("goal_reason", ""),
            iterations_used=final.get("iteration", 0),
            tokens_used=final.get("total_tokens", 0),
            cost_usd=final.get("estimated_cost_usd", 0.0),
        )
    except Exception as e:
        await bus.close()
        elapsed = time.time() - started
        logger.error(
            "Worker %s failed after %.1fs: %s", subtask.id, elapsed, e
        )
        return WorkerResult(
            task_id=subtask.id,
            description=subtask.description,
            status="failed",
            findings="",
            iterations_used=0,
            tokens_used=0,
            cost_usd=0.0,
            error=str(e),
        )
