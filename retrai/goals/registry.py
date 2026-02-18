"""Goal registry: maps goal name strings to GoalBase instances."""

from __future__ import annotations

from retrai.goals.ai_eval import AiEvalGoal
from retrai.goals.base import GoalBase
from retrai.goals.bun_goal import BunTestGoal
from retrai.goals.cargo_goal import CargoTestGoal
from retrai.goals.go_goal import GoTestGoal
from retrai.goals.make_goal import MakeTestGoal
from retrai.goals.ml_goal import MlOptimizeGoal
from retrai.goals.npm_goal import NpmTestGoal
from retrai.goals.perf_goal import PerfCheckGoal
from retrai.goals.pyright_goal import PyrightGoal
from retrai.goals.pytest_goal import PytestGoal
from retrai.goals.research_goal import ResearchGoal
from retrai.goals.shell_goal import ShellGoal
from retrai.goals.sql_goal import SqlBenchmarkGoal

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

