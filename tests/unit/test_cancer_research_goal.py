"""Tests for CancerResearchGoal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from retrai.goals.cancer_research_goal import CancerResearchGoal


def _make_state(**kwargs) -> dict:
    base = {
        "messages": [],
        "tool_results": [],
        "iteration": 1,
    }
    base.update(kwargs)
    return base


class TestCancerResearchGoalCheck:
    @pytest.mark.asyncio
    async def test_no_phases_complete(self, tmp_path: Path) -> None:
        goal = CancerResearchGoal(topic="KRAS G12C", output_dir=".retrai/research")
        state = _make_state()
        result = await goal.check(state, str(tmp_path))
        assert result.achieved is False
        assert "0%" in result.reason
        assert result.details["percentage"] == 0

    @pytest.mark.asyncio
    async def test_literature_review_phase(self, tmp_path: Path) -> None:
        out = tmp_path / ".retrai" / "research"
        out.mkdir(parents=True)
        lit = out / "literature_review.md"
        lit.write_text(
            "# Literature Review\n\n"
            "PMID: 12345678\nDOI: 10.1234/test\n"
            "Key findings about KRAS G12C inhibitors from pubmed.\n" * 20
        )

        goal = CancerResearchGoal(topic="KRAS G12C", output_dir=".retrai/research")
        state = _make_state()
        result = await goal.check(state, str(tmp_path))
        assert result.achieved is False
        assert result.details["phases"]["literature_review"] is True
        assert result.details["percentage"] == 20  # 1 of 5 phases

    @pytest.mark.asyncio
    async def test_all_phases_complete(self, tmp_path: Path) -> None:
        out = tmp_path / ".retrai" / "research"
        out.mkdir(parents=True)

        # Phase 1: literature review
        lit = out / "literature_review.md"
        lit.write_text(
            "# Literature Review\n\n"
            "PMID: 12345678\nDOI: 10.1234/test\n"
            "Key findings from pubmed and clinical trials.\n" * 20
        )

        # Phase 2: molecular data
        mol_dir = out / "molecular_data"
        mol_dir.mkdir()
        (mol_dir / "kras_uniprot.json").write_text('{"accession": "P01116"}')

        # Phase 4: model file
        (out / "model_results.json").write_text('{"auc": 0.92}')

        # Phase 5: report
        report = out / "report.md"
        report.write_text(
            "## Abstract\nThis study investigates KRAS G12C.\n\n"
            "## Methods\nWe used ChEMBL and PDB data.\n\n"
            "## Results\nIC50 values were measured.\n\n"
            "## Conclusion\nSotorasib shows promise.\n" * 10
        )

        goal = CancerResearchGoal(topic="KRAS G12C", output_dir=".retrai/research")

        # Mock ExperimentTracker to return 1 experiment (Phase 3)
        with patch(
            "retrai.goals.cancer_research_goal.ExperimentTracker"
        ) as mock_tracker_cls:
            mock_tracker = MagicMock()
            mock_tracker.list_experiments.return_value = [{"id": "exp1"}]
            mock_tracker_cls.return_value = mock_tracker

            state = _make_state(
                tool_results=[
                    {"name": "ml_train", "content": '{"metrics": {"auc": 0.92}}'}
                ]
            )
            result = await goal.check(state, str(tmp_path))

        assert result.achieved is True
        assert result.details["percentage"] == 100

    def test_has_ml_result_from_tool_results(self) -> None:
        goal = CancerResearchGoal()
        state = _make_state(tool_results=[{"name": "ml_train", "content": "{}"}])
        assert goal._has_ml_result(state) is True

    def test_has_ml_result_from_messages(self) -> None:
        goal = CancerResearchGoal()
        msg = MagicMock()
        msg.name = "ml_train"
        msg.content = "{}"
        state = _make_state(messages=[msg])
        assert goal._has_ml_result(state) is True

    def test_has_ml_result_false(self) -> None:
        goal = CancerResearchGoal()
        state = _make_state()
        assert goal._has_ml_result(state) is False


class TestCancerResearchGoalSystemPrompt:
    def test_system_prompt_contains_key_terms(self) -> None:
        goal = CancerResearchGoal(topic="KRAS G12C")
        prompt = goal.system_prompt()
        assert "KRAS G12C" in prompt
        assert "pubmed" in prompt.lower()
        assert "clinicaltrials" in prompt.lower()
        assert "uniprot" in prompt.lower()
        assert "chembl" in prompt.lower()
        assert "pdb" in prompt.lower()
        assert "Phase 1" in prompt
        assert "Phase 5" in prompt

    def test_system_prompt_loads_config(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text("topic: 'TP53 mutations'\noutput_dir: .retrai/cancer\n")
        goal = CancerResearchGoal()
        prompt = goal.system_prompt(str(tmp_path))
        assert "TP53 mutations" in prompt

    def test_system_prompt_custom_prefix(self, tmp_path: Path) -> None:
        config = tmp_path / ".retrai.yml"
        config.write_text(
            "topic: 'BRCA1'\nsystem_prompt: 'Focus on hereditary breast cancer.'\n"
        )
        goal = CancerResearchGoal()
        prompt = goal.system_prompt(str(tmp_path))
        assert "Focus on hereditary breast cancer." in prompt
        assert "BRCA1" in prompt


class TestCancerResearchGoalRegistry:
    def test_registered_in_registry(self) -> None:
        from retrai.goals.registry import get_goal

        goal = get_goal("cancer-research")
        assert isinstance(goal, CancerResearchGoal)
