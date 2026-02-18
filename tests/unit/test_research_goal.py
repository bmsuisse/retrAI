"""Tests for retrai.goals.research_goal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrai.goals.research_goal import ResearchGoal


class TestResearchGoalInit:
    """Test construction and defaults."""

    def test_default_topic_and_output_dir(self) -> None:
        goal = ResearchGoal()
        assert goal.topic == ""
        assert goal.output_dir == ".retrai/research"
        assert goal.name == "research"

    def test_custom_topic(self) -> None:
        goal = ResearchGoal(topic="COVID-19 vaccine efficacy")
        assert goal.topic == "COVID-19 vaccine efficacy"

    def test_custom_output_dir(self) -> None:
        goal = ResearchGoal(output_dir="output/my_research")
        assert goal.output_dir == "output/my_research"


class TestResearchGoalCheck:
    """Test the phase-based progress checking."""

    @pytest.mark.asyncio
    async def test_0_percent_when_empty(self, tmp_path: Path) -> None:
        goal = ResearchGoal(topic="test")
        result = await goal.check({}, str(tmp_path))
        assert not result.achieved
        assert "0%" in result.reason
        assert result.details["percentage"] == 0

    @pytest.mark.asyncio
    async def test_25_percent_with_literature(self, tmp_path: Path) -> None:
        goal = ResearchGoal(topic="test")
        out_dir = tmp_path / ".retrai" / "research"
        out_dir.mkdir(parents=True)
        lit = out_dir / "literature_review.md"
        lit.write_text("# Literature Review\n" + "content " * 50)

        result = await goal.check({}, str(tmp_path))
        assert not result.achieved
        assert "25%" in result.reason
        assert result.details["phases"]["literature_review"] is True

    @pytest.mark.asyncio
    async def test_50_percent_with_literature_and_data(
        self,
        tmp_path: Path,
    ) -> None:
        goal = ResearchGoal(topic="test")
        out_dir = tmp_path / ".retrai" / "research"
        data_dir = out_dir / "data"
        data_dir.mkdir(parents=True)
        (out_dir / "literature_review.md").write_text("x" * 200)
        (data_dir / "sample.csv").write_text("a,b\n1,2\n")

        result = await goal.check({}, str(tmp_path))
        assert not result.achieved
        assert "50%" in result.reason
        assert result.details["phases"]["data_collection"] is True

    @pytest.mark.asyncio
    async def test_75_percent_with_experiment(
        self,
        tmp_path: Path,
    ) -> None:
        goal = ResearchGoal(topic="test")
        out_dir = tmp_path / ".retrai" / "research"
        data_dir = out_dir / "data"
        data_dir.mkdir(parents=True)
        (out_dir / "literature_review.md").write_text("x" * 200)
        (data_dir / "sample.csv").write_text("a,b\n1,2\n")

        # Create a fake experiment
        exp_dir = tmp_path / ".retrai" / "experiments"
        exp_dir.mkdir(parents=True)
        exp_file = exp_dir / "exp-001.json"
        exp_file.write_text(
            json.dumps(
                {
                    "id": "exp-001",
                    "name": "test",
                    "hypothesis": "h",
                    "parameters": {},
                    "metrics": {},
                    "result": "ok",
                    "tags": [],
                    "notes": "",
                    "created_at": "2026-01-01T00:00:00",
                }
            )
        )

        result = await goal.check({}, str(tmp_path))
        assert not result.achieved
        assert "75%" in result.reason
        assert result.details["phases"]["analysis"] is True

    @pytest.mark.asyncio
    async def test_100_percent_all_phases(self, tmp_path: Path) -> None:
        goal = ResearchGoal(topic="test")
        out_dir = tmp_path / ".retrai" / "research"
        data_dir = out_dir / "data"
        data_dir.mkdir(parents=True)
        (out_dir / "literature_review.md").write_text("x" * 200)
        (data_dir / "sample.csv").write_text("a,b\n1,2\n")
        (out_dir / "report.md").write_text("# Report\n" + "y" * 300)

        # Experiment
        exp_dir = tmp_path / ".retrai" / "experiments"
        exp_dir.mkdir(parents=True)
        (exp_dir / "exp-001.json").write_text(
            json.dumps(
                {
                    "id": "exp-001",
                    "name": "t",
                    "hypothesis": "",
                    "parameters": {},
                    "metrics": {},
                    "result": "",
                    "tags": [],
                    "notes": "",
                    "created_at": "2026-01-01",
                }
            )
        )

        result = await goal.check({}, str(tmp_path))
        assert result.achieved
        assert "100%" in result.reason
        assert result.details["percentage"] == 100

    @pytest.mark.asyncio
    async def test_next_phase_identified(self, tmp_path: Path) -> None:
        goal = ResearchGoal(topic="test")
        result = await goal.check({}, str(tmp_path))
        assert result.details["next_phase"] == "literature_review"


class TestResearchGoalSystemPrompt:
    """Test system prompt generation."""

    def test_contains_topic(self) -> None:
        goal = ResearchGoal(topic="RNA sequencing")
        prompt = goal.system_prompt()
        assert "RNA sequencing" in prompt

    def test_contains_phases(self) -> None:
        goal = ResearchGoal(topic="test")
        prompt = goal.system_prompt()
        assert "Phase 1" in prompt
        assert "Phase 2" in prompt
        assert "Phase 3" in prompt
        assert "Phase 4" in prompt

    def test_mentions_tools(self) -> None:
        goal = ResearchGoal(topic="test")
        prompt = goal.system_prompt()
        assert "dataset_fetch" in prompt
        assert "data_analysis" in prompt
        assert "hypothesis_test" in prompt
        assert "experiment_log" in prompt
        assert "visualize" in prompt

    def test_default_topic_string(self) -> None:
        goal = ResearchGoal()
        prompt = goal.system_prompt()
        assert "the given topic" in prompt

    def test_contains_output_dir(self) -> None:
        goal = ResearchGoal(output_dir="my_output")
        prompt = goal.system_prompt()
        assert "my_output" in prompt
