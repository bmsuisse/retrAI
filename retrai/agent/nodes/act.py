"""Act node: dispatches tool calls and collects results (with parallel execution)."""

from __future__ import annotations

import asyncio
import json

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState, ToolCall, ToolResult
from retrai.events.types import AgentEvent
from retrai.experiment.tracker import experiment_list, experiment_log
from retrai.safety.guardrails import SafetyGuard, load_safety_config
from retrai.tools.bash_exec import bash_exec
from retrai.tools.data_analysis import data_analysis
from retrai.tools.dataset_fetch import dataset_fetch
from retrai.tools.file_patch import file_patch
from retrai.tools.file_read import file_list, file_read
from retrai.tools.file_write import file_write
from retrai.tools.find_files import find_files
from retrai.tools.git_diff import git_diff, git_log, git_status
from retrai.tools.grep_search import grep_search
from retrai.tools.hypothesis_test import hypothesis_test
from retrai.tools.js_exec import js_exec
from retrai.tools.pytest_runner import run_pytest
from retrai.tools.python_exec import python_exec
from retrai.tools.visualize import visualize
from retrai.tools.web_search import web_search

# Tools that are safe to run in parallel (read-only, no side effects)
_PARALLEL_SAFE: frozenset[str] = frozenset({
    "file_read",
    "file_list",
    "grep_search",
    "find_files",
    "git_status",
    "git_log",
    "git_diff",
    "web_search",
    "dataset_fetch",
    "data_analysis",
    "experiment_list",
    "visualize",
})


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
                tc, cwd, run_id, iteration, event_bus,
                tool_results, tool_messages, safety_guard,
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
            tasks = [
                _dispatch(tc["name"], tc["args"], cwd) for tc in batch
            ]
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
            content = (
                "⛔ Safety guard BLOCKED this operation:\n"
                + safety_guard.format_violations(violations)
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
    tool_messages.append(
        ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
    )


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
            result_msg = await file_patch(
                args["path"], args["old"], args["new"], cwd
            )
            return result_msg, False

        elif tool_name == "web_search":
            result = await web_search(
                query=args["query"],
                max_results=int(args.get("max_results", 5)),
            )
            return result[:8000], False

        elif tool_name == "grep_search":
            result = await grep_search(
                pattern=args["pattern"],
                cwd=cwd,
                is_regex=bool(args.get("is_regex", False)),
                case_insensitive=bool(args.get("case_insensitive", True)),
                include_glob=args.get("include_glob"),
            )
            return result[:8000], False

        elif tool_name == "find_files":
            result = await find_files(
                pattern=args["pattern"],
                cwd=cwd,
            )
            return result[:8000], False

        elif tool_name == "git_diff":
            result = await git_diff(
                cwd=cwd,
                staged=bool(args.get("staged", False)),
            )
            return result[:8000], False

        elif tool_name == "git_status":
            result = await git_status(cwd=cwd)
            return result[:4000], False

        elif tool_name == "git_log":
            result = await git_log(
                cwd=cwd,
                count=int(args.get("count", 10)),
            )
            return result[:4000], False

        elif tool_name == "python_exec":
            result = await python_exec(
                code=args["code"],
                cwd=cwd,
                packages=args.get("packages"),
                timeout=float(args.get("timeout", 30)),
            )
            if result.timed_out:
                return "Python execution timed out", True
            output = (
                f"EXIT CODE: {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )
            return output[:8000], False

        elif tool_name == "js_exec":
            result = await js_exec(
                code=args["code"],
                cwd=cwd,
                packages=args.get("packages"),
                timeout=float(args.get("timeout", 30)),
            )
            if result.timed_out:
                return "JS execution timed out", True
            output = (
                f"EXIT CODE: {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )
            return output[:8000], False

        elif tool_name == "dataset_fetch":
            result = await dataset_fetch(
                source=args["source"],
                query=args["query"],
                max_results=int(args.get("max_results", 10)),
                save_path=args.get("save_path"),
                cwd=cwd,
            )
            return result[:8000], False

        elif tool_name == "data_analysis":
            result = await data_analysis(
                file_path=args["file_path"],
                cwd=cwd,
                analysis_type=args.get("analysis_type", "summary"),
            )
            return result[:8000], False

        elif tool_name == "experiment_log":
            result = await experiment_log(
                name=args["name"],
                cwd=cwd,
                hypothesis=args.get("hypothesis", ""),
                parameters=args.get("parameters"),
                metrics=args.get("metrics"),
                result=args.get("result", ""),
                notes=args.get("notes", ""),
                tags=args.get("tags"),
            )
            return result[:8000], False

        elif tool_name == "experiment_list":
            result = await experiment_list(
                cwd=cwd,
                tag=args.get("tag"),
                status=args.get("status"),
                compare_ids=args.get("compare_ids"),
            )
            return result[:8000], False

        elif tool_name == "hypothesis_test":
            result = await hypothesis_test(
                test_type=args["test_type"],
                cwd=cwd,
                data1=args.get("data1"),
                data2=args.get("data2"),
                data_file=args.get("data_file"),
                column1=args.get("column1"),
                column2=args.get("column2"),
                alpha=float(args.get("alpha", 0.05)),
            )
            return result[:8000], False

        elif tool_name == "visualize":
            result = await visualize(
                file_path=args["file_path"],
                chart_type=args["chart_type"],
                cwd=cwd,
                x_column=args.get("x_column"),
                y_column=args.get("y_column"),
                title=args.get("title"),
                output_path=args.get("output_path"),
            )
            return result[:8000], False

        else:
            return f"Unknown tool: {tool_name}", True

    except Exception as e:
        return f"Tool error: {type(e).__name__}: {e}", True
