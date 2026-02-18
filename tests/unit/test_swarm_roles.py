"""Unit tests for swarm research roles."""

from __future__ import annotations

from retrai.swarm.roles import (
    RESEARCH_ROLES,
    get_all_roles_info,
    get_role,
    get_role_prompt,
    list_roles,
)


class TestResearchRoles:
    """Tests for research role definitions."""

    def test_four_roles_defined(self) -> None:
        assert len(RESEARCH_ROLES) == 4

    def test_all_roles_have_name(self) -> None:
        for role in RESEARCH_ROLES.values():
            assert role.name
            assert role.description
            assert role.system_prompt
            assert len(role.preferred_tools) > 0

    def test_get_role_existing(self) -> None:
        role = get_role("researcher")
        assert role is not None
        assert role.name == "researcher"

    def test_get_role_case_insensitive(self) -> None:
        role = get_role("Analyst")
        assert role is not None
        assert role.name == "analyst"

    def test_get_role_nonexistent(self) -> None:
        assert get_role("wizard") is None

    def test_list_roles(self) -> None:
        names = list_roles()
        assert "researcher" in names
        assert "analyst" in names
        assert "reviewer" in names
        assert "synthesizer" in names

    def test_get_role_prompt(self) -> None:
        prompt = get_role_prompt("reviewer")
        assert "Peer Reviewer" in prompt

    def test_get_role_prompt_missing(self) -> None:
        assert get_role_prompt("missing") == ""

    def test_get_all_roles_info(self) -> None:
        info = get_all_roles_info()
        assert len(info) == 4
        for item in info:
            assert "name" in item
            assert "description" in item
            assert "preferred_tools" in item

    def test_researcher_has_dataset_fetch(self) -> None:
        role = get_role("researcher")
        assert role is not None
        assert "dataset_fetch" in role.preferred_tools

    def test_analyst_has_hypothesis_test(self) -> None:
        role = get_role("analyst")
        assert role is not None
        assert "hypothesis_test" in role.preferred_tools
