"""Assemble and compile the LangGraph StateGraph."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from retrai.agent.nodes.act import act_node
from retrai.agent.nodes.evaluate import evaluate_node
from retrai.agent.nodes.human_check import human_check_node
from retrai.agent.nodes.plan import plan_node
from retrai.agent.nodes.reflect import reflect_node
from retrai.agent.routers import route_after_evaluate, route_after_human_check, should_call_tools
from retrai.agent.state import AgentState


def build_graph(hitl_enabled: bool = False):
    """Build and compile the agent StateGraph.

    Graph topology:
        START → plan → (has tool calls?) → act → evaluate → (achieved?) → END
                     ↘ no tool calls ↗           ↓ continue
                                           reflect → plan
                                           (hitl?) → human_check → plan
    """
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("plan", plan_node)
    builder.add_node("act", act_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("reflect", reflect_node)
    if hitl_enabled:
        builder.add_node("human_check", human_check_node)

    # Edges
    builder.add_edge(START, "plan")
    builder.add_conditional_edges(
        "plan",
        should_call_tools,
        {"act": "act", "evaluate": "evaluate"},
    )
    builder.add_edge("act", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "end": END,
            "reflect": "reflect",
            "human_check": "human_check" if hitl_enabled else "reflect",
        },
    )

    # Reflect always leads back to plan
    builder.add_edge("reflect", "plan")

    if hitl_enabled:
        builder.add_conditional_edges(
            "human_check",
            route_after_human_check,
            {"end": END, "plan": "plan"},
        )

    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_check"] if hitl_enabled else [],
    )
