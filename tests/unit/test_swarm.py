"""Tests for the swarm module — decomposer, orchestrator, and types."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from retrai.swarm.decomposer import _parse_subtasks
from retrai.swarm.types import SubTask, SwarmResult, WorkerResult

# ── SubTask parsing ──────────────────────────────────────────


def test_parse_subtasks_valid_json():
    raw = json.dumps(
        [
            {
                "id": "task-1",
                "description": "Fix the parser",
                "focus_files": ["parser.py"],
                "strategy_hint": "Use regex",
            },
            {
                "id": "task-2",
                "description": "Add tests",
                "focus_files": ["test_parser.py"],
                "strategy_hint": "Cover edge cases",
            },
        ]
    )
    result = _parse_subtasks(raw)
    assert len(result) == 2
    assert result[0].id == "task-1"
    assert result[0].description == "Fix the parser"
    assert result[0].focus_files == ["parser.py"]
    assert result[1].id == "task-2"


def test_parse_subtasks_with_markdown_fences():
    raw = (
        "```json\n"
        + json.dumps(
            [
                {"id": "t1", "description": "Do something"},
            ]
        )
        + "\n```"
    )
    result = _parse_subtasks(raw)
    assert len(result) == 1
    assert result[0].id == "t1"


def test_parse_subtasks_invalid_json():
    result = _parse_subtasks("this is not json at all")
    assert len(result) == 1  # Falls back to single task


def test_parse_subtasks_empty_array():
    result = _parse_subtasks("[]")
    assert len(result) == 1  # Fallback to at least one task


def test_parse_subtasks_single_object():
    raw = json.dumps({"id": "solo", "description": "Only task"})
    result = _parse_subtasks(raw)
    assert len(result) == 1
    assert result[0].id == "solo"


# ── Data types ───────────────────────────────────────────────


def test_subtask_dataclass():
    st = SubTask(id="t1", description="Do X")
    assert st.focus_files == []
    assert st.strategy_hint == ""


def test_worker_result_dataclass():
    wr = WorkerResult(
        task_id="t1",
        description="task",
        status="achieved",
        findings="Fixed it",
        iterations_used=3,
        tokens_used=1500,
    )
    assert wr.cost_usd == 0.0
    assert wr.error is None


def test_swarm_result_dataclass():
    sr = SwarmResult(
        status="partial",
        worker_results=[],
        synthesis="Some workers succeeded",
        total_tokens=5000,
        total_cost=0.05,
        total_iterations=15,
    )
    assert sr.status == "partial"
    assert sr.total_tokens == 5000


# ── Orchestrator logic ───────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_status_all_achieved():
    """When all workers achieve their goals, status should be 'achieved'."""
    from retrai.swarm.orchestrator import SwarmOrchestrator

    subtasks = [
        SubTask(id="t1", description="Task 1"),
        SubTask(id="t2", description="Task 2"),
    ]
    worker_results = [
        WorkerResult(
            task_id="t1",
            description="Task 1",
            status="achieved",
            findings="Done",
            iterations_used=2,
            tokens_used=500,
        ),
        WorkerResult(
            task_id="t2",
            description="Task 2",
            status="achieved",
            findings="Done",
            iterations_used=3,
            tokens_used=700,
        ),
    ]

    orchestrator = SwarmOrchestrator(
        description="Test goal",
        cwd="/tmp",
        model_name="test-model",
    )

    # Mock decompose_goal and run_worker
    with (
        patch("retrai.swarm.orchestrator.decompose_goal", new_callable=AsyncMock) as mock_decompose,
        patch("retrai.swarm.orchestrator.run_worker", new_callable=AsyncMock) as mock_worker,
        patch.object(orchestrator, "_synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_decompose.return_value = subtasks
        mock_worker.side_effect = worker_results
        mock_synth.return_value = "All tasks completed"

        result = await orchestrator.run()

    assert result.status == "achieved"
    assert result.total_tokens == 1200
    assert result.total_iterations == 5


@pytest.mark.asyncio
async def test_orchestrator_status_partial():
    """When some workers fail, status should be 'partial'."""
    from retrai.swarm.orchestrator import SwarmOrchestrator

    subtasks = [
        SubTask(id="t1", description="Task 1"),
        SubTask(id="t2", description="Task 2"),
    ]
    worker_results = [
        WorkerResult(
            task_id="t1",
            description="Task 1",
            status="achieved",
            findings="Done",
            iterations_used=2,
            tokens_used=500,
        ),
        WorkerResult(
            task_id="t2",
            description="Task 2",
            status="failed",
            findings="Could not fix",
            iterations_used=5,
            tokens_used=2000,
        ),
    ]

    orchestrator = SwarmOrchestrator(
        description="Test goal",
        cwd="/tmp",
        model_name="test-model",
    )

    with (
        patch("retrai.swarm.orchestrator.decompose_goal", new_callable=AsyncMock) as mock_decompose,
        patch("retrai.swarm.orchestrator.run_worker", new_callable=AsyncMock) as mock_worker,
        patch.object(orchestrator, "_synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_decompose.return_value = subtasks
        mock_worker.side_effect = worker_results
        mock_synth.return_value = "Partial success"

        result = await orchestrator.run()

    assert result.status == "partial"


@pytest.mark.asyncio
async def test_orchestrator_handles_worker_exceptions():
    """Orchestrator should handle workers that raise exceptions."""
    from retrai.swarm.orchestrator import SwarmOrchestrator

    subtasks = [SubTask(id="t1", description="Failing task")]

    orchestrator = SwarmOrchestrator(
        description="Test goal",
        cwd="/tmp",
        model_name="test-model",
    )

    with (
        patch("retrai.swarm.orchestrator.decompose_goal", new_callable=AsyncMock) as mock_decompose,
        patch("retrai.swarm.orchestrator.run_worker", new_callable=AsyncMock) as mock_worker,
        patch.object(orchestrator, "_synthesize", new_callable=AsyncMock) as mock_synth,
    ):
        mock_decompose.return_value = subtasks
        mock_worker.side_effect = RuntimeError("Worker crashed")
        mock_synth.return_value = "Failed"

        result = await orchestrator.run()

    assert result.status == "failed"
    assert len(result.worker_results) == 1
    assert result.worker_results[0].error == "Worker crashed"
