"""Run history persistence — save and load run summaries to disk."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HISTORY_DIR = ".retrai/history"


@dataclass
class RunRecord:
    """A persisted summary of an agent run."""

    run_id: str
    goal: str
    model: str
    status: str  # achieved | failed | aborted
    iterations: int
    max_iterations: int
    total_tokens: int
    estimated_cost_usd: float
    started_at: float
    finished_at: float
    duration_seconds: float
    reason: str
    cwd: str
    files_changed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save_run_history(
    cwd: str,
    run_id: str,
    goal: str,
    model: str,
    status: str,
    iterations: int,
    max_iterations: int,
    total_tokens: int,
    estimated_cost_usd: float,
    started_at: float,
    reason: str,
    files_changed: list[str] | None = None,
) -> Path:
    """Save a run record to .retrai/history/<run_id>.json.

    Returns the path to the saved file.
    """
    finished_at = time.time()
    record = RunRecord(
        run_id=run_id,
        goal=goal,
        model=model,
        status=status,
        iterations=iterations,
        max_iterations=max_iterations,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=round(finished_at - started_at, 2),
        reason=reason,
        cwd=cwd,
        files_changed=files_changed or [],
    )

    history_dir = Path(cwd) / HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)

    out_path = history_dir / f"{run_id}.json"
    out_path.write_text(
        json.dumps(record.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    return out_path


def load_run_history(cwd: str, limit: int = 20) -> list[RunRecord]:
    """Load recent run records from .retrai/history/, newest first."""
    history_dir = Path(cwd) / HISTORY_DIR
    if not history_dir.exists():
        return []

    records: list[RunRecord] = []
    json_files = sorted(history_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    for path in json_files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records.append(RunRecord(**data))
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    return records


def get_run_record(cwd: str, run_id: str) -> RunRecord | None:
    """Load a single run record by ID."""
    path = Path(cwd) / HISTORY_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunRecord(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None
