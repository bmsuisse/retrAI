"""Act node: dispatches tool calls and collects results."""

from __future__ import annotations

import json

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState, ToolResult
from retrai.events.types import AgentEvent
from retrai.tools.bash_exec import bash_exec
from retrai.tools.file_patch import file_patch
from retrai.tools.file_read import file_list, file_read
from retrai.tools.file_write import file_write
from retrai.tools.pytest_runner import run_pytest


async def act_node(state: AgentState, config: RunnableConfig) -> dict:
    """Execute all pending tool calls and return results."""
    cfg = config.get("configurable", {})
    event_bus = cfg.get("event_bus")
    run_id = state["run_id"]
    iteration = state["iteration"]
    cwd = state["cwd"]

    tool_results: list[ToolResult] = []
    tool_messages: list[ToolMessage] = []

    for tc in state["pending_tool_calls"]:
        tool_name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]

        if event_bus:
            await event_bus.publish(
                AgentEvent(
                    kind="tool_call",
                    run_id=run_id,
                    iteration=iteration,
                    payload={"tool": tool_name, "args": args},
                )
            )

        content, error = await _dispatch(tool_name, args, cwd)

        if event_bus:
            await event_bus.publish(
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
        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
        )

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
        "pending_tool_calls": [],
    }


async def _dispatch(tool_name: str, args: dict, cwd: str) -> tuple[str, bool]:
    """Dispatch a single tool call. Returns (content, is_error)."""
    try:
        if tool_name == "bash_exec":
            result = await bash_exec(
                command=args["command"],
                cwd=cwd,
                timeout=float(args.get("timeout", 60)),
            )
            if result.timed_out:
                return "Command timed out", True
            output = (
                f"EXIT CODE: {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )
            return output[:8000], False

        elif tool_name == "file_read":
            content = await file_read(args["path"], cwd)
            return content, False

        elif tool_name == "file_list":
            path = args.get("path", ".")
            entries = await file_list(path, cwd)
            return "\n".join(entries), False

        elif tool_name == "file_write":
            written = await file_write(args["path"], args["content"], cwd)
            return f"Written: {written}", False

        elif tool_name == "run_pytest":
            import asyncio

            result = await asyncio.get_event_loop().run_in_executor(None, run_pytest, cwd)
            summary = {
                "exit_code": result.exit_code,
                "passed": result.passed,
                "failed": result.failed,
                "error": result.error,
                "total": result.total,
            }
            output = json.dumps(
                {
                    "summary": summary,
                    "failures": result.failures[:10],
                    "stdout": result.stdout[:3000],
                },
                indent=2,
            )
            return output, False

        elif tool_name == "file_patch":
            result_msg = await file_patch(args["path"], args["old"], args["new"], cwd)
            return result_msg, False

        else:
            return f"Unknown tool: {tool_name}", True

    except Exception as e:
        return f"Tool error: {type(e).__name__}: {e}", True
