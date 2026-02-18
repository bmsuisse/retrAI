"""Shared types for the swarm module."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubTask:
    """A single sub-task produced by the decomposer."""

    id: str
    description: str
    focus_files: list[str] = field(default_factory=list)
    strategy_hint: str = ""
    role: str = ""  # Optional research role: researcher, analyst, reviewer, synthesizer


@dataclass
class WorkerResult:
    """Result from a single worker agent run."""

    task_id: str
    description: str
    status: str  # achieved | failed
    findings: str
    iterations_used: int
    tokens_used: int
    cost_usd: float = 0.0
    error: str | None = None


@dataclass
class SwarmResult:
    """Aggregated result from a swarm run."""

    status: str  # achieved | partial | failed
    worker_results: list[WorkerResult]
    synthesis: str  # LLM-generated synthesis of all findings
    total_tokens: int
    total_cost: float
    total_iterations: int
