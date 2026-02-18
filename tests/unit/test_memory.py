"""Tests for the Memory store (mem0 + local Qdrant backend)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from retrai.memory.store import Memory, MemoryStore, MEMORY_USER_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mem0_item(
    insight: str,
    category: str = "tip",
    score: float = 1.0,
    run_id: str = "",
) -> dict[str, Any]:
    """Build a fake mem0 result dict."""
    return {
        "memory": insight,
        "score": score,
        "metadata": {
            "category": category,
            "timestamp": time.time(),
            "run_id": run_id,
            "relevance_score": score,
        },
    }


@pytest.fixture()
def mock_mem0_client() -> MagicMock:
    """A MagicMock that mimics the mem0.Memory client."""
    client = MagicMock()
    client.get_all.return_value = {"results": []}
    client.search.return_value = {"results": []}
    return client


@pytest.fixture()
def store(tmp_path: Any, mock_mem0_client: MagicMock) -> MemoryStore:
    """MemoryStore with a mocked mem0 client (no real API calls)."""
    with patch("retrai.memory.store.MemoryStore._init_client", return_value=mock_mem0_client):
        s = MemoryStore(str(tmp_path))
        s._client = mock_mem0_client
        return s


# ---------------------------------------------------------------------------
# Memory dataclass
# ---------------------------------------------------------------------------


class TestMemory:
    def test_defaults(self) -> None:
        m = Memory(insight="Tests need DB", category="project_fact")
        assert m.insight == "Tests need DB"
        assert m.category == "project_fact"
        assert m.relevance_score == 1.0
        assert m.timestamp > 0

    def test_round_trip(self) -> None:
        m = Memory(
            insight="Use file_patch",
            category="strategy",
            run_id="abc",
            relevance_score=0.8,
        )
        d = m.to_dict()
        m2 = Memory.from_dict(d)
        assert m2.insight == m.insight
        assert m2.category == m.category
        assert m2.run_id == m.run_id
        assert m2.relevance_score == m.relevance_score

    def test_from_mem0(self) -> None:
        item = _make_mem0_item("insight text", category="strategy", score=0.9, run_id="r1")
        m = Memory.from_mem0(item)
        assert m.insight == "insight text"
        assert m.category == "strategy"
        assert m.relevance_score == 0.9
        assert m.run_id == "r1"

    def test_from_mem0_fallback_text_key(self) -> None:
        """from_mem0 should also work when key is 'text' instead of 'memory'."""
        item = {"text": "fallback text", "score": 0.5, "metadata": {}}
        m = Memory.from_mem0(item)
        assert m.insight == "fallback text"


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class TestMemoryStore:
    def test_add_calls_client(self, store: MemoryStore, mock_mem0_client: MagicMock) -> None:
        m = Memory(insight="Test insight", category="tip")
        store.add(m)
        mock_mem0_client.add.assert_called_once()
        call_args = mock_mem0_client.add.call_args
        assert call_args[0][0] == "Test insight"
        assert call_args[1]["user_id"] == MEMORY_USER_ID
        assert call_args[1]["metadata"]["category"] == "tip"

    def test_add_batch(self, store: MemoryStore, mock_mem0_client: MagicMock) -> None:
        memories = [Memory(insight=f"Insight {i}", category="tip") for i in range(3)]
        store.add_batch(memories)
        assert mock_mem0_client.add.call_count == 3

    def test_search_returns_memories(
        self, store: MemoryStore, mock_mem0_client: MagicMock
    ) -> None:
        mock_mem0_client.search.return_value = {
            "results": [
                _make_mem0_item("Tests require DATABASE_URL env var", category="project_fact"),
                _make_mem0_item("Use file_patch for small edits", category="strategy"),
            ]
        }
        results = store.search("database")
        assert len(results) == 2
        assert "DATABASE_URL" in results[0].insight
        mock_mem0_client.search.assert_called_once_with(
            "database", user_id=MEMORY_USER_ID, limit=5
        )

    def test_search_empty(self, store: MemoryStore, mock_mem0_client: MagicMock) -> None:
        mock_mem0_client.search.return_value = {"results": []}
        results = store.search("xyznonexistent")
        assert results == []

    def test_search_handles_list_response(
        self, store: MemoryStore, mock_mem0_client: MagicMock
    ) -> None:
        """search() should handle both dict-with-results and plain list responses."""
        mock_mem0_client.search.return_value = [
            _make_mem0_item("Direct list item", category="tip")
        ]
        results = store.search("something")
        assert len(results) == 1

    def test_get_all(self, store: MemoryStore, mock_mem0_client: MagicMock) -> None:
        mock_mem0_client.get_all.return_value = {
            "results": [
                _make_mem0_item("Insight A", category="strategy"),
                _make_mem0_item("Insight B", category="tip"),
            ]
        }
        all_memories = store.get_all()
        assert len(all_memories) == 2
        mock_mem0_client.get_all.assert_called_with(user_id=MEMORY_USER_ID)

    def test_clear(self, store: MemoryStore, mock_mem0_client: MagicMock) -> None:
        store.clear()
        mock_mem0_client.delete_all.assert_called_once_with(user_id=MEMORY_USER_ID)

    def test_len(self, store: MemoryStore, mock_mem0_client: MagicMock) -> None:
        mock_mem0_client.get_all.return_value = {
            "results": [_make_mem0_item("A"), _make_mem0_item("B")]
        }
        assert len(store) == 2

    def test_format_for_prompt_empty(
        self, store: MemoryStore, mock_mem0_client: MagicMock
    ) -> None:
        mock_mem0_client.get_all.return_value = {"results": []}
        assert store.format_for_prompt() == ""

    def test_format_for_prompt_with_memories(
        self, store: MemoryStore, mock_mem0_client: MagicMock
    ) -> None:
        mock_mem0_client.get_all.return_value = {
            "results": [
                _make_mem0_item("Tests require DB", category="project_fact"),
                _make_mem0_item("Use grep_search", category="strategy"),
            ]
        }
        prompt = store.format_for_prompt()
        assert "Past Learnings" in prompt
        assert "Tests require DB" in prompt
        assert "Use grep_search" in prompt
        assert "📋" in prompt  # project_fact icon
        assert "🎯" in prompt  # strategy icon

    def test_search_exception_returns_empty(
        self, store: MemoryStore, mock_mem0_client: MagicMock
    ) -> None:
        mock_mem0_client.search.side_effect = RuntimeError("connection error")
        results = store.search("anything")
        assert results == []

    def test_qdrant_dir_created(self, tmp_path: Any) -> None:
        """MemoryStore should create the .retrai/qdrant directory."""
        with patch("retrai.memory.store.MemoryStore._init_client", return_value=MagicMock()):
            store = MemoryStore(str(tmp_path))
            assert (tmp_path / ".retrai" / "qdrant").is_dir()
            _ = store  # suppress unused warning
