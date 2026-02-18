"""Unit tests for ScoreGoal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from retrai.goals.score_goal import ScoreGoal

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
async def test_missing_task_config(tmp_path: Path) -> None:
    """No task in config → achieved=False immediately."""
    _write_config(tmp_path, {"goal": "score", "output_file": "out.md"})
    goal = ScoreGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "task" in result.reason.lower()


@pytest.mark.asyncio
async def test_output_file_not_yet_created(tmp_path: Path) -> None:
    """Output file missing → achieved=False with helpful message."""
    _write_config(
        tmp_path,
        {"goal": "score", "task": "Summarise the paper.", "output_file": "summary.md"},
    )
    goal = ScoreGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "summary.md" in result.reason or "output" in result.reason.lower()


@pytest.mark.asyncio
async def test_empty_output_file(tmp_path: Path) -> None:
    """Output file exists but is empty → achieved=False."""
    _write_config(
        tmp_path,
        {"goal": "score", "task": "Summarise the paper.", "output_file": "summary.md"},
    )
    _write_file(tmp_path, "summary.md", "   ")
    goal = ScoreGoal()
    result = await goal.check({}, str(tmp_path))
    assert not result.achieved
    assert "empty" in result.reason.lower()


@pytest.mark.asyncio
async def test_llm_judge_failure_is_graceful(tmp_path: Path) -> None:
    """LLM judge fails → achieved=False, no exception propagated."""
    _write_config(
        tmp_path,
        {"goal": "score", "task": "Summarise the paper.", "output_file": "summary.md"},
    )
    _write_file(tmp_path, "summary.md", "This paper discusses AI safety.")

    with patch(
        "retrai.goals.score_goal._llm_score",
        new=AsyncMock(return_value=(None, "timeout")),
    ):
        goal = ScoreGoal()
        result = await goal.check({}, str(tmp_path))

    assert not result.achieved
    assert "judge" in result.reason.lower() or "failed" in result.reason.lower()


@pytest.mark.asyncio
async def test_score_below_target(tmp_path: Path) -> None:
    """Score 5.0 with target 8 → achieved=False, gap in details."""
    _write_config(
        tmp_path,
        {
            "goal": "score",
            "task": "Summarise the paper.",
            "output_file": "summary.md",
            "target_score": 8,
            "rubric": "Score on accuracy and brevity.",
        },
    )
    _write_file(tmp_path, "summary.md", "The paper is about things.")

    with patch(
        "retrai.goals.score_goal._llm_score",
        new=AsyncMock(return_value=(5.0, "Too vague, missing key findings.")),
    ):
        goal = ScoreGoal()
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
        {
            "goal": "score",
            "task": "Summarise the paper.",
            "output_file": "summary.md",
            "target_score": 8,
        },
    )
    _write_file(tmp_path, "summary.md", "A concise and accurate summary.")

    with patch(
        "retrai.goals.score_goal._llm_score",
        new=AsyncMock(return_value=(8.5, "Accurate, concise, well-structured.")),
    ):
        goal = ScoreGoal()
        result = await goal.check({}, str(tmp_path))

    assert result.achieved
    assert result.details["score"] == 8.5
    assert "✅" in result.reason


@pytest.mark.asyncio
async def test_input_file_loaded_as_context(tmp_path: Path) -> None:
    """When input_file exists, its content is passed to the LLM judge."""
    _write_config(
        tmp_path,
        {
            "goal": "score",
            "task": "Summarise the paper.",
            "input_file": "paper.md",
            "output_file": "summary.md",
            "target_score": 7,
        },
    )
    _write_file(tmp_path, "paper.md", "This is the original research paper content.")
    _write_file(tmp_path, "summary.md", "A summary of the paper.")

    captured_kwargs: list[dict] = []

    async def fake_score(**kwargs):  # type: ignore
        captured_kwargs.append(kwargs)
        return (7.5, "Good summary.")

    with patch("retrai.goals.score_goal._llm_score", new=fake_score):
        goal = ScoreGoal()
        result = await goal.check({}, str(tmp_path))

    assert result.achieved
    assert captured_kwargs[0]["input_text"] != ""
    assert "paper" in captured_kwargs[0]["input_text"].lower()


@pytest.mark.asyncio
async def test_missing_input_file_is_ok(tmp_path: Path) -> None:
    """input_file specified but missing → still runs (judge gets empty context)."""
    _write_config(
        tmp_path,
        {
            "goal": "score",
            "task": "Summarise the paper.",
            "input_file": "missing.md",
            "output_file": "summary.md",
            "target_score": 7,
        },
    )
    _write_file(tmp_path, "summary.md", "A summary without the original.")

    with patch(
        "retrai.goals.score_goal._llm_score",
        new=AsyncMock(return_value=(7.0, "Acceptable.")),
    ):
        goal = ScoreGoal()
        result = await goal.check({}, str(tmp_path))

    assert result.achieved


def test_system_prompt_contains_key_info(tmp_path: Path) -> None:
    """system_prompt() mentions the task, output file, target score, and rubric."""
    _write_config(
        tmp_path,
        {
            "goal": "score",
            "task": "Write an executive summary.",
            "output_file": "exec_summary.md",
            "target_score": 9,
            "rubric": "Score on accuracy, brevity, and clarity.",
        },
    )
    goal = ScoreGoal()
    prompt = goal.system_prompt(str(tmp_path))
    assert "exec_summary.md" in prompt
    assert "9" in prompt
    assert "accuracy" in prompt
    assert "brevity" in prompt
