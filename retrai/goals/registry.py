"""Goal registry: maps goal name strings to GoalBase instances."""

from __future__ import annotations

from retrai.goals.ai_eval import AiEvalGoal
from retrai.goals.api_test_goal import ApiTestGoal
from retrai.goals.base import GoalBase
from retrai.goals.bun_goal import BunTestGoal
from retrai.goals.cancer_research_goal import CancerResearchGoal
from retrai.goals.cargo_goal import CargoTestGoal
from retrai.goals.creative_goal import CreativeGoal
from retrai.goals.docker_goal import DockerGoal
from retrai.goals.go_goal import GoTestGoal
from retrai.goals.lint_goal import LintGoal
from retrai.goals.make_goal import MakeTestGoal
from retrai.goals.migration_goal import MigrationGoal
from retrai.goals.ml_goal import MlOptimizeGoal
from retrai.goals.npm_goal import NpmTestGoal
from retrai.goals.perf_goal import PerfCheckGoal
from retrai.goals.pyright_goal import PyrightGoal
from retrai.goals.pytest_goal import PytestGoal
from retrai.goals.research_goal import ResearchGoal
from retrai.goals.rust_optimize_goal import RustOptimizeGoal
from retrai.goals.score_goal import ScoreGoal
from retrai.goals.shell_goal import ShellGoal
from retrai.goals.sql_goal import SqlBenchmarkGoal
from retrai.goals.text_improve_goal import TextImproveGoal

_REGISTRY: dict[str, GoalBase] = {
    "pytest": PytestGoal(),
    "pyright": PyrightGoal(),
    "bun-test": BunTestGoal(),
    "npm-test": NpmTestGoal(),
    "cargo-test": CargoTestGoal(),
    "go-test": GoTestGoal(),
    "make-test": MakeTestGoal(),
    "shell-goal": ShellGoal(),
    "perf-check": PerfCheckGoal(),
    "sql-benchmark": SqlBenchmarkGoal(),
    "ai-eval": AiEvalGoal(),
    "ml-optimize": MlOptimizeGoal(),
    "research": ResearchGoal(),
    # Biomedical / scientific research
    "cancer-research": CancerResearchGoal(),
    # Systems / low-level performance
    "rust-optimize": RustOptimizeGoal(),
    # Non-coding / LLM-scored goals
    "text-improve": TextImproveGoal(),
    "creative": CreativeGoal(),
    "score": ScoreGoal(),
    # Infrastructure / tooling
    "docker-build": DockerGoal(),
    "lint": LintGoal(),
    "db-migrate": MigrationGoal(),
    # HTTP integration testing
    "api-test": ApiTestGoal(),
}


def get_goal(name: str) -> GoalBase:
    """Return a goal by name, raising KeyError if not found."""
    if name not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys())
        raise KeyError(f"Unknown goal: '{name}'. Available: {available}")
    return _REGISTRY[name]


def get_solver_goal(description: str) -> GoalBase:
    """Create a SolverGoal for natural language problem solving."""
    from retrai.goals.solver import SolverGoal

    return SolverGoal(description=description)


def list_goals() -> list[str]:
    return list(_REGISTRY.keys())


def get_research_goal(topic: str) -> ResearchGoal:
    """Create a ResearchGoal for a specific topic."""
    return ResearchGoal(topic=topic)
