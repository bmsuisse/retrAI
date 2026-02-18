"""Tests for the Memory store and extractor."""

from __future__ import annotations

from retrai.memory.store import MAX_MEMORIES, Memory, MemoryStore

# ---------------------------------------------------------------------------
# Memory dataclass
# ---------------------------------------------------------------------------


class TestMemory:
    def test_defaults(self):
        m = Memory(insight="Tests need DB", category="project_fact")
        assert m.insight == "Tests need DB"
        assert m.category == "project_fact"
        assert m.relevance_score == 1.0
        assert m.timestamp > 0

    def test_round_trip(self):
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


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class TestMemoryStore:
    def test_add_and_get_all(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        store.add(Memory(insight="Test insight", category="tip"))
        assert len(store) == 1
        assert store.get_all()[0].insight == "Test insight"

    def test_persistence(self, tmp_path):
        store1 = MemoryStore(str(tmp_path))
        store1.add(Memory(insight="Persistent", category="strategy"))

        # New instance should load from disk
        store2 = MemoryStore(str(tmp_path))
        assert len(store2) == 1
        assert store2.get_all()[0].insight == "Persistent"

    def test_add_batch(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        memories = [Memory(insight=f"Insight {i}", category="tip") for i in range(5)]
        store.add_batch(memories)
        assert len(store) == 5

    def test_prune(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        memories = [
            Memory(
                insight=f"Insight {i}",
                category="tip",
                relevance_score=float(i),
            )
            for i in range(MAX_MEMORIES + 10)
        ]
        store.add_batch(memories)
        assert len(store) <= MAX_MEMORIES

    def test_search_keyword(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        store.add_batch(
            [
                Memory(insight="Tests require DATABASE_URL env var", category="project_fact"),
                Memory(insight="Use file_patch for small edits", category="strategy"),
                Memory(insight="The auth module needs Redis", category="project_fact"),
            ]
        )
        results = store.search("database")
        assert len(results) >= 1
        assert "DATABASE_URL" in results[0].insight

    def test_search_no_match(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        store.add(Memory(insight="Something else", category="tip"))
        results = store.search("xyznonexistent")
        assert len(results) == 0

    def test_clear(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        store.add(Memory(insight="To be cleared", category="tip"))
        assert len(store) == 1
        store.clear()
        assert len(store) == 0

    def test_format_for_prompt_empty(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        assert store.format_for_prompt() == ""

    def test_format_for_prompt_with_memories(self, tmp_path):
        store = MemoryStore(str(tmp_path))
        store.add(Memory(insight="Tests require DB", category="project_fact"))
        store.add(Memory(insight="Use grep_search", category="strategy"))
        prompt = store.format_for_prompt()
        assert "Past Learnings" in prompt
        assert "Tests require DB" in prompt
        assert "Use grep_search" in prompt

    def test_corrupted_file(self, tmp_path):
        """Store should handle corrupted JSON gracefully."""
        retrai_dir = tmp_path / ".retrai"
        retrai_dir.mkdir()
        (retrai_dir / "memory.json").write_text("not json")
        store = MemoryStore(str(tmp_path))
        assert len(store) == 0
