"""Cancer research goal — full biomedical research pipeline.

Guides the agent through a rigorous scientific investigation:
  Phase 1: Literature review (PubMed, arXiv, ClinicalTrials.gov)
  Phase 2: Molecular/pathway data (UniProt, ChEMBL, PDB)
  Phase 3: Statistical analysis + hypothesis testing
  Phase 4: Computational experiment (ML on biological data)
  Phase 5: Full scientific report with citations
"""

from __future__ import annotations

import logging
from pathlib import Path

from retrai.experiment.tracker import ExperimentTracker
from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)


class CancerResearchGoal(GoalBase):
    """Goal that guides the agent through a full cancer research pipeline.

    The agent is done when all 5 phases are complete:
    1. Literature review (PubMed + arXiv + ClinicalTrials)
    2. Molecular/pathway data collected (UniProt/ChEMBL/PDB)
    3. Statistical analysis performed (at least one experiment logged)
    4. Computational model trained on biological data
    5. Comprehensive scientific report written

    Progress is tracked incrementally (0-100%).

    `.retrai.yml` config:
    ```yaml
    goal: cancer-research
    topic: "KRAS G12C inhibitors for non-small cell lung cancer"
    output_dir: .retrai/research
    ```
    """

    name = "cancer-research"

    def __init__(
        self,
        topic: str = "",
        output_dir: str = ".retrai/research",
    ) -> None:
        self.topic = topic
        self.output_dir = output_dir

    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Check how much of the cancer research pipeline is complete."""
        import yaml

        # Load config from .retrai.yml if present
        config_path = Path(cwd) / ".retrai.yml"
        if config_path.exists():
            try:
                cfg = yaml.safe_load(config_path.read_text()) or {}
                if cfg.get("topic"):
                    self.topic = cfg["topic"]
                if cfg.get("output_dir"):
                    self.output_dir = cfg["output_dir"]
            except Exception:
                pass

        root = Path(cwd).resolve()
        out = root / self.output_dir
        phases: dict[str, bool] = {}

        # Phase 1: Literature review (PubMed + arXiv + ClinicalTrials)
        lit_review = out / "literature_review.md"
        phases["literature_review"] = (
            lit_review.exists()
            and lit_review.stat().st_size > 500
            # Must mention at least one of the key biomedical sources
            and any(
                kw in lit_review.read_text().lower()
                for kw in ("pubmed", "pmid", "doi", "arxiv", "clinical", "trial", "ncbi")
            )
        )

        # Phase 2: Molecular/pathway data
        mol_dir = out / "molecular_data"
        mol_files = list(mol_dir.glob("*")) if mol_dir.exists() else []
        phases["molecular_data"] = len(mol_files) > 0

        # Phase 3: Statistical analysis (at least one experiment logged)
        tracker = ExperimentTracker(cwd)
        experiments = tracker.list_experiments()
        phases["statistical_analysis"] = len(experiments) > 0

        # Phase 4: Computational model
        # Check for any model output file or ml_train result in tool outputs
        model_files = list(out.glob("model*")) + list(out.glob("*.pkl")) + list(out.glob("*.joblib"))
        has_model_in_tools = self._has_ml_result(state)
        phases["computational_model"] = len(model_files) > 0 or has_model_in_tools

        # Phase 5: Scientific report
        report = out / "report.md"
        phases["scientific_report"] = (
            report.exists()
            and report.stat().st_size > 1000
            # Must have structured sections
            and any(
                section in report.read_text()
                for section in ("## Abstract", "## Methods", "## Results", "## Conclusion")
            )
        )

        completed = sum(1 for v in phases.values() if v)
        total = len(phases)
        pct = int((completed / total) * 100) if total > 0 else 0

        icons = {True: "✅", False: "❌"}
        status_parts = [
            f"{name.replace('_', ' ')}: {icons[done]}" for name, done in phases.items()
        ]
        status_str = " | ".join(status_parts)

        if completed == total:
            return GoalResult(
                achieved=True,
                reason=f"Cancer research complete ({pct}%): {status_str}",
                details={
                    "phases": phases,
                    "percentage": pct,
                    "experiments": len(experiments),
                    "topic": self.topic,
                },
            )

        next_phase = next((k for k, v in phases.items() if not v), None)
        return GoalResult(
            achieved=False,
            reason=f"Research {pct}% complete: {status_str}",
            details={
                "phases": phases,
                "percentage": pct,
                "experiments": len(experiments),
                "next_phase": next_phase,
                "topic": self.topic,
            },
        )

    def _has_ml_result(self, state: dict) -> bool:
        """Check if any ml_train tool result exists in the agent state."""
        for tr in state.get("tool_results", []):
            if tr.get("name") == "ml_train":
                return True
        for msg in state.get("messages", []):
            if getattr(msg, "name", "") == "ml_train":
                return True
        return False

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        import yaml

        topic = self.topic
        out_dir = self.output_dir
        custom = ""

        config_path = Path(cwd) / ".retrai.yml"
        if config_path.exists():
            try:
                cfg = yaml.safe_load(config_path.read_text()) or {}
                topic = cfg.get("topic", topic)
                out_dir = cfg.get("output_dir", out_dir)
                custom = cfg.get("system_prompt", "")
            except Exception:
                pass

        topic_str = topic or "the given cancer/disease topic"

        base = (
            f"## Goal: Cancer Research Investigation\n\n"
            f"Conduct a rigorous, multi-phase scientific investigation on:\n"
            f"**{topic_str}**\n\n"
            "You are a world-class computational biologist and oncologist. "
            "Follow this pipeline strictly in order:\n\n"
            "### Phase 1: LITERATURE REVIEW\n"
            "- Use `bio_search` with source='pubmed' to find recent papers "
            "(last 5 years preferred)\n"
            "- Use `bio_search` with source='clinicaltrials' for ongoing trials\n"
            "- Use `dataset_fetch` with source='arxiv' for preprints\n"
            "- Use `web_search` for additional context\n"
            f"- Write a structured literature review to `{out_dir}/literature_review.md`\n"
            "- Include: paper titles, authors, PMIDs/DOIs, key findings, "
            "mechanisms of action, clinical outcomes\n\n"
            "### Phase 2: MOLECULAR/PATHWAY DATA\n"
            "- Use `bio_search` with source='uniprot' to get protein data for "
            "key targets\n"
            "- Use `bio_search` with source='chembl' for drug-target bioactivity\n"
            "- Use `bio_search` with source='pdb' for 3D structure data\n"
            f"- Save all data files to `{out_dir}/molecular_data/`\n"
            "- Document key targets, pathways, and drug candidates\n\n"
            "### Phase 3: STATISTICAL ANALYSIS\n"
            "- Use `data_analysis` on any collected datasets\n"
            "- Use `hypothesis_test` to test biological hypotheses "
            "(e.g., bioactivity differences between compound classes)\n"
            "- Use `visualize` to create charts (IC50 distributions, "
            "survival curves, pathway maps)\n"
            "- Log EVERY analysis with `experiment_log`\n\n"
            "### Phase 4: COMPUTATIONAL MODEL\n"
            "- Use `ml_train` to build predictive models "
            "(e.g., bioactivity prediction, patient stratification)\n"
            "- Try multiple algorithms and report cross-validation metrics\n"
            "- Interpret feature importance biologically\n"
            "- Log all model runs with `experiment_log`\n\n"
            "### Phase 5: SCIENTIFIC REPORT\n"
            f"- Write a comprehensive report to `{out_dir}/report.md`\n"
            "- Required sections: ## Abstract, ## Background, ## Methods, "
            "## Results, ## Discussion, ## Conclusion, ## References\n"
            "- Include all visualizations and cite all experiments\n"
            "- Propose concrete next steps for wet-lab validation\n\n"
            "### Critical Rules\n"
            "- Complete phases in order — do not skip\n"
            "- Every claim must be backed by data or literature\n"
            "- Use PMID/DOI citations for every paper referenced\n"
            "- Think like a Nature paper reviewer: rigor, reproducibility, impact\n"
            "- If a database API fails, try an alternative source\n"
        )
        return (custom + "\n\n" + base).strip() if custom else base
