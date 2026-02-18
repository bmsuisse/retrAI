"""Built-in tools wrapped as BaseTool subclasses.

Each class bundles its JSON schema, dispatch logic, and metadata
in one place so the agent can discover and invoke them from the
central :class:`ToolRegistry`.

The original implementation functions (``bash_exec``, ``file_read``, etc.)
are kept untouched — these classes simply delegate to them.
"""

from __future__ import annotations

from typing import Any

from retrai.tools.base import BaseTool, ToolRegistry, ToolSchema

# ──────────────────────────────────────────────────────────────────
# Shell / Execution
# ──────────────────────────────────────────────────────────────────


class BashExecTool(BaseTool):
    """Execute a shell command in the project directory."""

    name = "bash_exec"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Execute a shell command in the project directory. "
                "Use for running tests, installing packages, running scripts"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to execute"},
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds",
                        "default": 60,
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.bash_exec import bash_exec

        result = await bash_exec(
            command=args["command"],
            cwd=cwd,
            timeout=float(args.get("timeout", 60)),
        )
        if result.timed_out:
            return (
                f"Command timed out after {args.get('timeout', 60)}s.\n"
                f"Partial stdout: {result.stdout[-2000:]}"
            ), True
        output = result.stdout + result.stderr
        is_error = result.returncode != 0
        return output[-8000:], is_error


# ──────────────────────────────────────────────────────────────────
# File Operations
# ──────────────────────────────────────────────────────────────────


class FileReadTool(BaseTool):
    """Read file contents relative to the project root."""

    name = "file_read"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description="Read the contents of a file. Path is relative to the project root.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_read import file_read

        content = await file_read(args["path"], cwd)
        return content, False


class FileListTool(BaseTool):
    """List files and directories in a path."""

    name = "file_list"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "List files and directories at the given path, relative to the project root."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to project root",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_read import file_list

        entries = await file_list(args["path"], cwd)
        return "\n".join(entries), False


class FileWriteTool(BaseTool):
    """Write or create a file."""

    name = "file_write"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Write content to a file. Creates parent directories "
                "as needed. Path is relative to the project root."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_write import file_write

        result = await file_write(args["path"], args["content"], cwd)
        return f"Wrote {result}", False


class FilePatchTool(BaseTool):
    """Surgically replace exact text in a file."""

    name = "file_patch"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Surgically replace text in a file. Finds an exact match "
                "of 'old' and replaces it with 'new'. By default the old "
                "text must appear exactly once; use 'occurrence' to target "
                "a specific match or replace all."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root",
                    },
                    "old": {
                        "type": "string",
                        "description": "Exact text to find",
                    },
                    "new": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                    "occurrence": {
                        "type": "integer",
                        "description": (
                            "Which occurrence to replace (1-indexed). "
                            "Default 1 (must be unique). "
                            "Set to 0 to replace ALL occurrences."
                        ),
                        "default": 1,
                    },
                },
                "required": ["path", "old", "new"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_patch import file_patch

        result = await file_patch(
            args["path"],
            args["old"],
            args["new"],
            cwd,
            occurrence=int(args.get("occurrence", 1)),
        )
        return result, False


class FileDeleteTool(BaseTool):
    """Delete a file or empty directory."""

    name = "file_delete"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Delete a file or empty directory. Path is relative to "
                "the project root. Refuses to delete non-empty directories."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory path relative to project root",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_delete import file_delete

        result = await file_delete(args["path"], cwd)
        return result, False


class FileRenameTool(BaseTool):
    """Rename or move a file within the project."""

    name = "file_rename"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Rename or move a file within the project tree. Both source "
                "and destination are relative to the project root. Creates "
                "parent directories for the destination as needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "Current file path (relative to project root)",
                    },
                    "new_path": {
                        "type": "string",
                        "description": "New file path (relative to project root)",
                    },
                },
                "required": ["old_path", "new_path"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_rename import file_rename

        result = await file_rename(args["old_path"], args["new_path"], cwd)
        return result, False


class FileInsertTool(BaseTool):
    """Insert text at a specific line number."""

    name = "file_insert"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Insert text at a specific line number in a file. "
                "Line is 1-indexed. Inserts BEFORE the given line. "
                "Use line=0 to prepend, or a very large number to append."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number to insert before (1-indexed)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text to insert",
                    },
                },
                "required": ["path", "line", "content"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.file_insert import file_insert

        result = await file_insert(
            args["path"],
            int(args["line"]),
            args["content"],
            cwd,
        )
        return result, False


# ──────────────────────────────────────────────────────────────────
# Search / Discovery
# ──────────────────────────────────────────────────────────────────


class GrepSearchTool(BaseTool):
    """Search for text/regex patterns across project files."""

    name = "grep_search"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Search for a text pattern across all project files. "
                "Like ripgrep — finds exact or regex matches with file "
                "paths and line numbers. Skips binary files, .git, "
                "node_modules, __pycache__, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text or regex pattern to search for",
                    },
                    "is_regex": {
                        "type": "boolean",
                        "description": "Treat pattern as regex (default: literal)",
                        "default": False,
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Case-insensitive search (default True)",
                        "default": True,
                    },
                    "include_glob": {
                        "type": "string",
                        "description": "Optional glob to filter files (e.g. '*.py')",
                    },
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.grep_search import grep_search

        result = await grep_search(
            pattern=args["pattern"],
            cwd=cwd,
            is_regex=args.get("is_regex", False),
            case_insensitive=args.get("case_insensitive", True),
            include_glob=args.get("include_glob"),
        )
        return result, False


