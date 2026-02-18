"""LangGraph StateGraph for the experiment setup wizard flow."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class SetupState(TypedDict):
    """State for the experiment setup wizard."""

    # Current wizard step (select_goal | configure_model | set_parameters | review)
    step: str
    # Collected configuration
    goal: str
    model_name: str
    provider: str
    max_iterations: int
    hitl_enabled: bool
    cwd: str
    # Flow control
    completed: bool
    cancelled: bool
    # Auto-detected goal (hint for the user)
    detected_goal: str


# ── Node functions ────────────────────────────────────────────


def select_goal_node(state: SetupState) -> dict[str, object]:
    """Transition to the goal selection step."""
    return {"step": "select_goal"}


def configure_model_node(state: SetupState) -> dict[str, object]:
    """Transition to the model configuration step."""
    return {"step": "configure_model"}


def set_parameters_node(state: SetupState) -> dict[str, object]:
    """Transition to the parameters step."""
    return {"step": "set_parameters"}


def review_node(state: SetupState) -> dict[str, object]:
    """Transition to the review step."""
    return {"step": "review"}


# ── Routers ───────────────────────────────────────────────────


def route_after_review(state: SetupState) -> str:
    """Route after the review step: launch or go back."""
    if state.get("completed"):
        return "end"
    if state.get("cancelled"):
        return "end"
    # Default: go back to select_goal for edits
    return "select_goal"


# ── Graph builder ─────────────────────────────────────────────


SETUP_STEPS: list[str] = [
    "select_goal",
    "configure_model",
    "set_parameters",
    "review",
]

STEP_LABELS: dict[str, str] = {
    "select_goal": "Select Goal",
    "configure_model": "Configure Model",
    "set_parameters": "Set Parameters",
    "review": "Review & Launch",
}


def build_setup_graph() -> CompiledStateGraph:
    """Build and compile the experiment setup wizard graph.

    Graph topology:
        START → select_goal → configure_model → set_parameters → review
                                                                   ↓
                                                          (confirm) → END
                                                          (back)   → select_goal
    """
    builder = StateGraph(SetupState)

    # Add nodes
    builder.add_node("select_goal", select_goal_node)
    builder.add_node("configure_model", configure_model_node)
    builder.add_node("set_parameters", set_parameters_node)
    builder.add_node("review", review_node)

    # Linear flow: START → select_goal → configure_model → set_parameters → review
    builder.add_edge(START, "select_goal")
    builder.add_edge("select_goal", "configure_model")
    builder.add_edge("configure_model", "set_parameters")
    builder.add_edge("set_parameters", "review")

    # After review: either end (launch/cancel) or loop back
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"end": END, "select_goal": "select_goal"},
    )

    return builder.compile()


def make_initial_setup_state(
    *,
    cwd: str = ".",
    detected_goal: str = "",
) -> SetupState:
    """Create the initial state for the setup wizard."""
    return SetupState(
        step="select_goal",
        goal=detected_goal or "",
        model_name="claude-sonnet-4-6",
        provider="Anthropic (Claude)",
        max_iterations=50,
        hitl_enabled=False,
        cwd=cwd,
        completed=False,
        cancelled=False,
        detected_goal=detected_goal,
    )
