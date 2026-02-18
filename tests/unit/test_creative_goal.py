"""Unit tests for CreativeGoal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from retrai.goals.creative_goal import CreativeGoal

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
async def test_missing_prompt_config(tmp_path: Path) -> None:
    """No prompt in config → achieved=False immediately."""
    _write_config(tmp_path, {"goal": "creative", "output_file": "story.md"})
    goal = CreativeGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "prompt" in result.reason.lower()


@pytest.mark.asyncio
async def test_output_file_not_yet_created(tmp_path: Path) -> None:
    """Output file missing → achieved=False with helpful message."""
    _write_config(
        tmp_path,
        {"goal": "creative", "prompt": "Write a haiku.", "output_file": "haiku.md"},
    )
    goal = CreativeGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "haiku.md" in result.reason or "output" in result.reason.lower()


@pytest.mark.asyncio
async def test_empty_output_file(tmp_path: Path) -> None:
    """Output file exists but is empty → achieved=False."""
    _write_config(
        tmp_path,
        {"goal": "creative", "prompt": "Write a haiku.", "output_file": "haiku.md"},
    )
    _write_file(tmp_path, "haiku.md", "")
    goal = CreativeGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "empty" in result.reason.lower()


@pytest.mark.asyncio
async def test_llm_judge_failure_is_graceful(tmp_path: Path) -> None:
    """LLM judge fails → achieved=False, no exception propagated."""
    _write_config(
        tmp_path,
        {"goal": "creative", "prompt": "Write a haiku.", "output_file": "haiku.md"},
    )
    _write_file(tmp_path, "haiku.md", "Old pond / A frog jumps in / Sound of water")

    with patch(
        "retrai.goals.creative_goal._llm_score_creative",
        new=AsyncMock(return_value=(None, "API error")),
    ):
        goal = CreativeGoal()
        result = await goal.check({}, str(tmp_path))

    assert not result.achieved
    assert "judge" in result.reason.lower() or "failed" in result.reason.lower()


@pytest.mark.asyncio
async def test_score_below_target(tmp_path: Path) -> None:
    """Score 4.0 with target 8 → achieved=False, gap in details."""
    _write_config(
        tmp_path,
        {
            "goal": "creative",
            "prompt": "Write a short story.",
            "output_file": "story.md",
            "target_score": 8,
        },
    )
    _write_file(tmp_path, "story.md", "Once upon a time there was a robot.")

    with patch(
        "retrai.goals.creative_goal._llm_score_creative",
        new=AsyncMock(return_value=(4.0, "Lacks depth and originality.")),
    ):
        goal = CreativeGoal()
        result = await goal.check({}, str(tmp_path))

    assert not result.achieved
    assert result.details["score"] == 4.0
    assert result.details["gap"] == pytest.approx(4.0)
    assert "4.0" in result.reason


@pytest.mark.asyncio
async def test_score_meets_target(tmp_path: Path) -> None:
    """Score 9.0 with target 8 → achieved=True."""
    _write_config(
        tmp_path,
        {
            "goal": "creative",
            "prompt": "Write a short story.",
            "output_file": "story.md",
            "target_score": 8,
        },
    )
    _write_file(tmp_path, "story.md", "A beautifully crafted story about time.")

    with patch(
        "retrai.goals.creative_goal._llm_score_creative",
        new=AsyncMock(return_value=(9.0, "Excellent voice and structure.")),
    ):
        goal = CreativeGoal()
        result = await goal.check({}, str(tmp_path))

    assert result.achieved
    assert result.details["score"] == 9.0
    assert "✅" in result.reason


def test_system_prompt_contains_key_info(tmp_path: Path) -> None:
    """system_prompt() mentions the brief, output file, and target score."""
    _write_config(
        tmp_path,
        {
            "goal": "creative",
            "prompt": "Write a poem about the sea.",
            "output_file": "poem.md",
            "target_score": 9,
            "style": "melancholic",
            "max_words": 200,
        },
    )
    goal = CreativeGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "poem.md" in prompt
    assert "9" in prompt
    assert "melancholic" in prompt
    assert "200" in prompt
