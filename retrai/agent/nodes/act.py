"""Act node: dispatches tool calls and collects results (with parallel execution)."""

from __future__ import annotations

import asyncio

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState, ToolCall, ToolResult
from retrai.events.types import AgentEvent
from retrai.safety.guardrails import SafetyGuard, load_safety_config
from retrai.tools.builtins import create_default_registry

# Module-level registry — created once, reused across invocations.
_registry = create_default_registry()
_PARALLEL_SAFE = _registry.parallel_safe_names()


def _partition_tool_calls(
    tool_calls: list[ToolCall],
) -> list[list[ToolCall]]:
    """Partition tool calls into batches for parallel/sequential execution.

    Read-only tools are grouped together for parallel execution.
    Write tools and bash_exec are executed sequentially in order.
    """
    if len(tool_calls) <= 1:
        return [[tc] for tc in tool_calls]

    batches: list[list[ToolCall]] = []
    current_parallel: list[ToolCall] = []

    for tc in tool_calls:
        if tc["name"] in _PARALLEL_SAFE:
            current_parallel.append(tc)
        else:
            # Flush any accumulated parallel batch
            if current_parallel:
                batches.append(current_parallel)
                current_parallel = []
            # Sequential tool gets its own batch
            batches.append([tc])

    # Flush remaining parallel batch
    if current_parallel:
        batches.append(current_parallel)

    return batches


async def act_node(state: AgentState, config: RunnableConfig) -> dict:
    """Execute all pending tool calls and return results.

    Read-only tools are executed in parallel for speed; write tools
    and bash_exec are executed sequentially.
    """
    cfg = config.get("configurable", {})
    event_bus = cfg.get("event_bus")
    run_id = state["run_id"]
    iteration = state["iteration"]
    cwd = state["cwd"]

    # Initialize safety guard
    safety_config = load_safety_config(cwd)
    safety_guard = SafetyGuard(safety_config)

    tool_results: list[ToolResult] = []
    tool_messages: list[ToolMessage] = []

    batches = _partition_tool_calls(state["pending_tool_calls"])

    for batch in batches:
        if len(batch) == 1:
            # Single tool — execute normally
            tc = batch[0]
            await _execute_and_record(
                tc,
                cwd,
                run_id,
                iteration,
                event_bus,
                tool_results,
                tool_messages,
                safety_guard,
            )
        else:
            # Multiple read-only tools — execute in parallel
            if event_bus:
                await event_bus.publish(
                    AgentEvent(
                        kind="log",
                        run_id=run_id,
                        iteration=iteration,
                        payload={
                            "message": f"⚡ Executing {len(batch)} tools in parallel",
                            "level": "info",
                        },
                    )
                )

            # Publish all tool_call events first
            for tc in batch:
                if event_bus:
                    await event_bus.publish(
                        AgentEvent(
                            kind="tool_call",
                            run_id=run_id,
                            iteration=iteration,
                            payload={"tool": tc["name"], "args": tc["args"]},
                        )
                    )

            # Execute all in parallel
            tasks = [_dispatch(tc["name"], tc["args"], cwd) for tc in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for tc, result in zip(batch, results):
                if isinstance(result, Exception):
                    content = f"Tool error: {type(result).__name__}: {result}"
                    error = True
                else:
                    content, error = result

                if event_bus:
                    await event_bus.publish(
                        AgentEvent(
                            kind="tool_result",
                            run_id=run_id,
                            iteration=iteration,
                            payload={
                                "tool": tc["name"],
                                "content": content[:500],
                                "error": error,
                            },
                        )
                    )

                tool_result = ToolResult(
                    tool_call_id=tc["id"],
                    name=tc["name"],
                    content=content,
                    error=error,
                )
                tool_results.append(tool_result)
                tool_messages.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=tc["id"],
                        name=tc["name"],
                    )
                )

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
        "pending_tool_calls": [],
    }


async def _execute_and_record(
    tc: ToolCall,
    cwd: str,
    run_id: str,
    iteration: int,
    event_bus: object | None,
    tool_results: list[ToolResult],
    tool_messages: list[ToolMessage],
    safety_guard: SafetyGuard | None = None,
) -> None:
    """Execute a single tool call and append results."""
    tool_name = tc["name"]
    args = tc["args"]
    tool_call_id = tc["id"]

    # Safety pre-check
    if safety_guard:
        violations = safety_guard.check_tool_call(tool_name, args)
        if safety_guard.should_block(violations):
            content = "⛔ Safety guard BLOCKED this operation:\n" + safety_guard.format_violations(
                violations
            )
            tool_results.append(
                ToolResult(
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    content=content,
                    error=True,
                )
            )
            tool_messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )
            return

    if event_bus:
        await event_bus.publish(  # type: ignore[union-attr]
            AgentEvent(
                kind="tool_call",
                run_id=run_id,
                iteration=iteration,
                payload={"tool": tool_name, "args": args},
            )
        )

    content, error = await _dispatch(tool_name, args, cwd)

    if event_bus:
        await event_bus.publish(  # type: ignore[union-attr]
            AgentEvent(
                kind="tool_result",
                run_id=run_id,
                iteration=iteration,
                payload={
                    "tool": tool_name,
                    "content": content[:500],
                    "error": error,
                },
            )
        )

    result = ToolResult(
        tool_call_id=tool_call_id,
        name=tool_name,
        content=content,
        error=error,
    )
    tool_results.append(result)
    tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name))


async def _dispatch(tool_name: str, args: dict, cwd: str) -> tuple[str, bool]:
    """Dispatch a single tool call via the registry. Returns (content, is_error)."""
    return await _registry.dispatch(tool_name, args, cwd)
