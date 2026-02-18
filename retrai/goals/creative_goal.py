"""Creative writing goal — generate and refine creative content until LLM score ≥ target."""

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


class CreativeGoal(GoalBase):
    """Generate and refine creative content until an LLM judge scores it ≥ target_score.

    `.retrai.yml`:

    ```yaml
    goal: creative
    prompt: "Write a short story about a robot learning to paint"
    output_file: story.md
    target_score: 8               # 0-10, default 8
    style: "literary fiction, melancholic"  # optional style guidance
    max_words: 1000               # optional word count limit
    ```

    The agent generates content, then iteratively refines it based on judge feedback
    until the target score is reached.
    """

    name = "creative"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        prompt = cfg.get("prompt", "")
        output_file = cfg.get("output_file", "output.md")
        target_score = float(cfg.get("target_score", 8))
        style = cfg.get("style", "")
        max_words = cfg.get("max_words")

        if not prompt:
            return GoalResult(
                achieved=False,
                reason="No prompt specified in .retrai.yml",
                details={"config": cfg},
            )

        root = Path(cwd)
        out_path = root / output_file

        if not out_path.exists():
            return GoalResult(
                achieved=False,
                reason=(
                    f"No output yet at '{output_file}'. "
                    "Generate the creative content and write it to that file."
                ),
                details={"output_file": output_file, "prompt": prompt},
            )

        content = out_path.read_text(errors="replace")
        if not content.strip():
            return GoalResult(
                achieved=False,
                reason=f"Output file '{output_file}' is empty. Write the content first.",
                details={"output_file": output_file},
            )

        model_name = state.get("model_name", "claude-sonnet-4-6")
        score, feedback = await _llm_score_creative(
            content=content,
            brief=prompt,
            style=style,
            max_words=max_words,
            model_name=model_name,
        )

        if score is None:
            return GoalResult(
                achieved=False,
                reason="LLM judge failed to score the content. Retry.",
                details={"feedback": feedback},
            )

        if score >= target_score:
            return GoalResult(
                achieved=True,
                reason=(
                    f"Creative content scored {score:.1f}/{target_score} ✅ — "
                    f"{feedback}"
                ),
                details={"score": score, "target_score": target_score, "feedback": feedback},
            )

        gap = target_score - score
        return GoalResult(
            achieved=False,
            reason=(
                f"Content scored {score:.1f}/{target_score} (need +{gap:.1f} more). "
                f"Feedback: {feedback}"
            ),
            details={
                "score": score,
                "target_score": target_score,
                "gap": gap,
                "feedback": feedback,
            },
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        prompt = cfg.get("prompt", "<creative brief>")
        output_file = cfg.get("output_file", "output.md")
        target_score = cfg.get("target_score", 8)
        style = cfg.get("style", "")
        max_words = cfg.get("max_words")
        custom = cfg.get("system_prompt", "")

        style_str = f" Style: {style}." if style else ""
        words_str = f" Max words: {max_words}." if max_words else ""

        base = (
            f"## Goal: Creative Writing\n\n"
            f"**Brief**: {prompt}\n"
            f"**Output file**: `{output_file}`\n"
            f"**Target score**: {target_score}/10{style_str}{words_str}\n\n"
            "**Strategy**:\n"
            "1. Read the brief carefully — understand the tone, subject, and constraints.\n"
            f"2. Generate the creative content and write it to `{output_file}`.\n"
            "3. The goal will score your output and give specific feedback.\n"
            "4. Revise based on the feedback — be willing to rewrite substantially.\n"
            "5. Repeat until the target score is reached.\n\n"
            "**Creative tips**:\n"
            "- Strong opening hook — grab attention immediately\n"
            "- Show, don't tell — use concrete details and sensory language\n"
            "- Consistent voice and tone throughout\n"
            "- Satisfying structure: beginning, middle, end (or equivalent)\n"
            "- Read the judge feedback carefully — it tells you exactly what to fix\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base


async def _llm_score_creative(
    content: str,
    brief: str,
    style: str,
    max_words: int | None,
    model_name: str,
) -> tuple[float | None, str]:
    """Ask the LLM to score creative content 0-10 and return (score, feedback)."""
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm

    style_note = f"\nExpected style: {style}" if style else ""  # noqa: E501
    words_note = f"\nWord limit: {max_words} words" if max_words else ""  # noqa: E501

    prompt = f"""You are a literary editor and creative writing coach. Evaluate the following content.  # noqa: E501

## CREATIVE BRIEF
{brief}{style_note}{words_note}

## CONTENT TO EVALUATE
{content[:8000]}

## SCORING
Score 0-10 on:
- Adherence to brief (does it match what was asked?)
- Originality and creativity
- Quality of writing (voice, style, language)
- Structure and flow
- Emotional impact / engagement

## RESPONSE FORMAT
Respond with a JSON object:
{{
  "score": <number 0-10, one decimal place>,
  "feedback": "<2-3 sentences: strengths, specific weaknesses, concrete suggestions for improvement>"  # noqa: E501
}}

Be honest. A score of 8+ means genuinely excellent creative work.
Respond with ONLY the JSON object."""

    try:
        llm = get_llm(model_name, temperature=0.1)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content_str = str(response.content).strip()

        if content_str.startswith("```json"):
            content_str = content_str[7:]
        elif content_str.startswith("```"):
            content_str = content_str[3:]
        if content_str.endswith("```"):
            content_str = content_str[:-3]
        content_str = content_str.strip()

        result = json.loads(content_str)
        score = float(result.get("score", 0))
        feedback = str(result.get("feedback", "No feedback provided"))
        return score, feedback
    except Exception as e:
        logger.warning("LLM creative scoring failed: %s", e)
        return None, str(e)
