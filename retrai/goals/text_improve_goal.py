"""Text improvement goal — iteratively improve a text file until LLM score ≥ target."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)

_CONFIG_FILE = ".retrai.yml"


def _load_config(cwd: str) -> dict:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


class TextImproveGoal(GoalBase):
    """Iteratively improve a text file until an LLM judge scores it ≥ target_score.

    `.retrai.yml`:

    ```yaml
    goal: text-improve
    input_file: draft.md          # source text to improve
    output_file: improved.md      # where the agent writes its result (optional)
    target_score: 8               # 0-10, default 8
    criteria:                     # optional rubric items
      - clarity
      - conciseness
      - persuasiveness
    ```

    The agent reads the current text, improves it, writes the result, and the
    goal checks the score on each iteration until target_score is reached.
    """

    name = "text-improve"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        input_file = cfg.get("input_file", "")
        output_file = cfg.get("output_file", input_file)
        target_score = float(cfg.get("target_score", 8))
        criteria: list[str] = cfg.get("criteria", [])

        if not input_file:
            return GoalResult(
                achieved=False,
                reason="No input_file specified in .retrai.yml",
                details={"config": cfg},
            )

        root = Path(cwd)
        # Prefer the output file if it exists, otherwise fall back to input
        text_path = root / output_file
        if not text_path.exists():
            text_path = root / input_file
        if not text_path.exists():
            return GoalResult(
                achieved=False,
                reason=f"Input file '{input_file}' not found. Create it first.",
                details={"input_file": input_file},
            )

        text = text_path.read_text(errors="replace")
        if not text.strip():
            return GoalResult(
                achieved=False,
                reason="Text file is empty. Write some content first.",
                details={"file": str(text_path)},
            )

        model_name = state.get("model_name", "claude-sonnet-4-6")
        score, feedback = await _llm_score(text, criteria, model_name)

        if score is None:
            return GoalResult(
                achieved=False,
                reason="LLM judge failed to score the text. Retry.",
                details={"feedback": feedback},
            )

        if score >= target_score:
            return GoalResult(
                achieved=True,
                reason=f"Text scored {score:.1f}/{target_score} ✅ — {feedback}",
                details={"score": score, "target_score": target_score, "feedback": feedback},
            )

        gap = target_score - score
        return GoalResult(
            achieved=False,
            reason=(
                f"Text scored {score:.1f}/{target_score} (need +{gap:.1f} more). "
                f"Feedback: {feedback}"
            ),
            details={"score": score, "target_score": target_score, "gap": gap, "feedback": feedback},  # noqa: E501
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        input_file = cfg.get("input_file", "<input_file>")
        output_file = cfg.get("output_file", input_file)
        target_score = cfg.get("target_score", 8)
        criteria = cfg.get("criteria", ["clarity", "conciseness", "quality"])
        custom = cfg.get("system_prompt", "")

        criteria_str = ", ".join(criteria) if criteria else "clarity, conciseness, quality"

        base = (
            f"## Goal: Text Improvement\n\n"
            f"Improve the text in `{input_file}` and write the result to `{output_file}`.\n"
            f"Target score: **{target_score}/10** on: {criteria_str}\n\n"
            "**Strategy**:\n"
            f"1. Read `{input_file}` to understand the current text.\n"
            "2. Identify weaknesses based on the scoring criteria.\n"
            "3. Rewrite and improve the text — be bold, not just cosmetic.\n"
            f"4. Write the improved version to `{output_file}`.\n"
            "5. The goal will score your output and tell you what still needs work.\n"
            "6. Repeat until the target score is reached.\n\n"
            "**Tips**:\n"
            "- Each iteration should make a meaningful improvement, not just minor edits\n"
            "- Read the feedback from the previous score carefully\n"
            "- Focus on the lowest-scoring criteria first\n"
            "- It's OK to restructure, reorder, or rewrite entire sections\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base


async def _llm_score(
    text: str,
    criteria: list[str],
    model_name: str,
) -> tuple[float | None, str]:
    """Ask the LLM to score the text 0-10 and return (score, feedback)."""
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm

    criteria_str = (
        ", ".join(criteria)
        if criteria
        else "clarity, conciseness, coherence, and overall quality"
    )

    prompt = f"""You are a professional editor and writing coach. Score the following text.

## TEXT TO EVALUATE
{text[:8000]}

## SCORING CRITERIA
Score 0-10 on: {criteria_str}

## RESPONSE FORMAT
Respond with a JSON object:
{{
  "score": <number 0-10, one decimal place>,
  "feedback": "<2-3 sentences: what's good, what needs improvement, specific suggestions>"
}}

Be honest and specific. A score of 8+ means the text is genuinely excellent.
Respond with ONLY the JSON object."""

    try:
        llm = get_llm(model_name, temperature=0.1)
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

        result = json.loads(content)
        score = float(result.get("score", 0))
        feedback = str(result.get("feedback", "No feedback provided"))
        return score, feedback
    except Exception as e:
        logger.warning("LLM scoring failed: %s", e)
        return None, str(e)
