"""Tests for run history persistence."""

from __future__ import annotations

import time
from pathlib import Path

from retrai.history import (
    RunRecord,
    get_run_record,
    load_run_history,
    save_run_history,
)


def test_save_and_load_run_history(tmp_path: Path):
    """Save a run record and verify it loads back correctly."""
    started = time.time() - 10  # pretend run started 10s ago

    path = save_run_history(
        cwd=str(tmp_path),
        run_id="test-run-001",
        goal="pytest",
        model="claude-sonnet-4-6",
        status="achieved",
        iterations=3,
        max_iterations=20,
        total_tokens=5000,
        estimated_cost_usd=0.0123,
        started_at=started,
        reason="All tests passed",
    )

    assert path.exists()
    assert path.suffix == ".json"

    # Load back
    records = load_run_history(str(tmp_path))
    assert len(records) == 1
    r = records[0]
    assert r.run_id == "test-run-001"
    assert r.goal == "pytest"
    assert r.model == "claude-sonnet-4-6"
    assert r.status == "achieved"
    assert r.iterations == 3
    assert r.total_tokens == 5000
    assert r.estimated_cost_usd == 0.0123
    assert r.duration_seconds > 0
    assert r.reason == "All tests passed"


def test_load_empty_history(tmp_path: Path):
    """Loading from a directory with no history returns empty list."""
    records = load_run_history(str(tmp_path))
    assert records == []


def test_get_run_record(tmp_path: Path):
    """Get a specific run record by ID."""
    save_run_history(
        cwd=str(tmp_path),
        run_id="abc-123",
        goal="pyright",
        model="gpt-4o",
        status="failed",
        iterations=5,
        max_iterations=10,
        total_tokens=8000,
        estimated_cost_usd=0.05,
        started_at=time.time() - 5,
        reason="Type errors remain",
    )

    record = get_run_record(str(tmp_path), "abc-123")
    assert record is not None
    assert record.run_id == "abc-123"
    assert record.status == "failed"


def test_get_run_record_not_found(tmp_path: Path):
    """Getting a non-existent run returns None."""
    result = get_run_record(str(tmp_path), "nonexistent")
    assert result is None


def test_multiple_runs_sorted_by_time(tmp_path: Path):
    """Multiple runs are returned sorted by time, newest first."""
    for i in range(5):
        save_run_history(
            cwd=str(tmp_path),
            run_id=f"run-{i}",
            goal="pytest",
            model="claude-sonnet-4-6",
            status="achieved" if i % 2 == 0 else "failed",
            iterations=i + 1,
            max_iterations=20,
            total_tokens=1000 * (i + 1),
            estimated_cost_usd=0.01 * (i + 1),
            started_at=time.time() - (5 - i),  # Earlier runs first
            reason=f"Run {i}",
        )
        time.sleep(0.01)  # Ensure different mtime

    records = load_run_history(str(tmp_path))
    assert len(records) == 5
    # Newest first
    assert records[0].run_id == "run-4"


def test_load_with_limit(tmp_path: Path):
    """Limit parameter caps the number of returned records."""
    for i in range(10):
        save_run_history(
            cwd=str(tmp_path),
            run_id=f"run-{i}",
            goal="pytest",
            model="gpt-4o",
            status="achieved",
            iterations=1,
            max_iterations=20,
            total_tokens=100,
            estimated_cost_usd=0.001,
            started_at=time.time(),
            reason="ok",
        )
        time.sleep(0.01)

    records = load_run_history(str(tmp_path), limit=3)
    assert len(records) == 3


def test_run_record_to_dict():
    """RunRecord.to_dict() returns a proper dict."""
    r = RunRecord(
        run_id="test",
        goal="pytest",
        model="gpt-4o",
        status="achieved",
        iterations=1,
        max_iterations=10,
        total_tokens=500,
        estimated_cost_usd=0.005,
        started_at=1000.0,
        finished_at=1010.0,
        duration_seconds=10.0,
        reason="done",
        cwd="/tmp/proj",
    )
    d = r.to_dict()
    assert isinstance(d, dict)
    assert d["run_id"] == "test"
    assert d["estimated_cost_usd"] == 0.005


def test_files_changed_tracking(tmp_path: Path):
    """Files changed list is saved and loaded correctly."""
    save_run_history(
        cwd=str(tmp_path),
        run_id="with-files",
        goal="pytest",
        model="gpt-4o",
        status="achieved",
        iterations=2,
        max_iterations=10,
        total_tokens=1500,
        estimated_cost_usd=0.01,
        started_at=time.time(),
        reason="All good",
        files_changed=["src/main.py", "tests/test_main.py"],
    )

    record = get_run_record(str(tmp_path), "with-files")
    assert record is not None
    assert record.files_changed == ["src/main.py", "tests/test_main.py"]
