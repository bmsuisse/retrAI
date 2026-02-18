"""Unit tests for TextImproveGoal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from retrai.goals.text_improve_goal import TextImproveGoal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, content: dict) -> None:
    import yaml
    (tmp_path / ".retrai.yml").write_text(yaml.dump(content))


def _write_file(tmp_path: Path, name: str, text: str) -> None:
    (tmp_path / name).write_text(text)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_input_file_config(tmp_path: Path) -> None:
    """No input_file in config → achieved=False immediately."""
    _write_config(tmp_path, {"goal": "text-improve", "target_score": 8})
    goal = TextImproveGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "input_file" in result.reason.lower() or "no input" in result.reason.lower()


@pytest.mark.asyncio
async def test_file_not_found(tmp_path: Path) -> None:
    """input_file specified but file missing → achieved=False."""
    _write_config(tmp_path, {"goal": "text-improve", "input_file": "draft.md"})
    goal = TextImproveGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "not found" in result.reason.lower() or "draft.md" in result.reason


@pytest.mark.asyncio
async def test_empty_file(tmp_path: Path) -> None:
    """File exists but is empty → achieved=False."""
    _write_config(tmp_path, {"goal": "text-improve", "input_file": "draft.md"})
    _write_file(tmp_path, "draft.md", "   \n  ")
    goal = TextImproveGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "empty" in result.reason.lower()


@pytest.mark.asyncio
async def test_llm_judge_failure_is_graceful(tmp_path: Path) -> None:
    """LLM judge raises → achieved=False, no exception propagated."""
    _write_config(tmp_path, {"goal": "text-improve", "input_file": "draft.md"})
    _write_file(tmp_path, "draft.md", "Some text content here.")

    with patch(
        "retrai.goals.text_improve_goal._llm_score",
        new=AsyncMock(return_value=(None, "LLM timeout")),
    ):
        goal = TextImproveGoal()
        result = await goal.check({}, str(tmp_path))

    assert not result.achieved
    assert "judge" in result.reason.lower() or "failed" in result.reason.lower()


@pytest.mark.asyncio
async def test_score_below_target(tmp_path: Path) -> None:
    """Score 5.0 with target 8 → achieved=False, gap in details."""
    _write_config(
        tmp_path,
        {"goal": "text-improve", "input_file": "draft.md", "target_score": 8},
    )
    _write_file(tmp_path, "draft.md", "Some text content here.")

    with patch(
        "retrai.goals.text_improve_goal._llm_score",
        new=AsyncMock(return_value=(5.0, "Needs more clarity.")),
    ):
        goal = TextImproveGoal()
        result = await goal.check({}, str(tmp_path))

    assert not result.achieved
    assert result.details["score"] == 5.0
    assert result.details["gap"] == pytest.approx(3.0)
    assert "5.0" in result.reason


@pytest.mark.asyncio
async def test_score_meets_target(tmp_path: Path) -> None:
    """Score 8.5 with target 8 → achieved=True."""
    _write_config(
        tmp_path,
        {"goal": "text-improve", "input_file": "draft.md", "target_score": 8},
    )
    _write_file(tmp_path, "draft.md", "Excellent text content here.")

    with patch(
        "retrai.goals.text_improve_goal._llm_score",
        new=AsyncMock(return_value=(8.5, "Well written and clear.")),
    ):
        goal = TextImproveGoal()
        result = await goal.check({}, str(tmp_path))

    assert result.achieved
    assert result.details["score"] == 8.5
    assert "✅" in result.reason


@pytest.mark.asyncio
async def test_output_file_preferred_over_input(tmp_path: Path) -> None:
    """When output_file exists, it is scored instead of input_file."""
    _write_config(
        tmp_path,
        {
            "goal": "text-improve",
            "input_file": "draft.md",
            "output_file": "improved.md",
            "target_score": 7,
        },
    )
    _write_file(tmp_path, "draft.md", "Original draft.")
    _write_file(tmp_path, "improved.md", "Much improved version of the text.")

    captured: list[str] = []

    async def fake_score(text: str, criteria: list, model_name: str):  # type: ignore
        captured.append(text)
        return (7.5, "Good improvement.")

    with patch("retrai.goals.text_improve_goal._llm_score", new=fake_score):
        goal = TextImproveGoal()
        result = await goal.check({}, str(tmp_path))

    assert result.achieved
    assert "improved" in captured[0].lower()


def test_system_prompt_contains_key_info(tmp_path: Path) -> None:
    """system_prompt() mentions the input file, target score, and strategy."""
    _write_config(
        tmp_path,
        {
            "goal": "text-improve",
            "input_file": "draft.md",
            "target_score": 9,
            "criteria": ["clarity", "persuasiveness"],
        },
    )
    goal = TextImproveGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "draft.md" in prompt
    assert "9" in prompt
    assert "clarity" in prompt
    assert "persuasiveness" in prompt
