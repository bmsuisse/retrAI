"""Event types for the retrAI agent."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

EventKind = Literal[
    "step_start",
    "tool_call",
    "tool_result",
    "goal_check",
    "human_check_required",
    "human_check_response",
    "iteration_complete",
    "run_end",
    "error",
    "log",
    "llm_usage",
    "reasoning",
    "step_progress",
]


@dataclass
class AgentEvent:
    """A structured event emitted by the agent during a run."""

    kind: EventKind
    run_id: str
    iteration: int
    payload: dict
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "run_id": self.run_id,
            "iteration": self.iteration,
            "payload": self.payload,
            "ts": self.ts,
        }