class FindFilesTool(BaseTool):
    """Find files matching a glob pattern."""

    name = "find_files"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Find files matching a glob pattern in the project tree. "
                "Returns paths with file sizes. Skips .git, node_modules, "
                "__pycache__, .venv, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. '**/*.py', '*.test.ts')",
                    },
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.find_files import find_files

        result = await find_files(pattern=args["pattern"], cwd=cwd)
        return result, False


class WebSearchTool(BaseTool):
    """Search the web via DuckDuckGo."""

    name = "web_search"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Search the web for information. Use when you need to "
                "look up documentation, find solutions to errors, research "
                "APIs, or find code examples."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.web_search import web_search

        result = await web_search(
            query=args["query"],
            max_results=args.get("max_results", 5),
        )
        return result, False


# ──────────────────────────────────────────────────────────────────
# Git
# ──────────────────────────────────────────────────────────────────


class GitDiffTool(BaseTool):
    """Show uncommitted changes in git."""

    name = "git_diff"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Show uncommitted changes in the git working tree. "
                "Use staged=true to see staged changes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes instead (default False)",
                        "default": False,
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.git_diff import git_diff

        result = await git_diff(cwd=cwd, staged=args.get("staged", False))
        return result, False


class GitStatusTool(BaseTool):
    """Show git working tree status."""

    name = "git_status"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Show the current git working tree status (short format). "
                "Shows modified, added, deleted, and untracked files."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.git_diff import git_status

        result = await git_status(cwd=cwd)
        return result, False


