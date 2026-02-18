"""Reflect node: detects stuck patterns and forces strategy shifts."""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState
from retrai.events.types import AgentEvent

logger = logging.getLogger(__name__)


async def reflect_node(state: AgentState, config: RunnableConfig) -> dict:
    """Detect stuck patterns and inject strategy shift instructions.

    This node runs between failed evaluate → plan transitions (after
    iteration 3+). It checks if the agent is repeating the same failed
    approach and, if so, forces a different strategy.
    """
    cfg = config.get("configurable", {})
    event_bus = cfg.get("event_bus")
    run_id = state["run_id"]
    iteration = state["iteration"]
    consecutive_failures = state.get("consecutive_failures", 0)
    failed_strategies = list(state.get("failed_strategies", []))

    # Only reflect after 2+ consecutive failures
    if consecutive_failures < 2:
        return {
            "failed_strategies": failed_strategies,
            "consecutive_failures": consecutive_failures,
        }

    # Emit reflection event
    if event_bus:
        await event_bus.publish(
            AgentEvent(
                kind="log",
                run_id=run_id,
                iteration=iteration,
                payload={
                    "message": (
                        f"Reflecting on {consecutive_failures} consecutive "
                        f"failures. Analyzing stuck patterns..."
                    ),
                    "level": "warning",
                },
            )
        )

    # Analyze what strategies have been tried by reading recent messages
    recent_failures = _extract_recent_failures(state)
    is_stuck = _detect_stuck_pattern(recent_failures)

    if not is_stuck:
        return {
            "failed_strategies": failed_strategies,
            "consecutive_failures": consecutive_failures,
        }

    # Generate reflection message based on failure patterns
    reflection = _build_reflection_message(
        recent_failures, failed_strategies, consecutive_failures
    )

    # Track this as a failed strategy
    if recent_failures:
        summary = recent_failures[-1][:200]
        if summary not in failed_strategies:
            failed_strategies.append(summary)
        # Keep only last 10
        failed_strategies = failed_strategies[-10:]

    reflection_msg = HumanMessage(content=reflection)

    if event_bus:
        await event_bus.publish(
            AgentEvent(
                kind="log",
                run_id=run_id,
                iteration=iteration,
                payload={
                    "message": "Strategy shift triggered — injecting new approach",
                    "level": "info",
                },
            )
        )

    return {
        "messages": [reflection_msg],
        "failed_strategies": failed_strategies,
        "consecutive_failures": consecutive_failures,
    }


def _extract_recent_failures(state: AgentState) -> list[str]:
    """Extract goal failure reasons from recent messages."""
    failures: list[str] = []
    messages = state.get("messages", [])

    for msg in messages[-20:]:
        content = ""
        if hasattr(msg, "content"):
            content = str(msg.content)
        if "Goal NOT YET achieved" in content or "NOT ACHIEVED" in content.upper():
            failures.append(content)

    return failures


def _detect_stuck_pattern(failures: list[str]) -> bool:
    """Detect if the agent is producing similar failures repeatedly."""
    if len(failures) < 2:
        return False

    # Simple similarity check: if last two failures share many words
    last = set(failures[-1].lower().split())
    prev = set(failures[-2].lower().split())

    if not last or not prev:
        return False

    overlap = len(last & prev) / max(len(last | prev), 1)
    return overlap > 0.6  # 60%+ similarity → stuck


def _build_reflection_message(
    recent_failures: list[str],
    failed_strategies: list[str],
    consecutive_failures: int,
) -> str:
    """Build a reflection message that forces the agent to shift strategy."""
    avoided = ""
    if failed_strategies:
        avoided = (
            "\n\n**Previously failed approaches (DO NOT repeat these):**\n"
            + "\n".join(f"- {s[:150]}" for s in failed_strategies[-5:])
        )

    escalation = ""
    if consecutive_failures >= 5:
        escalation = (
            "\n\n⚠️ **CRITICAL**: You have failed {consecutive_failures} times. "
            "Take a COMPLETELY different approach:\n"
            "- If you were editing code, try rewriting the entire function\n"
            "- If tests are failing, look at the test expectations — maybe "
            "the tests are wrong\n"
            "- Use `web_search` to find alternative solutions\n"
            "- Consider importing a library instead of writing from scratch\n"
            "- Read the whole file or module to understand the full picture"
        )
    elif consecutive_failures >= 3:
        escalation = (
            "\n\n⚡ **Strategy shift required.** Your previous approaches are "
            "not working. Try something fundamentally different:\n"
            "- Search the codebase more broadly with `grep_search`\n"
            "- Read upstream/downstream files for context\n"
            "- Try a simpler, more direct approach\n"
            "- Check if there's a different root cause than what you assumed"
        )

    return (
        f"🔄 **REFLECTION** (after {consecutive_failures} consecutive failures)\n\n"
        f"Your recent attempts have not succeeded. Before trying again, "
        f"STOP and think deeply about:\n"
        f"1. What is the ACTUAL root cause of the failure?\n"
        f"2. Why did your previous approach not work?\n"
        f"3. What DIFFERENT approach could solve this?\n"
        f"{avoided}{escalation}\n\n"
        f"Take a moment to reason step-by-step about a new strategy, "
        f"then execute it."
    )
