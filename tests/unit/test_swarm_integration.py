"""Tests for swarm role wiring (decomposer, worker, orchestrator)."""

from __future__ import annotations

import json

from retrai.swarm.decomposer import _parse_subtasks
from retrai.swarm.roles import get_role
from retrai.swarm.types import SubTask


class TestDecomposerRoleParsing:
    """Test that the decomposer parses role fields from LLM responses."""

    def test_parses_role_from_json(self) -> None:
        content = json.dumps([
            {
                "id": "task-1",
                "description": "Search for papers",
                "focus_files": [],
                "strategy_hint": "Use PubMed",
                "role": "researcher",
            },
            {
                "id": "task-2",
                "description": "Analyze data",
                "focus_files": ["data/"],
                "strategy_hint": "Use data_analysis",
                "role": "analyst",
            },
        ])
        subtasks = _parse_subtasks(content)
        assert len(subtasks) == 2
        assert subtasks[0].role == "researcher"
        assert subtasks[1].role == "analyst"

    def test_empty_role_when_not_provided(self) -> None:
        content = json.dumps([
            {
                "id": "task-1",
                "description": "Fix a bug",
                "focus_files": ["src/main.py"],
                "strategy_hint": "Debug it",
            },
        ])
        subtasks = _parse_subtasks(content)
        assert subtasks[0].role == ""

    def test_parses_role_from_markdown_wrapped_json(self) -> None:
        content = '```json\n' + json.dumps([
            {
                "id": "task-1",
                "description": "Review methods",
                "focus_files": [],
                "strategy_hint": "Check methodology",
                "role": "reviewer",
            },
        ]) + '\n```'
        subtasks = _parse_subtasks(content)
        assert subtasks[0].role == "reviewer"


class TestWorkerRoleInjection:
    """Test that role prompts are injected into worker config."""

    def test_role_prompt_built_for_known_role(self) -> None:
        """Verify the role prompt is constructed correctly."""
        role = get_role("analyst")
        assert role is not None
        role_prompt = (
            f"\n\n## YOUR ROLE: {role.name.upper()}\n"
            f"{role.system_prompt}\n"
            f"Preferred tools: {', '.join(role.preferred_tools)}\n"
        )
        assert "YOUR ROLE: ANALYST" in role_prompt
        assert "data_analysis" in role_prompt
        assert "hypothesis_test" in role_prompt

    def test_no_role_prompt_for_unknown_role(self) -> None:
        role = get_role("wizard")
        assert role is None

    def test_subtask_with_role_field(self) -> None:
        st = SubTask(
            id="task-1",
            description="analyze",
            role="analyst",
        )
        assert st.role == "analyst"

    def test_subtask_without_role_defaults_empty(self) -> None:
        st = SubTask(id="task-1", description="work")
        assert st.role == ""


class TestDetectorResearchGoal:
    """Test the detect_research_goal function."""

    def test_detects_research_keywords(self) -> None:
        from retrai.goals.detector import detect_research_goal

        assert detect_research_goal("Research the effects of caffeine")
        assert detect_research_goal("Investigate cancer biomarkers")
        assert detect_research_goal("Run a statistical analysis on the data")
        assert detect_research_goal(
            "Search PubMed for COVID vaccine papers"
        )

    def test_does_not_detect_non_research(self) -> None:
        from retrai.goals.detector import detect_research_goal

        assert not detect_research_goal("Fix the login page CSS")
        assert not detect_research_goal("Add a button to the navbar")
        assert not detect_research_goal("Refactor the database module")


class TestRegistryResearchGoal:
    """Test research goal in the registry."""

    def test_research_goal_in_registry(self) -> None:
        from retrai.goals.registry import get_goal, list_goals

        assert "research" in list_goals()
        goal = get_goal("research")
        assert goal.name == "research"

    def test_get_research_goal_factory(self) -> None:
        from retrai.goals.registry import get_research_goal

        goal = get_research_goal("RNA sequencing")
        assert goal.topic == "RNA sequencing"
        assert goal.name == "research"
