"""SolverGoal — LLM-as-judge evaluation for natural language goals."""

from __future__ import annotations

import json
import logging

from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)


class SolverGoal(GoalBase):
    """A goal that uses an LLM-as-judge to evaluate natural language descriptions.

    Unlike test-based goals, the solver evaluates success by asking the LLM
    to judge whether the project's current state satisfies the description.
    """

    name = "solve"

    def __init__(self, description: str) -> None:
        self.description = description

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Use core heuristics + LLM-as-judge to evaluate the goal."""
        iteration = state.get("iteration", 0)

        # Don't do LLM evaluation on first iteration (nothing has changed yet)
        if iteration < 1:
            return GoalResult(
                achieved=False,
                reason="Initial iteration — no changes made yet.",
                details={},
            )

        # Gather context about what changed via git diff
        diff_text = await self._get_diff(cwd)
        if not diff_text.strip():
            return GoalResult(
                achieved=False,
                reason="No changes detected yet. Make code changes to satisfy the goal.",
                details={},
            )

        # Use LLM as judge
        verdict = await self._llm_judge(state, cwd, diff_text)
        return verdict

    async def _get_diff(self, cwd: str) -> str:
        """Get the current git diff."""
        try:
            from retrai.tools.git_diff import git_diff

            return await git_diff(cwd=cwd, staged=False)
        except Exception:
            return ""

    async def _llm_judge(self, state: dict, cwd: str, diff_text: str) -> GoalResult:
        """Ask the LLM to judge whether the goal has been achieved."""
        from langchain_core.messages import HumanMessage

        from retrai.llm.factory import get_llm

        model_name = state.get("model_name", "claude-sonnet-4-6")

        prompt = f"""You are a code review judge. Evaluate whether the following changes
satisfy the stated goal.

## GOAL
{self.description}

## CHANGES MADE (git diff)
```diff
{diff_text[:6000]}
```

## EVALUATION
Respond with a JSON object:
{{
  "achieved": true or false,
  "reason": "Brief explanation of why the goal is or isn't achieved",
  "confidence": 0.0 to 1.0
}}

Rules:
- Set "achieved" to true ONLY if the changes clearly and fully address the goal
- If partial progress has been made but more work is needed, set "achieved" to false
- Be strict but fair — small imperfections are OK if the core goal is met
- The "reason" should be specific about what was done or what's missing

Respond with ONLY the JSON object."""

        try:
            llm = get_llm(model_name, temperature=0.0)
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
            achieved = bool(result.get("achieved", False))
            reason = str(result.get("reason", "No reason provided"))
            confidence = float(result.get("confidence", 0.5))

            return GoalResult(
                achieved=achieved,
                reason=reason,
                details={"confidence": confidence, "judge_model": model_name},
            )
        except Exception as e:
            logger.warning("LLM judge failed: %s", e)
            return GoalResult(
                achieved=False,
                reason=f"Judge evaluation failed: {e}. Continue working on the goal.",
                details={"error": str(e)},
            )

    def system_prompt(self, cwd: str = ".") -> str:
        """Return the system prompt for the solver agent."""
        return (
            f"## Goal: Solve a Problem\n\n"
            f"**Description**: {self.description}\n\n"
            f"You must make changes to the codebase to satisfy this goal. "
            f"The goal will be evaluated by an LLM judge that reads your git diff.\n\n"
            f"**Important**: Make real, meaningful changes. The judge will verify "
            f"that the diff actually addresses the goal description.\n\n"
            f"**Strategy**:\n"
            f"1. First, understand the codebase by reading relevant files\n"
            f"2. Plan your approach — think about what needs to change\n"
            f"3. Make the changes using file_patch or file_write\n"
            f"4. Verify your changes work (run tests, type checks, etc.)\n"
            f"5. Review the diff to ensure it matches the goal"
        )
