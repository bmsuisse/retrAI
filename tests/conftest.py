"""Shared fixtures for the retrAI test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from retrai.config import RunConfig
from retrai.events.bus import AsyncEventBus
from retrai.events.types import AgentEvent


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Return a temporary directory that looks like a minimal Python project."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'testpkg'\nversion = '0.1.0'\n")
    return tmp_path


@pytest.fixture
def passing_project(tmp_project: Path) -> Path:
    """A project where all tests already pass."""
    (tmp_project / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_project / "tests" / "test_calc.py").write_text(
        "from src.calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    return tmp_project


@pytest.fixture
def failing_project(tmp_project: Path) -> Path:
    """A project with one failing test."""
    (tmp_project / "src" / "calc.py").write_text(
        "def add(a, b):\n    return a - b  # bug: should be +\n"
    )
    (tmp_project / "tests" / "test_calc.py").write_text(
        "from src.calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    return tmp_project


@pytest.fixture
def run_config(tmp_project: Path) -> RunConfig:
    return RunConfig(goal="pytest", cwd=str(tmp_project))


@pytest.fixture
async def event_bus() -> AsyncGenerator[AsyncEventBus, None]:
    bus = AsyncEventBus()
    yield bus
    await bus.close()


@pytest.fixture
def sample_event() -> AgentEvent:
    return AgentEvent(
        kind="tool_call",
        run_id="test-run-1",
        iteration=1,
        payload={"tool": "bash_exec", "args": {"command": "ls"}},
        ts=1_700_000_000.0,
    )
