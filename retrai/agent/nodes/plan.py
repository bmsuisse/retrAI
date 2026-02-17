"""Plan node: calls the LLM and extracts pending tool calls."""

from __future__ import annotations

import inspect
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState, ToolCall
from retrai.events.types import AgentEvent
from retrai.llm.factory import get_llm

# Tools available to the agent
TOOL_DEFINITIONS = [
    {
        "name": "bash_exec",
        "description": (
            "Execute a shell command in the project directory. "
            "Use for running tests, installing packages, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run"},
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default 60)",
                    "default": 60,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "file_read",
        "description": "Read the contents of a file (path relative to project root)",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_list",
        "description": "List files and directories at a path relative to project root",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to project root (default '.')",
                    "default": ".",
                }
            },
            "required": [],
        },
    },
    {
        "name": "file_write",
        "description": "Write content to a file (path relative to project root). Creates parent dirs.",  # noqa: E501
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
                "content": {"type": "string", "description": "Full file content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_pytest",
        "description": "Run the pytest test suite and return structured results with failures",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "file_patch",
        "description": (
            "Surgically replace an exact text match in a file with new text. "
            "More efficient than rewriting the whole file — provide only the exact "
            "old text and the replacement. The old text must appear exactly once."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
                "old": {"type": "string", "description": "Exact text to find (must be unique)"},
                "new": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old", "new"],
        },
    },
]


async def plan_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call the LLM to decide next actions."""
    cfg = config.get("configurable", {})
    event_bus = cfg.get("event_bus")
    goal = cfg.get("goal")
    run_id = state["run_id"]
    iteration = state["iteration"]

    if event_bus:
        await event_bus.publish(
            AgentEvent(
                kind="step_start",
                run_id=run_id,
                iteration=iteration,
                payload={"node": "plan", "iteration": iteration},
            )
        )

    llm = get_llm(state["model_name"])

    # Build messages — start with system prompt on first iteration
    messages = list(state["messages"])
    if not messages:
        system_content = _build_system_prompt(goal, state)
        messages = [SystemMessage(content=system_content)]

    # Trim to avoid unbounded context growth
    messages = _trim_messages(messages)

    # Bind tools to the model
    llm_with_tools = llm.bind_tools(TOOL_DEFINITIONS)  # type: ignore[attr-defined]

    response: AIMessage = await llm_with_tools.ainvoke(messages)

    # Extract token usage metadata (always, for tracking)
    usage_meta = getattr(response, "usage_metadata", None) or {}

    # Emit token usage event
    if event_bus and usage_meta:
        prompt_tokens = usage_meta.get("input_tokens", 0)
        completion_tokens = usage_meta.get("output_tokens", 0)
        await event_bus.publish(
            AgentEvent(
                kind="llm_usage",
                run_id=run_id,
                iteration=iteration,
                payload={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "model": state["model_name"],
                },
            )
        )

    # Extract tool calls from the response
    pending: list[ToolCall] = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            pending.append(
                ToolCall(
                    id=str(tc.get("id") or ""),
                    name=tc.get("name", ""),
                    args=tc.get("args", {}),
                )
            )

    new_total = state.get("total_tokens", 0)
    if usage_meta:
        new_total += usage_meta.get("input_tokens", 0) + usage_meta.get("output_tokens", 0)

    return {
        "messages": [response],
        "pending_tool_calls": pending,
        "tool_results": [],
        "total_tokens": new_total,
    }


def _trim_messages(messages: list, max_keep: int = 40) -> list:
    """Keep the first (system) message and the most recent messages."""
    if len(messages) <= max_keep:
        return messages
    # Always keep the first system message
    first = messages[0:1]
    tail = messages[-(max_keep - 1) :]
    return first + tail


def _build_system_prompt(goal: Any, state: AgentState) -> str:
    if goal is None:
        goal_prompt = "Complete the task."
    else:
        sig = inspect.signature(goal.system_prompt)
        if len(sig.parameters) > 0:
            goal_prompt = goal.system_prompt(state.get("cwd", "."))
        else:
            goal_prompt = goal.system_prompt()
    return (
        f"You are retrAI, an autonomous software agent.\n\n"
        f"Project directory: {state['cwd']}\n"
        f"Max iterations: {state['max_iterations']}\n\n"
        f"## Goal\n{goal_prompt}\n\n"
        "## Available Tools\n"
        "- `bash_exec`: run shell commands\n"
        "- `file_read`: read a file\n"
        "- `file_list`: list directory contents\n"
        "- `file_write`: write/overwrite a file\n"
        "- `file_patch`: surgically replace exact text in a file (preferred for edits)\n"
        "- `run_pytest`: run the test suite\n\n"
        "Prefer `file_patch` over `file_write` when making targeted edits.\n"
        "Always think step-by-step. Be methodical and precise."
    )