class GitLogTool(BaseTool):
    """Show recent git commit history."""

    name = "git_log"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=("Show the recent git commit history (oneline format)."),
            parameters={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of commits to show (default 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.git_diff import git_log

        result = await git_log(cwd=cwd, count=args.get("count", 10))
        return result, False


# ──────────────────────────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────────────────────────


class RunPytestTool(BaseTool):
    """Run pytest with structured results."""

    name = "run_pytest"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description="Run the pytest test suite. Returns structured pass/fail results.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        import asyncio

        from retrai.tools.pytest_runner import run_pytest

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            run_pytest,
            cwd,
        )
        if result.timed_out:
            return "pytest timed out", True

        parts: list[str] = []
        parts.append(
            f"Tests: {result.passed} passed, {result.failed} failed, "
            f"{result.error} error, {result.total} total"
        )
        if result.failures:
            parts.append("\nFailures:")
            for f in result.failures[:5]:
                parts.append(f"  - {f.get('nodeid', '?')}")
                longrepr = f.get("longrepr", "")
                if longrepr:
                    parts.append(f"    {longrepr[:500]}")

        is_error = result.failed > 0 or result.error > 0
        return "\n".join(parts), is_error


# ──────────────────────────────────────────────────────────────────
# Sandboxed Execution
# ──────────────────────────────────────────────────────────────────


class PythonExecTool(BaseTool):
    """Execute Python code in an isolated sandbox venv."""

    name = "python_exec"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Execute Python code in an isolated sandbox environment. "
                "The sandbox is a separate venv at .retrai/sandbox/ with "
                "NO access to the host's environment variables. "
                "Use for data analysis, experiments, or safe computations."
            ),
            parameters={
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
                        "description": "Timeout in seconds (default 30)",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.python_exec import python_exec

        result = await python_exec(
            code=args["code"],
            cwd=cwd,
            packages=args.get("packages"),
            timeout=float(args.get("timeout", 30)),
        )
        if result.timed_out:
            return "Execution timed out", True
        output = result.stdout + result.stderr
        return output[-8000:], result.returncode != 0


class JsExecTool(BaseTool):
    """Execute JavaScript/TypeScript in an isolated Bun sandbox."""

    name = "js_exec"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Execute JavaScript or TypeScript code in an isolated "
                "Bun sandbox. The sandbox is at .retrai/js-sandbox/ with "
                "NO access to the host's environment variables. "
                "Bun runs TypeScript natively."
            ),
            parameters={
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
                        "description": "Timeout in seconds (default 30)",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.js_exec import js_exec

        result = await js_exec(
            code=args["code"],
            cwd=cwd,
            packages=args.get("packages"),
            timeout=float(args.get("timeout", 30)),
        )
        if result.timed_out:
            return "Execution timed out", True
        output = result.stdout + result.stderr
        return output[-8000:], result.returncode != 0


# ──────────────────────────────────────────────────────────────────
# Scientific / Data
# ──────────────────────────────────────────────────────────────────


class DatasetFetchTool(BaseTool):
    """Fetch datasets from PubMed, arXiv, HuggingFace, or URLs."""

    name = "dataset_fetch"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Fetch datasets or search scientific literature from public "
                "APIs. Supports PubMed, arXiv, HuggingFace, or downloading "
                "from a trusted URL."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Data source: 'pubmed', 'arxiv', 'huggingface', or 'url'",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (or URL if source='url')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results (default 10, max 50)",
                        "default": 10,
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Optional file path to save downloaded data",
                    },
                },
                "required": ["source", "query"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.dataset_fetch import dataset_fetch

        result = await dataset_fetch(
            source=args["source"],
            query=args["query"],
            max_results=args.get("max_results", 10),
            save_path=args.get("save_path"),
            cwd=cwd,
        )
        return result, False


class DataAnalysisTool(BaseTool):
    """Analyze CSV/JSON/Excel data files."""

    name = "data_analysis"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Analyze a CSV, JSON, or Excel data file. Runs in a "
                "sandboxed Python environment with pandas. Returns "
                "structured statistical results."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to data file (relative to project)",
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
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.data_analysis import data_analysis

        result = await data_analysis(
            file_path=args["file_path"],
            cwd=cwd,
            analysis_type=args.get("analysis_type", "summary"),
        )
        return result, False


class HypothesisTestTool(BaseTool):
    """Run statistical hypothesis tests."""

    name = "hypothesis_test"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Run a statistical hypothesis test. Supports t-test, "
                "paired t-test, one-sample t-test, chi-squared, "
                "Mann-Whitney U, ANOVA, Shapiro-Wilk, and Pearson correlation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "description": (
                            "Test: 'ttest', 'ttest_paired', 'ttest_1samp', "
                            "'chi2', 'mann_whitney', 'anova', 'shapiro', 'pearson'"
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
                        "description": "Second sample (for two-sample tests)",
                    },
                    "data_file": {
                        "type": "string",
                        "description": "CSV file path (alternative to inline data)",
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
                        "description": "Significance level (default 0.05)",
                        "default": 0.05,
                    },
                },
                "required": ["test_type"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.hypothesis_test import hypothesis_test

        result = await hypothesis_test(
            test_type=args["test_type"],
            cwd=cwd,
            data1=args.get("data1"),
            data2=args.get("data2"),
            data_file=args.get("data_file"),
            column1=args.get("column1"),
            column2=args.get("column2"),
            alpha=args.get("alpha", 0.05),
        )
        return result, False


class VisualizeTool(BaseTool):
    """Generate charts from data files."""

    name = "visualize"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Generate a chart from a data file (CSV/JSON/Excel) and "
                "save as PNG. Supports scatter, bar, histogram, heatmap, "
                "boxplot, line, and correlation_matrix charts."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the data file",
                    },
                    "chart_type": {
                        "type": "string",
                        "description": (
                            "Chart type: 'scatter', 'bar', 'histogram', "
                            "'heatmap', 'boxplot', 'line', 'correlation_matrix'"
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
                        "description": "Output PNG path (auto-generated if omitted)",
                    },
                },
                "required": ["file_path", "chart_type"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.visualize import visualize

        result = await visualize(
            file_path=args["file_path"],
            chart_type=args["chart_type"],
            cwd=cwd,
            x_column=args.get("x_column"),
            y_column=args.get("y_column"),
            title=args.get("title"),
            output_path=args.get("output_path"),
        )
        return result, False


# ──────────────────────────────────────────────────────────────────
# Experiment Tracking
# ──────────────────────────────────────────────────────────────────


class ExperimentLogTool(BaseTool):
    """Log a scientific experiment."""

    name = "experiment_log"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Log a scientific experiment with hypothesis, parameters, "
                "metrics, and results. Experiments are stored locally in "
                ".retrai/experiments/ for tracking and comparison."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short experiment name"},
                    "hypothesis": {"type": "string", "description": "The hypothesis being tested"},
                    "parameters": {
                        "type": "object",
                        "description": "Experiment parameters (key-value pairs)",
                    },
                    "metrics": {
                        "type": "object",
                        "description": "Result metrics (key-value number pairs)",
                    },
                    "result": {
                        "type": "string",
                        "description": (
                            "Outcome: 'confirmed', 'rejected', 'inconclusive', or 'error'"
                        ),
                    },
                    "notes": {"type": "string", "description": "Additional notes"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization",
                    },
                },
                "required": ["name"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.experiment.tracker import experiment_log

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
        return result, False


class ExperimentListTool(BaseTool):
    """List or compare past experiments."""

    name = "experiment_list"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "List past experiments or compare specific experiments "
                "by their IDs. Shows metrics, status, and rankings."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Filter by tag"},
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'running', 'completed', 'failed'",
                    },
                    "compare_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Experiment IDs to compare side-by-side",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.experiment.tracker import experiment_list

        result = await experiment_list(
            cwd=cwd,
            tag=args.get("tag"),
            status=args.get("status"),
            compare_ids=args.get("compare_ids"),
        )
        return result, False


