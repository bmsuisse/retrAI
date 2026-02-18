"""Swarm orchestrator — decomposes goals and runs parallel worker agents."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage

from retrai.llm.factory import get_llm
from retrai.swarm.decomposer import decompose_goal
from retrai.swarm.types import SubTask, SwarmResult, WorkerResult
from retrai.swarm.worker import run_worker

logger = logging.getLogger(__name__)


class SwarmOrchestrator:
    """Master orchestrator that decomposes a goal and runs parallel workers.

    Usage:
        orchestrator = SwarmOrchestrator(
            description="Fix all type errors and add missing tests",
            cwd="/path/to/project",
            model_name="claude-sonnet-4-6",
            max_workers=3,
            max_iterations_per_worker=10,
        )
        result = await orchestrator.run()
    """

    def __init__(
        self,
        description: str,
        cwd: str,
        model_name: str = "claude-sonnet-4-6",
        max_workers: int = 3,
        max_iterations_per_worker: int = 10,
        on_event: Callable[..., Any] | None = None,
    ) -> None:
        self.description = description
        self.cwd = cwd
        self.model_name = model_name
        self.max_workers = max_workers
        self.max_iterations_per_worker = max_iterations_per_worker
        self._on_event = on_event

    async def run(self) -> SwarmResult:
        """Execute the full swarm pipeline: decompose → dispatch → synthesize."""
        # Phase 1: Decompose the goal into sub-tasks
        logger.info("Decomposing goal: %s", self.description[:80])
        subtasks = await decompose_goal(
            description=self.description,
            cwd=self.cwd,
            model_name=self.model_name,
            max_subtasks=self.max_workers,
        )
        logger.info("Decomposed into %d sub-tasks", len(subtasks))
        for st in subtasks:
            if st.role:
                logger.info("  %s → role: %s", st.id, st.role)

        # Phase 2: Run workers in parallel
        worker_results = await self._dispatch_workers(subtasks)

        # Phase 3: Synthesize findings
        synthesis = await self._synthesize(worker_results)

        # Compute aggregates
        total_tokens = sum(r.tokens_used for r in worker_results)
        total_cost = sum(r.cost_usd for r in worker_results)
        total_iterations = sum(r.iterations_used for r in worker_results)

        achieved_count = sum(1 for r in worker_results if r.status == "achieved")
        if achieved_count == len(worker_results):
            status = "achieved"
        elif achieved_count > 0:
            status = "partial"
        else:
            status = "failed"

        return SwarmResult(
            status=status,
            worker_results=worker_results,
            synthesis=synthesis,
            total_tokens=total_tokens,
            total_cost=total_cost,
            total_iterations=total_iterations,
        )

    async def _dispatch_workers(
        self, subtasks: list[SubTask]
    ) -> list[WorkerResult]:
        """Run all workers concurrently."""
        tasks = [
            run_worker(
                subtask=st,
                cwd=self.cwd,
                model_name=self.model_name,
                max_iterations=self.max_iterations_per_worker,
            )
            for st in subtasks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        worker_results: list[WorkerResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Worker %s raised exception: %s",
                    subtasks[i].id,
                    result,
                )
                worker_results.append(
                    WorkerResult(
                        task_id=subtasks[i].id,
                        description=subtasks[i].description,
                        status="failed",
                        findings="",
                        iterations_used=0,
                        tokens_used=0,
                        cost_usd=0.0,
                        error=str(result),
                    )
                )
            else:
                worker_results.append(result)  # type: ignore[arg-type]

        return worker_results

    async def _synthesize(self, results: list[WorkerResult]) -> str:
        """Use the LLM to synthesize all worker findings into a summary."""
        findings_text = "\n\n".join(
            f"### Worker: {r.task_id}\n"
            f"**Task**: {r.description}\n"
            f"**Status**: {r.status}\n"
            f"**Findings**: {r.findings or 'No findings reported'}\n"
            f"**Iterations**: {r.iterations_used} | "
            f"**Tokens**: {r.tokens_used:,}"
            for r in results
        )

        prompt = f"""You are a technical project manager. Multiple AI worker agents have been
working on sub-tasks of the following goal:

**GOAL**: {self.description}

Here are the results from each worker:

{findings_text}

Synthesize these results into a concise summary that:
1. States the overall outcome (what was achieved vs. what remains)
2. Highlights key findings or changes made
3. Notes any conflicts between workers (if any)
4. Suggests next steps if the goal is not fully achieved

Be concise (max 300 words)."""

        try:
            llm = get_llm(self.model_name, temperature=0.3)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return str(response.content)
        except Exception as e:
            logger.error("Synthesis failed: %s", e)
            # Fallback: concatenate findings
            achieved = sum(1 for r in results if r.status == "achieved")
            return (
                f"{achieved}/{len(results)} workers completed successfully.\n\n"
                + "\n".join(
                    f"- {r.task_id}: {r.status} — {r.findings[:200]}"
                    for r in results
                )
            )
