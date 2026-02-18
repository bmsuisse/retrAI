"""LLM-powered task decomposition for the swarm orchestrator."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from retrai.swarm.types import SubTask

logger = logging.getLogger(__name__)


async def decompose_goal(
    description: str,
    cwd: str,
    model_name: str = "claude-sonnet-4-6",
    max_subtasks: int = 5,
) -> list[SubTask]:
    """Decompose a high-level goal into concrete sub-tasks.

    Uses the LLM to analyze the project context and break the goal
    into 2-5 independent sub-tasks that can be worked on in parallel.
    """
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm

    context = _build_context(cwd)
    prompt = _build_decompose_prompt(description, context, max_subtasks)

    llm = get_llm(model_name, temperature=0.2)
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    content = str(response.content)
    return _parse_subtasks(content)


def _build_context(cwd: str) -> str:
    """Build a compact project overview for decomposition."""
    root = Path(cwd).resolve()
    parts: list[str] = []

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
                        if sub.name.startswith(".") or sub.name in skip_dirs:
                            continue
                        suffix = "/" if sub.is_dir() else ""
                        tree_lines.append(f"    {sub.name}{suffix}")
                except PermissionError:
                    pass
            else:
                tree_lines.append(f"  {name}")
    except PermissionError:
        pass

    if tree_lines:
        parts.append("## Directory structure\n```\n" + "\n".join(tree_lines) + "\n```")

    # Read key config files
    config_files = [
        "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
        ".retrai.yml", "Makefile",
    ]
    for fname in config_files:
        fpath = root / fname
        if fpath.exists() and fpath.is_file():
            try:
                content = fpath.read_text(errors="replace")
                lines = content.splitlines()[:100]
                snippet = "\n".join(lines)
                parts.append(f"## {fname}\n```\n{snippet}\n```")
            except OSError:
                pass

    return "\n\n".join(parts)


def _build_decompose_prompt(
    description: str,
    context: str,
    max_subtasks: int,
) -> str:
    return f"""You are an expert software architect. Your job is to decompose a complex goal
into smaller, independent sub-tasks that can be worked on IN PARALLEL by separate AI agents.

## GOAL
{description}

## PROJECT CONTEXT
{context}

## AVAILABLE SPECIALIST ROLES
You may assign a role to each sub-task to use a specialist agent:
- "researcher": Literature search, data collection, exploration
- "analyst": Statistical analysis, data processing, hypothesis testing
- "reviewer": Critical evaluation, methodology checking, quality assurance
- "synthesizer": Combining findings into conclusions and reports

Leave "role" empty for general-purpose tasks.

## INSTRUCTIONS
Break the goal into 2-{max_subtasks} independent sub-tasks. Each sub-task should be:
1. **Self-contained**: Can be completed without depending on the results of other sub-tasks
2. **Focused**: Targets specific files or components
3. **Actionable**: Clear enough for an AI agent to execute without ambiguity

Respond with a JSON array of objects, each with these fields:
- "id": short unique identifier (e.g. "task-1")
- "description": detailed description of what to do
- "focus_files": list of file paths this task should focus on (can be globs like "src/*.py")
- "strategy_hint": a hint about what approach to take
- "role": optional specialist role (researcher, analyst, reviewer, synthesizer)

Respond with ONLY the JSON array, no other text. Example:
```json
[
  {{
    "id": "task-1",
    "description": "Search PubMed and arXiv for papers on the topic",
    "focus_files": [],
    "strategy_hint": "Use dataset_fetch with pubmed and arxiv sources",
    "role": "researcher"
  }},
  {{
    "id": "task-2",
    "description": "Analyze the collected data and run statistical tests",
    "focus_files": ["data/*.csv"],
    "strategy_hint": "Use data_analysis and hypothesis_test tools",
    "role": "analyst"
  }}
]
```"""


def _parse_subtasks(content: str) -> list[SubTask]:
    """Parse the LLM response into SubTask objects."""
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Failed to parse decomposition response, creating single task")
        return [
            SubTask(
                id=f"task-{uuid.uuid4().hex[:6]}",
                description=content[:500],
                focus_files=[],
                strategy_hint="",
            )
        ]

    if not isinstance(raw, list):
        raw = [raw]

    subtasks: list[SubTask] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        subtasks.append(
            SubTask(
                id=item.get("id", f"task-{i + 1}"),
                description=item.get("description", ""),
                focus_files=item.get("focus_files", []),
                strategy_hint=item.get("strategy_hint", ""),
                role=item.get("role", ""),
            )
        )

    if not subtasks:
        subtasks.append(
            SubTask(
                id=f"task-{uuid.uuid4().hex[:6]}",
                description="Complete the goal",
                focus_files=[],
                strategy_hint="",
            )
        )

    return subtasks
