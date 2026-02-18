"""Evaluate node: checks goal completion and emits events."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState
from retrai.events.types import AgentEvent


async def evaluate_node(state: AgentState, config: RunnableConfig) -> dict:
    """Check the goal and update goal_achieved/goal_reason."""
    cfg = config.get("configurable", {})
    event_bus = cfg.get("event_bus")
    goal = cfg.get("goal")
    run_id = state["run_id"]
    iteration = state["iteration"]
    cwd = state["cwd"]

    new_iteration = iteration + 1

    if goal:
        result = await goal.check(state, cwd)
        achieved = result.achieved
        reason = result.reason
        details = result.details
    else:
        achieved = False
        reason = "No goal defined"
        details = {}

    if event_bus:
        await event_bus.publish(
            AgentEvent(
                kind="goal_check",
                run_id=run_id,
                iteration=new_iteration,
                payload={
                    "achieved": achieved,
                    "reason": reason,
                    "details": _truncate_details(details),
                },
            )
        )
        await event_bus.publish(
            AgentEvent(
                kind="iteration_complete",
                run_id=run_id,
                iteration=new_iteration,
                payload={"iteration": new_iteration, "goal_achieved": achieved},
            )
        )

    # If max iterations hit, force end
    if new_iteration >= state["max_iterations"] and not achieved:
        achieved_final = False
        reason_final = f"Max iterations ({state['max_iterations']}) reached. {reason}"
    else:
        achieved_final = achieved
        reason_final = reason

    # Inject goal status into conversation so the LLM knows where it stands
    remaining = state["max_iterations"] - new_iteration
    cost_usd = state.get("estimated_cost_usd", 0.0)
    cost_str = f" | Cost: ${cost_usd:.4f}" if cost_usd > 0 else ""
    tokens = state.get("total_tokens", 0)
    token_str = f" | Tokens: {tokens:,}" if tokens > 0 else ""

    if achieved:
        status_msg = HumanMessage(
            content=(
                f"[Iteration {new_iteration}/{state['max_iterations']}"
                f"{token_str}{cost_str}] "
                f"✅ Goal ACHIEVED! {reason}"
            )
        )
    elif new_iteration >= state["max_iterations"]:
        status_msg = HumanMessage(
            content=(
                f"[Iteration {new_iteration}/{state['max_iterations']}"
                f"{token_str}{cost_str}] "
                f"⛔ Max iterations reached. Final status: {reason}"
            )
        )
    else:
        status_msg = HumanMessage(
            content=(
                f"[Iteration {new_iteration}/{state['max_iterations']}"
                f"{token_str}{cost_str}] "
                f"Goal NOT YET achieved. {reason}\n\n"
                f"You have {remaining} iterations remaining. "
                "DO NOT give up. Analyze what went wrong and try a "
                "different approach. If your current strategy isn't "
                "working, consider:\n"
                "- Reading the error messages more carefully\n"
                "- Using `grep_search` to find related code\n"
                "- Trying an alternative solution\n"
                "- Searching the web for similar issues\n"
                "- Running diagnostic commands to gather more info\n"
                "- Simplifying your approach\n"
                "Keep going until the goal is achieved."
            )
        )

    # Track consecutive failures for the reflect node
    if achieved:
        consecutive = 0
    else:
        consecutive = state.get("consecutive_failures", 0) + 1

    return {
        "messages": [status_msg],
        "goal_achieved": achieved_final,
        "goal_reason": reason_final,
        "iteration": new_iteration,
        "consecutive_failures": consecutive,
    }


def _truncate_details(details: dict, max_len: int = 2000) -> dict:
    """Truncate long string values in details dict for event payload."""
    truncated = {}
    for k, v in details.items():
        if isinstance(v, str) and len(v) > max_len:
            truncated[k] = v[:max_len] + "..."
        elif isinstance(v, dict):
            truncated[k] = _truncate_details(v, max_len)
        else:
            truncated[k] = v
    return truncated
