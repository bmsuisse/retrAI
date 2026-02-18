"""Tests for checkpoint save/load round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrai.checkpoint import (
    checkpoint_path,
    list_checkpoints,
    load_checkpoint,
    save_checkpoint,
)


def _make_state(extra: dict | None = None) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    state: dict = {
        "messages": [
            SystemMessage(content="You are a helpful agent."),
            HumanMessage(content="Fix the bug."),
        ],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 3,
        "max_iterations": 50,
        "stop_mode": "soft",
        "hitl_enabled": False,
        "model_name": "claude-sonnet-4-6",
        "cwd": "/tmp/project",
        "run_id": "test-run-abc",
        "total_tokens": 1234,
        "estimated_cost_usd": 0.0025,
        "max_cost_usd": 0.0,
        "failed_strategies": ["strategy_a"],
        "consecutive_failures": 1,
        "tool_cache": {"file_read:{}": "contents"},
        "mop_enabled": False,
        "mop_k": 3,
    }
    if extra:
        state.update(extra)
    return state


class TestCheckpointRoundTrip:
    def test_save_and_load_basic(self, tmp_path: Path) -> None:
        state = _make_state()
        run_id = "run-roundtrip"
        base_dir = str(tmp_path)

        saved_path = save_checkpoint(state, run_id, base_dir=base_dir)
        assert saved_path.exists()

        loaded = load_checkpoint(run_id, base_dir=base_dir)

        # Scalar fields survive round-trip
        assert loaded["iteration"] == 3
        assert loaded["model_name"] == "claude-sonnet-4-6"
        assert loaded["total_tokens"] == 1234
        assert loaded["estimated_cost_usd"] == pytest.approx(0.0025)
        assert loaded["tool_cache"] == {"file_read:{}": "contents"}

    def test_messages_reconstructed(self, tmp_path: Path) -> None:
        from langchain_core.messages import HumanMessage, SystemMessage

        state = _make_state()
        run_id = "run-messages"
        save_checkpoint(state, run_id, base_dir=str(tmp_path))
        loaded = load_checkpoint(run_id, base_dir=str(tmp_path))

        msgs = loaded["messages"]
        assert len(msgs) == 2
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[0].content == "You are a helpful agent."
        assert msgs[1].content == "Fix the bug."

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_checkpoint("does-not-exist", base_dir=str(tmp_path))

    def test_checkpoint_path_helper(self, tmp_path: Path) -> None:
        p = checkpoint_path("my-run", base_dir=str(tmp_path))
        assert p.name == "my-run.json"

    def test_list_checkpoints(self, tmp_path: Path) -> None:
        base_dir = str(tmp_path)
        assert list_checkpoints(base_dir) == []
        save_checkpoint(_make_state(), "run-1", base_dir=base_dir)
        save_checkpoint(_make_state(), "run-2", base_dir=base_dir)
        ids = list_checkpoints(base_dir)
        assert "run-1" in ids
        assert "run-2" in ids

    def test_non_serialisable_value_is_stringified(self, tmp_path: Path) -> None:
        """Values that can't be JSON-encoded are converted to str gracefully."""
        state = _make_state()
        state["some_weird_field"] = object()  # type: ignore[assignment]
        run_id = "run-weird"
        # Should not raise
        save_checkpoint(state, run_id, base_dir=str(tmp_path))
        loaded = load_checkpoint(run_id, base_dir=str(tmp_path))
        assert isinstance(loaded["some_weird_field"], str)
