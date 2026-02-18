"""Experiment tracking — local JSON-backed experiment registry."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXPERIMENTS_DIR = ".retrai/experiments"


@dataclass
class Experiment:
    """A recorded experiment with hypothesis, parameters, and results."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    hypothesis: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    result: str = ""  # "confirmed" | "rejected" | "inconclusive" | "error"
    notes: str = ""
    status: str = "running"  # "running" | "completed" | "failed"
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experiment:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            hypothesis=data.get("hypothesis", ""),
            parameters=data.get("parameters", {}),
            metrics=data.get("metrics", {}),
            result=data.get("result", ""),
            notes=data.get("notes", ""),
            status=data.get("status", "running"),
            tags=data.get("tags", []),
            created_at=data.get("created_at", time.time()),
            completed_at=data.get("completed_at"),
        )


class ExperimentTracker:
    """JSON-backed experiment tracker for a project.

    Each experiment is stored as a separate JSON file in
    `.retrai/experiments/` for easy browsing and version control.
    """

    def __init__(self, cwd: str) -> None:
        self.cwd = Path(cwd).resolve()
        self._dir = self.cwd / EXPERIMENTS_DIR

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def log(self, experiment: Experiment) -> str:
        """Save an experiment. Returns the experiment ID."""
        self._ensure_dir()
        path = self._dir / f"{experiment.id}.json"
        path.write_text(
            json.dumps(experiment.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        return experiment.id

    def get(self, experiment_id: str) -> Experiment | None:
        """Load an experiment by ID."""
        path = self._dir / f"{experiment_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Experiment.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def update(
        self,
        experiment_id: str,
        metrics: dict[str, float] | None = None,
        result: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> bool:
        """Update an existing experiment. Returns True on success."""
        exp = self.get(experiment_id)
        if exp is None:
            return False

        if metrics:
            exp.metrics.update(metrics)
        if result is not None:
            exp.result = result
        if notes is not None:
            exp.notes = notes
        if status is not None:
            exp.status = status
            if status in ("completed", "failed"):
                exp.completed_at = time.time()

        self.log(exp)
        return True

    def list_experiments(
        self,
        tag: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Experiment]:
        """List experiments, optionally filtered by tag/status."""
        if not self._dir.exists():
            return []

        experiments: list[Experiment] = []
        for path in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                exp = Experiment.from_dict(data)

                if tag and tag not in exp.tags:
                    continue
                if status and exp.status != status:
                    continue

                experiments.append(exp)
                if len(experiments) >= limit:
                    break
            except (json.JSONDecodeError, OSError):
                continue

        return experiments

    def compare(self, experiment_ids: list[str]) -> dict[str, Any]:
        """Compare metrics across multiple experiments."""
        experiments = []
        for eid in experiment_ids:
            exp = self.get(eid)
            if exp:
                experiments.append(exp)

        if not experiments:
            return {"error": "No experiments found"}

        # Collect all metric keys
        all_metrics: set[str] = set()
        for exp in experiments:
            all_metrics.update(exp.metrics.keys())

        comparison: dict[str, Any] = {
            "experiments": [],
            "metrics_compared": sorted(all_metrics),
        }

        for exp in experiments:
            comparison["experiments"].append(
                {
                    "id": exp.id,
                    "name": exp.name,
                    "result": exp.result,
                    "metrics": exp.metrics,
                    "parameters": exp.parameters,
                }
            )

        # Find best/worst for each metric
        if len(experiments) > 1:
            rankings: dict[str, dict[str, str]] = {}
            for metric in all_metrics:
                values = [
                    (exp.id, exp.metrics.get(metric, float("nan")))
                    for exp in experiments
                    if metric in exp.metrics
                ]
                if values:
                    best = max(values, key=lambda x: x[1])
                    worst = min(values, key=lambda x: x[1])
                    rankings[metric] = {
                        "best": f"{best[0]} ({best[1]})",
                        "worst": f"{worst[0]} ({worst[1]})",
                    }
            comparison["rankings"] = rankings

        return comparison

    def delete(self, experiment_id: str) -> bool:
        """Delete an experiment by ID."""
        path = self._dir / f"{experiment_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False


async def experiment_log(
    name: str,
    cwd: str,
    hypothesis: str = "",
    parameters: dict[str, Any] | None = None,
    metrics: dict[str, float] | None = None,
    result: str = "",
    notes: str = "",
    tags: list[str] | None = None,
) -> str:
    """Log a new experiment or update an existing one.

    Returns JSON with the experiment details.
    """
    tracker = ExperimentTracker(cwd)
    exp = Experiment(
        name=name,
        hypothesis=hypothesis,
        parameters=parameters or {},
        metrics=metrics or {},
        result=result,
        notes=notes,
        status="completed" if result else "running",
        tags=tags or [],
    )
    if result:
        exp.completed_at = time.time()

    exp_id = tracker.log(exp)
    return json.dumps(
        {
            "experiment_id": exp_id,
            "status": exp.status,
            "experiment": exp.to_dict(),
        },
        indent=2,
        default=str,
    )


async def experiment_list(
    cwd: str,
    tag: str | None = None,
    status: str | None = None,
    compare_ids: list[str] | None = None,
) -> str:
    """List or compare experiments.

    Returns JSON with experiment listing or comparison.
    """
    tracker = ExperimentTracker(cwd)

    if compare_ids:
        comparison = tracker.compare(compare_ids)
        return json.dumps(comparison, indent=2, default=str)

    experiments = tracker.list_experiments(tag=tag, status=status)
    items = []
    for exp in experiments:
        items.append(
            {
                "id": exp.id,
                "name": exp.name,
                "result": exp.result,
                "status": exp.status,
                "metrics": exp.metrics,
                "tags": exp.tags,
                "created_at": exp.created_at,
            }
        )

    return json.dumps(
        {
            "total": len(items),
            "experiments": items,
        },
        indent=2,
        default=str,
    )
