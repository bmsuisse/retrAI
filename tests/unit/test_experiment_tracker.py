"""Unit tests for experiment tracking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrai.experiment.tracker import (
    Experiment,
    ExperimentTracker,
    experiment_list,
    experiment_log,
)


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    """Create a tracker backed by a temp directory."""
    return ExperimentTracker(str(tmp_path))


class TestExperiment:
    """Tests for the Experiment dataclass."""

    def test_to_dict_round_trip(self) -> None:
        exp = Experiment(
            name="test_exp",
            hypothesis="H1: x > y",
            parameters={"lr": 0.01},
            metrics={"accuracy": 0.95},
            result="confirmed",
            tags=["ml"],
        )
        d = exp.to_dict()
        restored = Experiment.from_dict(d)
        assert restored.name == "test_exp"
        assert restored.hypothesis == "H1: x > y"
        assert restored.parameters == {"lr": 0.01}
        assert restored.metrics == {"accuracy": 0.95}
        assert restored.result == "confirmed"
        assert restored.tags == ["ml"]

    def test_from_dict_defaults(self) -> None:
        exp = Experiment.from_dict({})
        assert exp.name == ""
        assert exp.status == "running"
        assert exp.parameters == {}


class TestExperimentTracker:
    """Tests for ExperimentTracker."""

    def test_log_and_get(self, tracker: ExperimentTracker) -> None:
        exp = Experiment(name="exp1", hypothesis="test")
        exp_id = tracker.log(exp)
        loaded = tracker.get(exp_id)
        assert loaded is not None
        assert loaded.name == "exp1"

    def test_get_nonexistent(self, tracker: ExperimentTracker) -> None:
        assert tracker.get("nonexistent") is None

    def test_update(self, tracker: ExperimentTracker) -> None:
        exp = Experiment(name="exp2")
        exp_id = tracker.log(exp)

        success = tracker.update(
            exp_id,
            metrics={"f1": 0.88},
            result="confirmed",
            status="completed",
        )
        assert success

        updated = tracker.get(exp_id)
        assert updated is not None
        assert updated.metrics == {"f1": 0.88}
        assert updated.result == "confirmed"
        assert updated.status == "completed"
        assert updated.completed_at is not None

    def test_update_nonexistent(self, tracker: ExperimentTracker) -> None:
        assert not tracker.update("nope", metrics={"x": 1.0})

    def test_list_experiments(self, tracker: ExperimentTracker) -> None:
        tracker.log(Experiment(name="a", tags=["ml"]))
        tracker.log(Experiment(name="b", tags=["stats"]))
        tracker.log(Experiment(name="c", tags=["ml"]))

        all_exps = tracker.list_experiments()
        assert len(all_exps) == 3

        ml_exps = tracker.list_experiments(tag="ml")
        assert len(ml_exps) == 2

    def test_compare(self, tracker: ExperimentTracker) -> None:
        e1 = Experiment(name="a", metrics={"acc": 0.9})
        e2 = Experiment(name="b", metrics={"acc": 0.95})
        id1 = tracker.log(e1)
        id2 = tracker.log(e2)

        comparison = tracker.compare([id1, id2])
        assert "experiments" in comparison
        assert len(comparison["experiments"]) == 2
        assert "rankings" in comparison

    def test_delete(self, tracker: ExperimentTracker) -> None:
        exp = Experiment(name="del_me")
        exp_id = tracker.log(exp)
        assert tracker.delete(exp_id)
        assert tracker.get(exp_id) is None
        assert not tracker.delete(exp_id)  # already deleted


class TestExperimentTools:
    """Tests for the tool-facing async functions."""

    @pytest.mark.asyncio
    async def test_experiment_log(self, tmp_path: Path) -> None:
        result = await experiment_log(
            name="test_run",
            cwd=str(tmp_path),
            hypothesis="X correlates with Y",
            parameters={"alpha": 0.05},
            metrics={"r": 0.72},
            result="confirmed",
            tags=["stats"],
        )
        data = json.loads(result)
        assert "experiment_id" in data
        assert data["status"] == "completed"
        assert data["experiment"]["name"] == "test_run"

    @pytest.mark.asyncio
    async def test_experiment_list(self, tmp_path: Path) -> None:
        await experiment_log(name="run1", cwd=str(tmp_path), result="confirmed")
        await experiment_log(name="run2", cwd=str(tmp_path), result="rejected")

        result = await experiment_list(cwd=str(tmp_path))
        data = json.loads(result)
        assert data["total"] == 2
