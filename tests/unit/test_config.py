"""Tests for RunConfig."""

from __future__ import annotations

import uuid
from pathlib import Path

from retrai.config import RunConfig


def test_default_values():
    cfg = RunConfig(goal="pytest")
    assert cfg.goal == "pytest"
    assert cfg.model_name == "claude-sonnet-4-6"
    assert cfg.max_iterations == 50
    assert cfg.hitl_enabled is False
    assert cfg.run_id  # non-empty
    assert Path(cfg.cwd).is_absolute()


def test_run_id_is_valid_uuid():
    cfg = RunConfig(goal="pytest")
    parsed = uuid.UUID(cfg.run_id)
    assert str(parsed) == cfg.run_id


def test_two_configs_have_different_run_ids():
    a = RunConfig(goal="pytest")
    b = RunConfig(goal="pytest")
    assert a.run_id != b.run_id


def test_explicit_run_id_is_preserved():
    cfg = RunConfig(goal="pytest", run_id="my-custom-id")
    assert cfg.run_id == "my-custom-id"


def test_cwd_is_resolved_to_absolute(tmp_path: Path):
    cfg = RunConfig(goal="pytest", cwd=str(tmp_path))
    assert Path(cfg.cwd).is_absolute()
    assert cfg.cwd == str(tmp_path.resolve())


def test_custom_model():
    cfg = RunConfig(goal="pytest", model_name="gpt-4o")
    assert cfg.model_name == "gpt-4o"


def test_max_iterations_respected():
    cfg = RunConfig(goal="pytest", max_iterations=5)
    assert cfg.max_iterations == 5
