"""Benchmark runner — compare models on the same task."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRun:
    """Result of a single model benchmark run."""

    model_name: str
    round_num: int
    achieved: bool
    iterations_used: int
    tokens_used: int
    cost_usd: float
    duration_seconds: float
    error: str | None = None


@dataclass
class ModelScore:
    """Aggregated score for a model across rounds."""

    model_name: str
    runs: list[BenchmarkRun] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if not self.runs:
            return 0.0
        return sum(1 for r in self.runs if r.achieved) / len(self.runs)

    @property
    def avg_iterations(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.iterations_used for r in self.runs) / len(self.runs)

    @property
    def avg_tokens(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.tokens_used for r in self.runs) / len(self.runs)

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.runs)

    @property
    def avg_duration(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.duration_seconds for r in self.runs) / len(self.runs)


@dataclass
class BenchmarkResult:
    """Complete benchmark comparison result."""

    goal_name: str
    models: list[ModelScore] = field(default_factory=list)
    rounds: int = 1

    @property
    def winner(self) -> str | None:
        """Best model by success rate, then by iterations."""
        if not self.models:
            return None
        ranked = sorted(
            self.models,
            key=lambda m: (m.success_rate, -m.avg_iterations),
            reverse=True,
        )
        return ranked[0].model_name


class BenchmarkRunner:
    """Compare multiple LLM models on the same task.

    Each model gets a fresh git state between runs to ensure fairness.

    Usage:
        runner = BenchmarkRunner(
            models=["claude-sonnet-4-6", "gpt-4o", "gemini-2.5-pro"],
            goal_name="pytest",
            cwd="/path/to/project",
        )
        result = await runner.run()
    """

    def __init__(
        self,
        models: list[str],
        goal_name: str,
        cwd: str,
        max_iterations: int = 20,
        rounds: int = 1,
        on_run_start: Any = None,
        on_run_end: Any = None,
    ) -> None:
        self.models = models
        self.goal_name = goal_name
        self.cwd = Path(cwd).resolve()
        self.max_iterations = max_iterations
        self.rounds = rounds
        self._on_run_start = on_run_start
        self._on_run_end = on_run_end

    async def run(self) -> BenchmarkResult:
        """Run all benchmark rounds for all models."""
        result = BenchmarkResult(
            goal_name=self.goal_name,
            rounds=self.rounds,
        )

        for model_name in self.models:
            score = ModelScore(model_name=model_name)

            for round_num in range(1, self.rounds + 1):
                logger.info(
                    "Benchmark: %s round %d/%d",
                    model_name,
                    round_num,
                    self.rounds,
                )

                if self._on_run_start:
                    await self._on_run_start(model_name, round_num)

                # Reset git state before each run
                await self._git_reset()

                run_result = await self._run_single(model_name, round_num)
                score.runs.append(run_result)

                if self._on_run_end:
                    await self._on_run_end(model_name, round_num, run_result)

                # Reset after each run too
                await self._git_reset()

            result.models.append(score)

        return result

    async def _run_single(self, model_name: str, round_num: int) -> BenchmarkRun:
        """Run a single benchmark iteration."""
        start_time = time.monotonic()
        run_id = str(uuid.uuid4())

        try:
            from retrai.agent.graph import build_graph
            from retrai.events.bus import AsyncEventBus
            from retrai.goals.registry import get_goal

            goal = get_goal(self.goal_name)
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
                "model_name": model_name,
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

            async for _ in graph.astream(initial_state, config=config):
                pass

            # Get final state
            snapshot = graph.get_state(config)
            achieved = False
            iterations = 0
            tokens = 0
            cost = 0.0

            if snapshot and snapshot.values:
                achieved = snapshot.values.get("goal_achieved", False)
                iterations = snapshot.values.get("iteration", 0)
                tokens = snapshot.values.get("total_tokens", 0)
                cost = snapshot.values.get("estimated_cost_usd", 0.0)

            return BenchmarkRun(
                model_name=model_name,
                round_num=round_num,
                achieved=achieved,
                iterations_used=iterations,
                tokens_used=tokens,
                cost_usd=cost,
                duration_seconds=time.monotonic() - start_time,
            )

        except Exception as e:
            logger.error(
                "Benchmark run failed (%s round %d): %s",
                model_name,
                round_num,
                e,
            )
            return BenchmarkRun(
                model_name=model_name,
                round_num=round_num,
                achieved=False,
                iterations_used=0,
                tokens_used=0,
                cost_usd=0.0,
                duration_seconds=time.monotonic() - start_time,
                error=str(e),
            )

    async def _git_reset(self) -> None:
        """Reset git working tree to clean state."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "checkout",
                ".",
                cwd=str(self.cwd),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            # Also clean untracked files created by the agent
            proc = await asyncio.create_subprocess_exec(
                "git",
                "clean",
                "-fd",
                cwd=str(self.cwd),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception as e:
            logger.warning("Git reset failed: %s", e)


def format_benchmark_table(result: BenchmarkResult) -> str:
    """Format a BenchmarkResult as a comparison table."""
    lines = [
        f"# Benchmark Results — {result.goal_name}",
        "",
        "| Model | Success Rate | Avg Iterations | Avg Tokens | Total Cost | Avg Time |",
        "|-------|-------------|----------------|------------|------------|----------|",
    ]

    for m in sorted(result.models, key=lambda x: x.success_rate, reverse=True):
        winner_badge = " 🏆" if m.model_name == result.winner else ""
        lines.append(
            f"| {m.model_name}{winner_badge} "
            f"| {m.success_rate:.0%} "
            f"| {m.avg_iterations:.1f} "
            f"| {m.avg_tokens:,.0f} "
            f"| ${m.total_cost:.4f} "
            f"| {m.avg_duration:.1f}s |"
        )

    return "\n".join(lines)
