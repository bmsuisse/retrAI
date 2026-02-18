"""Pipeline runner — chain multiple goals sequentially."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from retrai.events.bus import AsyncEventBus
from retrai.goals.registry import get_goal, list_goals

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    goal_name: str
    achieved: bool
    reason: str
    iterations_used: int
    tokens_used: int
    cost_usd: float
    duration_seconds: float
    error: str | None = None


@dataclass
class PipelineResult:
    """Aggregated result of a full pipeline run."""

    steps: list[StepResult] = field(default_factory=list)
    status: str = "pending"  # "achieved" | "partial" | "failed"
    total_tokens: int = 0
    total_cost: float = 0.0
    total_duration: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for s in self.steps if s.achieved)

    @property
    def failed(self) -> int:
        return sum(1 for s in self.steps if not s.achieved)


class PipelineRunner:
    """Run multiple goals in sequence, passing context between them.

    Usage:
        runner = PipelineRunner(
            steps=["pytest", "pyright", "ruff"],
            cwd="/path/to/project",
            model_name="claude-sonnet-4-6",
        )
        result = await runner.run()
    """

    def __init__(
        self,
        steps: list[str],
        cwd: str,
        model_name: str = "claude-sonnet-4-6",
        max_iterations_per_step: int = 30,
        continue_on_error: bool = False,
        on_step_start: Any = None,
        on_step_end: Any = None,
    ) -> None:
        self.steps = steps
        self.cwd = cwd
        self.model_name = model_name
        self.max_iterations = max_iterations_per_step
        self.continue_on_error = continue_on_error
        self._on_step_start = on_step_start
        self._on_step_end = on_step_end

        # Validate all goals exist upfront
        available = list_goals()
        for step in steps:
            if step not in available:
                msg = f"Unknown goal '{step}'. Available: {', '.join(available)}"
                raise ValueError(msg)

    async def run(self) -> PipelineResult:
        """Execute all pipeline steps sequentially."""
        from retrai.agent.graph import build_graph

        result = PipelineResult()
        pipeline_start = time.monotonic()

        for i, goal_name in enumerate(self.steps):
            step_num = i + 1
            logger.info(
                "Pipeline step %d/%d: %s",
                step_num,
                len(self.steps),
                goal_name,
            )

            if self._on_step_start:
                await self._on_step_start(step_num, goal_name)

            step_result = await self._run_step(goal_name, build_graph)

            result.steps.append(step_result)
            result.total_tokens += step_result.tokens_used
            result.total_cost += step_result.cost_usd

            if self._on_step_end:
                await self._on_step_end(step_num, goal_name, step_result)

            if not step_result.achieved and not self.continue_on_error:
                logger.warning(
                    "Pipeline stopped at step %d (%s): %s",
                    step_num,
                    goal_name,
                    step_result.reason,
                )
                break

        result.total_duration = time.monotonic() - pipeline_start

        # Determine overall status
        if all(s.achieved for s in result.steps):
            result.status = "achieved"
        elif any(s.achieved for s in result.steps):
            result.status = "partial"
        else:
            result.status = "failed"

        return result

    async def _run_step(
        self,
        goal_name: str,
        build_graph: Any,
    ) -> StepResult:
        """Run a single pipeline step."""
        step_start = time.monotonic()
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
            "cwd": self.cwd,
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

        try:
            final_state = None
            async for state in graph.astream(initial_state, config=config):
                final_state = state

            # Extract final state from the last node output
            achieved = False
            reason = "No result"
            tokens = 0
            cost = 0.0

            if final_state:
                # The stream yields {node_name: state_update} dicts
                last_update = list(final_state.values())[-1]
                if isinstance(last_update, dict):
                    achieved = last_update.get("goal_achieved", False)
                    reason = last_update.get("goal_reason", "No reason")
                    tokens = last_update.get("total_tokens", 0)
                    cost = last_update.get("estimated_cost_usd", 0.0)

            # Get final snapshot for accurate totals
            snapshot = graph.get_state(config)
            if snapshot and snapshot.values:
                achieved = snapshot.values.get("goal_achieved", achieved)
                reason = snapshot.values.get("goal_reason", reason)
                tokens = snapshot.values.get("total_tokens", tokens)
                cost = snapshot.values.get("estimated_cost_usd", cost)
                iteration = snapshot.values.get("iteration", 0)
            else:
                iteration = 0

            return StepResult(
                goal_name=goal_name,
                achieved=achieved,
                reason=reason,
                iterations_used=iteration,
                tokens_used=tokens,
                cost_usd=cost,
                duration_seconds=time.monotonic() - step_start,
            )

        except Exception as e:
            logger.error("Pipeline step '%s' failed: %s", goal_name, e)
            return StepResult(
                goal_name=goal_name,
                achieved=False,
                reason=f"Step crashed: {e}",
                iterations_used=0,
                tokens_used=0,
                cost_usd=0.0,
                duration_seconds=time.monotonic() - step_start,
                error=str(e),
            )
