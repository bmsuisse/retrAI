"""Plan node: calls the LLM and extracts pending tool calls."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from retrai.agent.state import AgentState, ToolCall
from retrai.events.types import AgentEvent
from retrai.llm.factory import get_llm
from retrai.tools.builtins import create_default_registry

logger = logging.getLogger(__name__)

# Tool definitions are dynamically generated from the ToolRegistry.
# Adding a new tool only requires creating a BaseTool subclass — no changes here.
_tool_registry = create_default_registry()
TOOL_DEFINITIONS = _tool_registry.list_definitions()



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
        # Inject role-specific prompt if running as a swarm worker
        role_prompt = cfg.get("role_prompt", "")
        if role_prompt:
            system_content += role_prompt
        # Auto-inject project context on first iteration
        context = _auto_context(state.get("cwd", "."))
        if context:
            system_content += "\n\n## Project Context (auto-detected)\n" + context
        # Inject past learnings from memory
        memory_section = _load_memories(state.get("cwd", "."))
        if memory_section:
            system_content += "\n\n" + memory_section
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

    # Emit reasoning event with the AI's chain-of-thought text
    reasoning_text = response.content if isinstance(response.content, str) else ""
    if event_bus and reasoning_text.strip():
        await event_bus.publish(
            AgentEvent(
                kind="reasoning",
                run_id=run_id,
                iteration=iteration,
                payload={
                    "text": reasoning_text,
                    "model": state["model_name"],
                    "has_tool_calls": bool(
                        hasattr(response, "tool_calls") and response.tool_calls
                    ),
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

    # Estimate cost
    new_cost = state.get("estimated_cost_usd", 0.0)
    if usage_meta:
        new_cost += _estimate_cost(
            state["model_name"],
            usage_meta.get("input_tokens", 0),
            usage_meta.get("output_tokens", 0),
        )

    return {
        "messages": [response],
        "pending_tool_calls": pending,
        "tool_results": [],
        "total_tokens": new_total,
        "estimated_cost_usd": new_cost,
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
        "- `grep_search`: Search for text/regex patterns across all "
        "project files (like ripgrep). Much faster than bash grep.\n"
        "- `find_files`: Find files by glob pattern in the project "
        "tree (e.g. '**/*.py')\n"
        "- `git_diff`: Show uncommitted changes in the working tree\n"
        "- `git_status`: Show git working tree status\n"
        "- `git_log`: Show recent commit history\n"
        "- `python_exec`: Execute Python code in an isolated sandbox "
        "venv (no host env vars). Great for data analysis, quick "
        "experiments, and safe computations.\n"
        "- `js_exec`: Execute JavaScript/TypeScript in an isolated "
        "Bun sandbox (no host env vars). Runs TS natively.\n"
        "- `web_search`: Search the web for documentation, error "
        "solutions, or code examples\n"
        "- `dataset_fetch`: Search PubMed, arXiv, HuggingFace, or "
        "download from trusted URLs — for scientific literature "
        "and dataset discovery\n"
        "- `data_analysis`: Analyze CSV/JSON/Excel files — summary "
        "stats, correlations, data quality, distributions\n"
        "- `hypothesis_test`: Run statistical tests (t-test, chi2, "
        "Mann-Whitney, ANOVA, Shapiro, Pearson) with effect sizes\n"
        "- `experiment_log`: Log experiments with hypothesis, params, "
        "metrics, and result for reproducibility\n"
        "- `experiment_list`: List/compare past experiments\n"
        "- `visualize`: Generate charts (scatter, bar, histogram, "
        "heatmap, boxplot, line, correlation_matrix) from data files\n"
        "- `ml_train`: Train ML models (sklearn/xgboost/lightgbm) on "
        "data files with auto-preprocessing, metrics, CV, and feature "
        "importance\n\n"
        "## Strategy\n"
        "1. **Understand first**: Use `grep_search` and `find_files` "
        "to quickly locate relevant code. Read key files.\n"
        "2. **Search code, not files**: Prefer `grep_search` over "
        "manually reading files to find definitions and usages.\n"
        "3. **Execute scripts**: You can run `python`, `node`, "
        "`bun`, `cargo`, or any CLI tool via `bash_exec` to test "
        "ideas, validate hypotheses, or generate data.\n"
        "4. **Iterate**: After each change, run tests/checks to "
        "verify. If tests fail, read the error output carefully, "
        "diagnose the root cause, and fix it.\n"
        "5. **Search when stuck**: If you encounter an unfamiliar "
        "error or API, use `web_search` to find solutions.\n"
        "6. **Try alternatives**: If your first approach doesn't "
        "work, step back and try a completely different strategy. "
        "Consider alternative libraries, different algorithms, or "
        "restructuring the code.\n\n"
        "## Critical Rules\n"
        "- **NEVER give up** while you have iterations remaining. "
        "If something isn't working, try a different approach.\n"
        "- **NEVER say 'I cannot'** — you have full shell access "
        "and can install packages, run scripts, and search the web.\n"
        "- Prefer `file_patch` over `file_write` for targeted edits.\n"
        "- Prefer `grep_search` over `bash_exec` with grep — it's "
        "faster and returns structured results.\n"
        "- Always verify your changes by running the relevant tests "
        "or checks.\n"
        "- Be precise with file paths (relative to project root).\n"
        "- If you need a package, install it with the appropriate "
        "package manager (pip/uv, npm/bun, cargo, etc.).\n"
        "- Think step-by-step. Show your reasoning before acting."
    )


def _auto_context(cwd: str) -> str:
    """Build a compact project overview to inject on the first iteration.

    Includes a depth-limited directory tree and the first ~200 lines of
    key config files so the agent doesn't waste iterations exploring.
    """
    from pathlib import Path

    root = Path(cwd).resolve()
    parts: list[str] = []

    # 1. Compact directory tree (depth=2)
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
        "dist", "build", ".eggs", "target", "vendor",
    }
    tree_lines: list[str] = []
    try:
        for entry in sorted(root.iterdir()):
            name = entry.name
            if name.startswith(".") and name not in (".retrai.yml",):
                continue
            if name in skip_dirs:
                continue
            if entry.is_dir():
                tree_lines.append(f"  {name}/")
                try:
                    for sub in sorted(entry.iterdir()):
                        sub_name = sub.name
                        if sub_name.startswith(".") or sub_name in skip_dirs:
                            continue
                        suffix = "/" if sub.is_dir() else ""
                        tree_lines.append(f"    {sub_name}{suffix}")
                except PermissionError:
                    pass
            else:
                tree_lines.append(f"  {name}")
    except PermissionError:
        pass

    if tree_lines:
        parts.append("### Directory Structure\n```\n" + "\n".join(tree_lines) + "\n```")

    # 2. Key config file snippets
    config_files = [
        "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
        ".retrai.yml", "Makefile",
    ]
    for fname in config_files:
        fpath = root / fname
        if fpath.exists() and fpath.is_file():
            try:
                content = fpath.read_text(errors="replace")
                # Truncate to first 150 lines
                lines = content.splitlines()[:150]
                snippet = "\n".join(lines)
                if len(lines) < len(content.splitlines()):
                    snippet += "\n... (truncated)"
                parts.append(f"### {fname}\n```\n{snippet}\n```")
            except OSError:
                pass

    return "\n\n".join(parts)


def _estimate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate dollar cost using LiteLLM's cost table.

    Returns 0.0 if the model isn't found in the cost table.
    """
    try:
        import litellm

        cost = litellm.completion_cost(
            model=model_name,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        )
        return float(cost)
    except Exception:
        # Fallback: rough estimate per 1M tokens
        _FALLBACK_COSTS: dict[str, tuple[float, float]] = {
            "claude-sonnet-4-6": (3.0, 15.0),
            "claude-opus-4-6": (15.0, 75.0),
            "gpt-4o": (2.5, 10.0),
            "gpt-4.1": (2.0, 8.0),
            "o4-mini": (1.1, 4.4),
            "gemini-2.5-pro": (1.25, 10.0),
        }
        for prefix, (inp_cost, out_cost) in _FALLBACK_COSTS.items():
            if prefix in model_name:
                return (input_tokens * inp_cost + output_tokens * out_cost) / 1_000_000
        return 0.0


def _load_memories(cwd: str) -> str:
    """Load past learnings from the project's memory store."""
    try:
        from retrai.memory.store import MemoryStore

        store = MemoryStore(cwd)
        return store.format_for_prompt(limit=10)
    except Exception:
        return ""

