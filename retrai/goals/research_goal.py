"""Research goal: guide agent through a full scientific research workflow."""

from __future__ import annotations

import logging
from pathlib import Path

from retrai.experiment.tracker import ExperimentTracker
from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)


class ResearchGoal(GoalBase):
    """Goal that guides the agent through literature → data → analysis → report.

    The agent is done when:
    1. A literature review file exists
    2. At least one dataset was collected
    3. At least one experiment was logged
    4. A final report was written

    Progress is tracked incrementally (0-100%).
    """

    name = "research"

    def __init__(
        self,
        topic: str = "",
        output_dir: str = ".retrai/research",
    ) -> None:
        self.topic = topic
        self.output_dir = output_dir

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Check how much of the research pipeline is complete."""
        root = Path(cwd).resolve()
        out = root / self.output_dir
        phases: dict[str, bool] = {}

        # Phase 1: Literature review
        lit_review = out / "literature_review.md"
        phases["literature_review"] = (
            lit_review.exists() and lit_review.stat().st_size > 100
        )

        # Phase 2: Data collection
        data_dir = out / "data"
        phases["data_collection"] = (
            data_dir.exists()
            and any(data_dir.iterdir())
        ) if data_dir.exists() else False

        # Phase 3: Analysis (at least one experiment logged)
        tracker = ExperimentTracker(cwd)
        experiments = tracker.list_experiments()
        phases["analysis"] = len(experiments) > 0

        # Phase 4: Report
        report = out / "report.md"
        phases["report"] = (
            report.exists() and report.stat().st_size > 200
        )

        completed = sum(1 for v in phases.values() if v)
        total = len(phases)
        pct = int((completed / total) * 100) if total > 0 else 0

        # Build status string
        icons = {True: "✅", False: "❌"}
        status_parts = [
            f"{name.replace('_', ' ')}: {icons[done]}"
            for name, done in phases.items()
        ]
        status_str = ", ".join(status_parts)

        if completed == total:
            return GoalResult(
                achieved=True,
                reason=(
                    f"Research complete ({pct}%): {status_str}"
                ),
                details={
                    "phases": phases,
                    "percentage": pct,
                    "experiments": len(experiments),
                },
            )

        return GoalResult(
            achieved=False,
            reason=(
                f"Research {pct}% complete: {status_str}"
            ),
            details={
                "phases": phases,
                "percentage": pct,
                "experiments": len(experiments),
                "next_phase": next(
                    (k for k, v in phases.items() if not v),
                    None,
                ),
            },
        )

    def system_prompt(self) -> str:
        topic_str = self.topic or "the given topic"
        out_dir = self.output_dir

        return (
            f"Your goal is to conduct a complete scientific "
            f"investigation on: **{topic_str}**\n\n"
            "Follow this research pipeline strictly in order:\n\n"
            "### Phase 1: LITERATURE REVIEW\n"
            "- Use `dataset_fetch` with source='pubmed' and "
            "source='arxiv' to find relevant papers\n"
            "- Use `web_search` for additional context\n"
            f"- Write a literature review to "
            f"`{out_dir}/literature_review.md`\n"
            "- Include paper titles, authors, key findings, "
            "and URLs\n\n"
            "### Phase 2: DATA COLLECTION\n"
            "- Download or create relevant datasets\n"
            f"- Save data files to `{out_dir}/data/`\n"
            "- Use `dataset_fetch` source='url' or "
            "source='huggingface' for public datasets\n\n"
            "### Phase 3: ANALYSIS\n"
            "- Use `data_analysis` for exploratory data "
            "analysis (summary stats, distributions)\n"
            "- Use `hypothesis_test` for statistical testing\n"
            "- Use `visualize` to create charts supporting "
            "your findings\n"
            "- Log EVERY analysis with `experiment_log` "
            "(hypothesis, parameters, metrics, result)\n\n"
            "### Phase 4: REPORT\n"
            f"- Write a comprehensive report to "
            f"`{out_dir}/report.md`\n"
            "- Structure: Executive Summary, Background, "
            "Methodology, Key Findings, Visualizations, "
            "Limitations, Conclusions, Next Steps\n"
            "- Reference all experiments and literature\n\n"
            "### Rules\n"
            "- Complete phases in order\n"
            "- Log every experiment for reproducibility\n"
            "- Cite every claim with evidence\n"
            "- Create at least one visualization\n"
        )
