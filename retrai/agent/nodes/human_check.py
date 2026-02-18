"""Human-in-the-loop check node."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from retrai.agent.state import AgentState
from retrai.events.types import AgentEvent


async def human_check_node(state: AgentState, config: RunnableConfig) -> dict:
    """Interrupt execution to wait for human approval."""
    cfg = config.get("configurable", {})
    event_bus = cfg.get("event_bus")
    run_id = state["run_id"]
    iteration = state["iteration"]

    if event_bus:
        await event_bus.publish(
            AgentEvent(
                kind="human_check_required",
                run_id=run_id,
                iteration=iteration,
                payload={
                    "iteration": iteration,
                    "goal_reason": state.get("goal_reason", ""),
                    "message": "Human approval required to continue",
                },
            )
        )

    # LangGraph interrupt — suspends graph execution until resumed
    decision = interrupt(
        {
            "run_id": run_id,
            "iteration": iteration,
            "message": "Approve to continue, abort to stop",
        }
    )

    if event_bus:
        await event_bus.publish(
            AgentEvent(
                kind="human_check_response",
                run_id=run_id,
                iteration=iteration,
                payload={"decision": decision},
            )
        )

    # decision is whatever the human passed in resume()
    approved = decision in (True, "approve", "yes", "continue")
    if not approved:
        return {"goal_achieved": False, "goal_reason": "Aborted by user."}
    return {}
