"""Memory extractor — distill run outcomes into reusable learnings."""

from __future__ import annotations

import json
import logging

from retrai.memory.store import Memory, MemoryStore

logger = logging.getLogger(__name__)


async def extract_learnings(
    run_id: str,
    goal_name: str,
    achieved: bool,
    iterations_used: int,
    cwd: str,
    model_name: str,
) -> list[Memory]:
    """Extract 1-3 reusable learnings from a completed run.

    Uses an LLM to analyze the run context and distill insights
    that could help future runs on the same project.
    """
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm

    # Gather context about what happened
    diff_text = await _get_recent_diff(cwd)
    if not diff_text:
        return []

    prompt = f"""You are a learning extraction agent. A coding agent just completed a run.
Analyze the outcome and extract 1-3 reusable insights for future runs.

## Run Details
- **Goal**: {goal_name}
- **Achieved**: {achieved}
- **Iterations used**: {iterations_used}
- **Project directory**: {cwd}

## Changes Made (git diff)
```diff
{diff_text[:4000]}
```

## Instructions
Extract 1-3 learnings. Each learning should be a single, actionable sentence
that would help a future agent working on this project.

Respond with a JSON array:
```json
[
  {{"insight": "The tests require REDIS_URL env var", "category": "project_fact"}},
  {{"insight": "Use file_patch for single-line fixes", "category": "strategy"}}
]
```

Categories:
- "project_fact": facts about the project structure or requirements
- "strategy": successful approach or technique
- "error_pattern": common error and how to fix it
- "tip": general productivity tip

Respond with ONLY the JSON array."""

    try:
        llm = get_llm(model_name, temperature=0.2)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = str(response.content).strip()

        # Strip markdown fences
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        items = json.loads(content)
        if not isinstance(items, list):
            return []

        memories: list[Memory] = []
        for item in items[:3]:  # Max 3
            memories.append(
                Memory(
                    insight=str(item.get("insight", "")),
                    category=str(item.get("category", "tip")),
                    run_id=run_id,
                )
            )
        return memories

    except Exception as e:
        logger.warning("Failed to extract learnings: %s", e)
        return []


async def extract_and_store(
    run_id: str,
    goal_name: str,
    achieved: bool,
    iterations_used: int,
    cwd: str,
    model_name: str,
) -> int:
    """Extract learnings and store them in the project memory.

    Returns the number of learnings stored.
    """
    memories = await extract_learnings(
        run_id=run_id,
        goal_name=goal_name,
        achieved=achieved,
        iterations_used=iterations_used,
        cwd=cwd,
        model_name=model_name,
    )

    if memories:
        store = MemoryStore(cwd)
        store.add_batch(memories)
        logger.info("Stored %d learnings from run %s", len(memories), run_id)

    return len(memories)


async def _get_recent_diff(cwd: str) -> str:
    """Get the recent git diff for learning extraction."""
    try:
        from retrai.tools.git_diff import git_diff

        return await git_diff(cwd=cwd, staged=False)
    except Exception:
        return ""
