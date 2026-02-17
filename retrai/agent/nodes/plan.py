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
            "Use for running tests, installing packages, running scripts "
            "(Python, Node.js, etc.), inspecting files with grep/find, "
            "and any other terminal operation. "
            "The command runs in a shell with full access to the system."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default 120)",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "file_read",
        "description": (
            "Read the contents of a file (path relative to project root)"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_list",
        "description": (
            "List files and directories at a path relative to "
            "project root"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory path relative to project root "
                        "(default '.')"
                    ),
                    "default": ".",
                }
            },
            "required": [],
        },
    },
    {
        "name": "file_write",
        "description": (
            "Write content to a file (path relative to project root). "
            "Creates parent dirs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_pytest",
        "description": (
            "Run the pytest test suite and return structured results "
            "with failures"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "file_patch",
        "description": (
            "Surgically replace an exact text match in a file with new "
            "text. More efficient than rewriting the whole file — provide "
            "only the exact old text and the replacement. "
            "The old text must appear exactly once."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root",
                },
                "old": {
                    "type": "string",
                    "description": (
                        "Exact text to find (must be unique in file)"
                    ),
                },
                "new": {
                    "type": "string",
                    "description": "Replacement text",
                },
            },
            "required": ["path", "old", "new"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for information. Use when you need to "
            "look up documentation, find solutions to errors, research "
            "APIs, or find code examples. Returns titles, URLs, and "
            "snippets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": (
                        "Maximum results to return (default 5)"
                    ),
                    "default": 5,
                },
            },
            "required": ["query"],
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
    llm_with_tools = llm.bind_tools(
        TOOL_DEFINITIONS,
    )  # type: ignore[attr-defined]

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
        new_total += (
            usage_meta.get("input_tokens", 0)
            + usage_meta.get("output_tokens", 0)
        )

    return {
        "messages": [response],
        "pending_tool_calls": pending,
        "tool_results": [],
        "total_tokens": new_total,
    }


def _trim_messages(messages: list, max_keep: int = 60) -> list:
    """Keep the first (system) message and the most recent messages."""
    if len(messages) <= max_keep:
        return messages
    # Always keep the first system message
    first = messages[0:1]
    tail = messages[-(max_keep - 1) :]
    return first + tail


def _build_system_prompt(goal: Any, state: AgentState) -> str:
    """Build the system prompt that drives the agent's behavior."""
    if goal is None:
        goal_prompt = "Complete the task."
    else:
        sig = inspect.signature(goal.system_prompt)
        if len(sig.parameters) > 0:
            goal_prompt = goal.system_prompt(state.get("cwd", "."))
        else:
            goal_prompt = goal.system_prompt()

    return (
        "You are retrAI, an autonomous software engineering agent. "
        "You are an expert programmer who solves problems methodically "
        "and NEVER gives up.\n\n"
        f"**Project directory**: `{state['cwd']}`\n"
        f"**Max iterations**: {state['max_iterations']}\n\n"
        "## Your Goal\n"
        f"{goal_prompt}\n\n"
        "## Available Tools\n"
        "- `bash_exec`: Run ANY shell command — tests, scripts, "
        "grep, find, curl, python, node, etc.\n"
        "- `file_read`: Read file contents\n"
        "- `file_list`: List directory contents\n"
        "- `file_write`: Write/create files\n"
        "- `file_patch`: Surgically replace exact text in a file "
        "(preferred for targeted edits)\n"
        "- `run_pytest`: Run the test suite with structured output\n"
        "- `web_search`: Search the web for documentation, error "
        "solutions, or code examples\n\n"
        "## Strategy\n"
        "1. **Understand first**: Read relevant files and run "
        "diagnostics before making changes.\n"
        "2. **Execute scripts**: You can run `python`, `node`, "
        "`bun`, `cargo`, or any CLI tool via `bash_exec` to test "
        "ideas, validate hypotheses, or generate data.\n"
        "3. **Iterate**: After each change, run tests/checks to "
        "verify. If tests fail, read the error output carefully, "
        "diagnose the root cause, and fix it.\n"
        "4. **Search when stuck**: If you encounter an unfamiliar "
        "error or API, use `web_search` to find solutions.\n"
        "5. **Try alternatives**: If your first approach doesn't "
        "work, step back and try a completely different strategy. "
        "Consider alternative libraries, different algorithms, or "
        "restructuring the code.\n\n"
        "## Critical Rules\n"
        "- **NEVER give up** while you have iterations remaining. "
        "If something isn't working, try a different approach.\n"
        "- **NEVER say 'I cannot'** — you have full shell access "
        "and can install packages, run scripts, and search the web.\n"
        "- Prefer `file_patch` over `file_write` for targeted edits.\n"
        "- Always verify your changes by running the relevant tests "
        "or checks.\n"
        "- Be precise with file paths (relative to project root).\n"
        "- If you need a package, install it with the appropriate "
        "package manager (pip/uv, npm/bun, cargo, etc.).\n"
        "- Think step-by-step. Show your reasoning before acting."
    )
