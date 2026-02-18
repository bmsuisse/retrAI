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

logger = logging.getLogger(__name__)

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
    {
        "name": "grep_search",
        "description": (
            "Search for a text pattern across all project files. "
            "Like ripgrep — finds exact or regex matches with file "
            "paths and line numbers. Use this instead of bash grep "
            "for faster, structured results. Skips binary files, "
            ".git, node_modules, __pycache__, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "is_regex": {
                    "type": "boolean",
                    "description": (
                        "Treat pattern as regex (default: literal)"
                    ),
                    "default": False,
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default True)",
                    "default": True,
                },
                "include_glob": {
                    "type": "string",
                    "description": (
                        "Optional glob to filter files (e.g. '*.py')"
                    ),
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "find_files",
        "description": (
            "Find files matching a glob pattern in the project tree. "
            "Returns paths with file sizes. Skips .git, node_modules, "
            "__pycache__, .venv, etc. Use '**/*.py' for recursive "
            "matching or '*.ts' for current-level only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": (
                        "Glob pattern (e.g. '**/*.py', '*.test.ts')"
                    ),
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "git_diff",
        "description": (
            "Show uncommitted changes in the git working tree. "
            "Returns a unified diff of all modified files. "
            "Use staged=true to see staged changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": (
                        "Show staged changes instead (default False)"
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "git_status",
        "description": (
            "Show the current git working tree status (short format). "
            "Shows modified, added, deleted, and untracked files."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "git_log",
        "description": (
            "Show the recent git commit history (oneline format). "
            "Useful for understanding what has changed recently."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": (
                        "Number of commits to show (default 10)"
                    ),
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "python_exec",
        "description": (
            "Execute Python code in an isolated sandbox environment. "
            "The sandbox is a separate venv at .retrai/sandbox/ with "
            "NO access to the host's environment variables (API keys, "
            "tokens, etc. are NOT available). Use this for data "
            "analysis, quick experiments, testing snippets, or running "
            "computations safely. You can install pip packages."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source code to execute",
                },
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional pip packages to install before "
                        "execution (e.g. ['numpy', 'pandas'])"
                    ),
                },
                "timeout": {
                    "type": "number",
                    "description": (
                        "Timeout in seconds (default 30)"
                    ),
                    "default": 30,
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "js_exec",
        "description": (
            "Execute JavaScript or TypeScript code in an isolated "
            "Bun sandbox. The sandbox is at .retrai/js-sandbox/ with "
            "NO access to the host's environment variables. Bun runs "
            "TypeScript natively. Use this for JS/TS experiments, "
            "data processing, or testing snippets. You can install "
            "npm packages."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "JavaScript or TypeScript source code",
                },
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional npm packages to install before "
                        "execution (e.g. ['lodash', 'zod'])"
                    ),
                },
                "timeout": {
                    "type": "number",
                    "description": (
                        "Timeout in seconds (default 30)"
                    ),
                    "default": 30,
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "dataset_fetch",
        "description": (
            "Fetch datasets or search scientific literature from public "
            "APIs. Supports PubMed (biomedical), arXiv (research papers), "
            "HuggingFace (ML datasets), or downloading from a trusted URL. "
            "Returns structured results with titles, abstracts, authors, "
            "and URLs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": (
                        "Data source: 'pubmed', 'arxiv', "
                        "'huggingface', or 'url'"
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Search query (or URL if source='url')"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results (default 10, max 50)",
                    "default": 10,
                },
                "save_path": {
                    "type": "string",
                    "description": (
                        "Optional file path to save downloaded data"
                    ),
                },
            },
            "required": ["source", "query"],
        },
    },
    {
        "name": "data_analysis",
        "description": (
            "Analyze a CSV, JSON, or Excel data file. Runs in a "
            "sandboxed Python environment with pandas. Returns "
            "structured statistical results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Path to data file (relative to project)"
                    ),
                },
                "analysis_type": {
                    "type": "string",
                    "description": (
                        "Type: 'summary' (stats), 'correlations', "
                        "'quality' (data quality report), "
                        "'distribution' (value distributions)"
                    ),
                    "default": "summary",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "experiment_log",
        "description": (
            "Log a scientific experiment with hypothesis, parameters, "
            "metrics, and results. Experiments are stored locally in "
            ".retrai/experiments/ for tracking and comparison."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short experiment name",
                },
                "hypothesis": {
                    "type": "string",
                    "description": "The hypothesis being tested",
                },
                "parameters": {
                    "type": "object",
                    "description": (
                        "Experiment parameters (key-value pairs)"
                    ),
                },
                "metrics": {
                    "type": "object",
                    "description": (
                        "Result metrics (key-value number pairs)"
                    ),
                },
                "result": {
                    "type": "string",
                    "description": (
                        "Outcome: 'confirmed', 'rejected', "
                        "'inconclusive', or 'error'"
                    ),
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "experiment_list",
        "description": (
            "List past experiments or compare specific experiments "
            "by their IDs. Shows metrics, status, and rankings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "Filter by tag",
                },
                "status": {
                    "type": "string",
                    "description": (
                        "Filter by status: 'running', "
                        "'completed', 'failed'"
                    ),
                },
                "compare_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Experiment IDs to compare side-by-side"
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "hypothesis_test",
        "description": (
            "Run a statistical hypothesis test. Supports t-test, "
            "paired t-test, one-sample t-test, chi-squared, "
            "Mann-Whitney U, ANOVA, Shapiro-Wilk normality, and "
            "Pearson correlation. Returns test statistic, p-value, "
            "effect size, and plain-English interpretation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "test_type": {
                    "type": "string",
                    "description": (
                        "Test: 'ttest', 'ttest_paired', "
                        "'ttest_1samp', 'chi2', 'mann_whitney', "
                        "'anova', 'shapiro', 'pearson'"
                    ),
                },
                "data1": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "First data sample",
                },
                "data2": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": (
                        "Second sample (for two-sample tests)"
                    ),
                },
                "data_file": {
                    "type": "string",
                    "description": (
                        "CSV file path (alternative to inline data)"
                    ),
                },
                "column1": {
                    "type": "string",
                    "description": "Column name for first sample",
                },
                "column2": {
                    "type": "string",
                    "description": "Column name for second sample",
                },
                "alpha": {
                    "type": "number",
                    "description": (
                        "Significance level (default 0.05)"
                    ),
                    "default": 0.05,
                },
            },
            "required": ["test_type"],
        },
    },
    {
        "name": "visualize",
        "description": (
            "Generate a chart from a data file (CSV/JSON/Excel) and "
            "save as PNG. Supports scatter, bar, histogram, heatmap, "
            "boxplot, line, and correlation_matrix charts. Uses "
            "matplotlib and seaborn for publication-ready output."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the data file",
                },
                "chart_type": {
                    "type": "string",
                    "description": (
                        "Chart type: 'scatter', 'bar', "
                        "'histogram', 'heatmap', 'boxplot', "
                        "'line', 'correlation_matrix'"
                    ),
                },
                "x_column": {
                    "type": "string",
                    "description": "Column for x-axis",
                },
                "y_column": {
                    "type": "string",
                    "description": "Column for y-axis",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title",
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Output PNG path (auto-generated if omitted)"
                    ),
                },
            },
            "required": ["file_path", "chart_type"],
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
        "heatmap, boxplot, line, correlation_matrix) from data files\n\n"
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