# ──────────────────────────────────────────────────────────────────
# ML Training
# ──────────────────────────────────────────────────────────────────


class MlTrainTool(BaseTool):
    """Train sklearn-compatible ML models in the sandbox."""

    name = "ml_train"
    parallel_safe = False

    def get_schema(self) -> ToolSchema:
        from retrai.tools.ml_train import MODEL_REGISTRY

        return ToolSchema(
            name=self.name,
            description=(
                "Train a machine learning model in the sandbox. "
                "Supports sklearn, xgboost, and lightgbm models. "
                f"Models: {', '.join(sorted(MODEL_REGISTRY))}."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "data_file": {
                        "type": "string",
                        "description": "Path to CSV/JSON dataset",
                    },
                    "target_column": {
                        "type": "string",
                        "description": "Column name to predict",
                    },
                    "model_type": {
                        "type": "string",
                        "description": f"Model: {', '.join(sorted(MODEL_REGISTRY))}",
                    },
                    "task_type": {
                        "type": "string",
                        "description": "'classification' or 'regression' (auto-detected)",
                    },
                    "hyperparams": {
                        "type": "object",
                        "description": "Model hyperparameters",
                    },
                    "test_size": {
                        "type": "number",
                        "description": "Test split ratio (default 0.2)",
                        "default": 0.2,
                    },
                    "feature_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to use as features (default: all)",
                    },
                    "scoring_metric": {
                        "type": "string",
                        "description": "Metric: auc, f1, accuracy, r2, rmse, mae (default auc)",
                        "default": "auc",
                    },
                    "cross_validate": {
                        "type": "boolean",
                        "description": "Run cross-validation (default True)",
                        "default": True,
                    },
                },
                "required": ["data_file", "target_column", "model_type"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.ml_train import ml_train

        result = await ml_train(
            data_file=args["data_file"],
            target_column=args["target_column"],
            cwd=cwd,
            model_type=args.get("model_type", "random_forest"),
            task_type=args.get("task_type"),
            hyperparams=args.get("hyperparams"),
            test_size=args.get("test_size", 0.2),
            feature_columns=args.get("feature_columns"),
            scoring_metric=args.get("scoring_metric", "auc"),
            cross_validate=args.get("cross_validate", True),
            cv_folds=args.get("cv_folds", 5),
        )
        return result, False


# ──────────────────────────────────────────────────────────────────
# SQL Bench
# ──────────────────────────────────────────────────────────────────


class SqlBenchTool(BaseTool):
    """Run, explain, and profile SQL queries on Databricks or SQLAlchemy."""

    name = "sql_bench"
    parallel_safe = True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Run SQL benchmarks, get execution plans, or profile "
                "tables. Works with Databricks SQL Warehouses and "
                "SQLAlchemy databases. Connection config is read from "
                ".retrai.yml. Actions: 'run_query' (execute + timing), "
                "'explain_query' (EXPLAIN EXTENDED), 'profile_table' "
                "(schema, row count, properties)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": ("Action: 'run_query', 'explain_query', or 'profile_table'"),
                    },
                    "query": {
                        "type": "string",
                        "description": "SQL query (for run_query, explain_query)",
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name (for profile_table)",
                    },
                    "iterations": {
                        "type": "integer",
                        "description": "Times to run query (default 1)",
                        "default": 1,
                    },
                    "warmup": {
                        "type": "boolean",
                        "description": "Warmup run before timing (default false)",
                        "default": False,
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        from retrai.tools.sql_bench import sql_bench

        result = await sql_bench(
            action=args["action"],
            cwd=cwd,
            query=args.get("query", ""),
            table=args.get("table", ""),
            iterations=int(args.get("iterations", 1)),
            warmup=bool(args.get("warmup", False)),
        )
        return result, False


# ──────────────────────────────────────────────────────────────────
# Default Registry Factory
# ──────────────────────────────────────────────────────────────────

# Canonical list of all built-in tools, in the order they should
# appear in the LLM definitions list.
ALL_BUILTIN_TOOLS: list[type[BaseTool]] = [
    BashExecTool,
    FileReadTool,
    FileListTool,
    FileWriteTool,
    FilePatchTool,
    FileDeleteTool,
    FileRenameTool,
    FileInsertTool,
    GrepSearchTool,
    FindFilesTool,
    WebSearchTool,
    GitDiffTool,
    GitStatusTool,
    GitLogTool,
    RunPytestTool,
    PythonExecTool,
    JsExecTool,
    DatasetFetchTool,
    DataAnalysisTool,
    HypothesisTestTool,
    VisualizeTool,
    ExperimentLogTool,
    ExperimentListTool,
    MlTrainTool,
    SqlBenchTool,
]


def create_default_registry(*, discover_plugins: bool = True) -> ToolRegistry:
    """Create a :class:`ToolRegistry` pre-loaded with all built-in tools.

    Args:
        discover_plugins: If True, also discover and load tools from
            installed packages via the ``retrai.tools`` entry-point group.

    Returns:
        A fully populated registry ready for dispatch.
    """
    registry = ToolRegistry()
    registry.register_many([cls() for cls in ALL_BUILTIN_TOOLS])

    if discover_plugins:
        registry.discover_plugins()

    return registry
