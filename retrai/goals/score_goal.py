"""Generic LLM-scored goal — any task with a custom rubric and target score."""

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


class ScoreGoal(GoalBase):
    """Generic goal: produce output that scores ≥ target_score against a custom rubric.

    `.retrai.yml`:

    ```yaml
    goal: score
    task: "Summarise this research paper into a 1-page executive summary"
    input_file: paper.pdf        # optional context file for the agent
    output_file: summary.md      # where the agent writes its result
    target_score: 8              # 0-10, default 8
    rubric: |
      Score 0-10 on: accuracy (key findings preserved), brevity (≤400 words),
      clarity (no jargon), actionability (clear next steps).
    ```

    This is the most flexible non-coding goal — covers translation, summarisation,
    business plans, documentation, analysis, and anything else that produces text.
    """

    name = "score"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        cfg = _load_config(cwd)
        task = cfg.get("task", "")
        output_file = cfg.get("output_file", "output.md")
        target_score = float(cfg.get("target_score", 8))
        rubric = cfg.get("rubric", "")
        input_file = cfg.get("input_file", "")

        if not task:
            return GoalResult(
                achieved=False,
                reason="No task specified in .retrai.yml",
                details={"config": cfg},
            )

        root = Path(cwd)
        out_path = root / output_file

        if not out_path.exists():
            return GoalResult(
                achieved=False,
                reason=(
                    f"No output yet at '{output_file}'. "
                    "Complete the task and write the result to that file."
                ),
                details={"output_file": output_file, "task": task},
            )

        output_text = out_path.read_text(errors="replace")
        if not output_text.strip():
            return GoalResult(
                achieved=False,
                reason=f"Output file '{output_file}' is empty. Write the result first.",
                details={"output_file": output_file},
            )

        # Optionally load input file as context for the judge
        input_text = ""
        if input_file:
            in_path = root / input_file
            if in_path.exists():
                input_text = in_path.read_text(errors="replace")[:4000]

        model_name = state.get("model_name", "claude-sonnet-4-6")
        score, feedback = await _llm_score(
            task=task,
            output_text=output_text,
            rubric=rubric,
            input_text=input_text,
            model_name=model_name,
        )

        if score is None:
            return GoalResult(
                achieved=False,
                reason="LLM judge failed to score the output. Retry.",
                details={"feedback": feedback},
            )

        if score >= target_score:
            return GoalResult(
                achieved=True,
                reason=f"Output scored {score:.1f}/{target_score} ✅ — {feedback}",
                details={"score": score, "target_score": target_score, "feedback": feedback},
            )

        gap = target_score - score
        return GoalResult(
            achieved=False,
            reason=(
                f"Output scored {score:.1f}/{target_score} (need +{gap:.1f} more). "
                f"Feedback: {feedback}"
            ),
            details={"score": score, "target_score": target_score, "gap": gap, "feedback": feedback},  # noqa: E501
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        task = cfg.get("task", "<task description>")
        output_file = cfg.get("output_file", "output.md")
        target_score = cfg.get("target_score", 8)
        input_file = cfg.get("input_file", "")
        rubric = cfg.get("rubric", "")
        custom = cfg.get("system_prompt", "")

        input_str = f"\n**Input/context file**: `{input_file}`" if input_file else ""
        rubric_str = f"\n\n**Scoring rubric**:\n{rubric}" if rubric else ""

        base = (
            f"## Goal: Scored Task\n\n"
            f"**Task**: {task}\n"
            f"**Output file**: `{output_file}`\n"
            f"**Target score**: {target_score}/10"
            f"{input_str}"
            f"{rubric_str}\n\n"
            "**Strategy**:\n"
            "1. Read the task description and any input files carefully.\n"
            f"2. Produce the output and write it to `{output_file}`.\n"
            "3. The goal will score your output against the rubric and give feedback.\n"
            "4. Revise your output based on the feedback.\n"
            "5. Repeat until the target score is reached.\n\n"
            "**Tips**:\n"
            "- Read the rubric carefully — it tells you exactly how you'll be scored\n"
            "- Address every rubric criterion explicitly\n"
            "- Each revision should meaningfully improve the lowest-scoring areas\n"
            "- Don't be afraid to restructure or rewrite substantially\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base


async def _llm_score(
    task: str,
    output_text: str,
    rubric: str,
    input_text: str,
    model_name: str,
) -> tuple[float | None, str]:
    """Ask the LLM to score the output 0-10 and return (score, feedback)."""
    from langchain_core.messages import HumanMessage

    from retrai.llm.factory import get_llm

    rubric_section = (
        f"\n## SCORING RUBRIC\n{rubric}"
        if rubric
        else "\n## SCORING CRITERIA\nScore 0-10 on overall quality, completeness, and how well the output satisfies the task."  # noqa: E501
    )

    input_section = (
        f"\n## INPUT / CONTEXT\n{input_text[:3000]}"
        if input_text
        else ""
    )

    prompt = f"""You are an expert evaluator. Score the following output against the task requirements.  # noqa: E501

## TASK
{task}
{input_section}
## OUTPUT TO EVALUATE
{output_text[:6000]}
{rubric_section}

## RESPONSE FORMAT
Respond with a JSON object:
{{
  "score": <number 0-10, one decimal place>,
  "feedback": "<2-3 sentences: what's good, what's missing or weak, specific actionable suggestions>"  # noqa: E501
}}

Be honest and specific. A score of 8+ means the output genuinely and fully satisfies the task.
Respond with ONLY the JSON object."""

    try:
        llm = get_llm(model_name, temperature=0.1)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = str(response.content).strip()

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
