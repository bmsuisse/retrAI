"""Tests for the RunManager registry."""

from __future__ import annotations

import pytest

from retrai.config import RunConfig
from retrai.server.run_manager import RunManager


@pytest.fixture
def manager() -> RunManager:
    return RunManager()


@pytest.fixture
def cfg() -> RunConfig:
    return RunConfig(goal="pytest", cwd="/tmp")


def test_create_returns_entry(manager: RunManager, cfg: RunConfig):
    entry = manager.create(cfg)
    assert entry.run_id == cfg.run_id
    assert entry.status == "pending"
    assert entry.config is cfg


def test_get_existing_run(manager: RunManager, cfg: RunConfig):
    entry = manager.create(cfg)
    found = manager.get(cfg.run_id)
    assert found is entry


def test_get_missing_run_returns_none(manager: RunManager):
    assert manager.get("nonexistent-id") is None


def test_get_or_raise_existing(manager: RunManager, cfg: RunConfig):
    entry = manager.create(cfg)
    assert manager.get_or_raise(cfg.run_id) is entry


def test_get_or_raise_missing(manager: RunManager):
    with pytest.raises(KeyError, match="Run not found"):
        manager.get_or_raise("nonexistent")


def test_list_runs_empty(manager: RunManager):
    assert manager.list_runs() == []


def test_list_runs_after_creates(manager: RunManager):
    cfg1 = RunConfig(goal="pytest", cwd="/tmp")
    cfg2 = RunConfig(goal="shell-goal", cwd="/tmp")
    manager.create(cfg1)
    manager.create(cfg2)
    runs = manager.list_runs()
    assert len(runs) == 2
    run_ids = {r.run_id for r in runs}
    assert cfg1.run_id in run_ids
    assert cfg2.run_id in run_ids


def test_run_has_event_bus(manager: RunManager, cfg: RunConfig):
    from retrai.events.bus import AsyncEventBus

    entry = manager.create(cfg)
    assert isinstance(entry.bus, AsyncEventBus)


def test_initial_status_is_pending(manager: RunManager, cfg: RunConfig):
    entry = manager.create(cfg)
    assert entry.status == "pending"
