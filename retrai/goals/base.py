"""Base class for agent goals."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GoalResult:
    achieved: bool
    reason: str
    details: dict


class GoalBase(ABC):
    """Abstract base for goals. A goal checks the current state and returns a result."""

    name: str = "base"

    @abstractmethod
    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Check whether the goal has been achieved given the current agent state."""
        ...

    @abstractmethod
    def system_prompt(self) -> str:
        """Return a system prompt fragment describing this goal to the LLM."""
        ...
