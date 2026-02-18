"""Agent memory — persistent cross-run knowledge store backed by mem0 + local Qdrant."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_USER_ID = "retrai_agent"


@dataclass
class Memory:
    """A single learned insight from a past run."""

    insight: str
    category: str  # "strategy" | "error_pattern" | "project_fact" | "tip"
    timestamp: float = field(default_factory=time.time)
    run_id: str = ""
    relevance_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight": self.insight,
            "category": self.category,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(
            insight=data.get("insight", ""),
            category=data.get("category", "tip"),
            timestamp=data.get("timestamp", 0.0),
            run_id=data.get("run_id", ""),
            relevance_score=data.get("relevance_score", 1.0),
        )

    @classmethod
    def from_mem0(cls, item: dict[str, Any]) -> Memory:
        """Construct a Memory from a mem0 search/get result dict."""
        meta = item.get("metadata") or {}
        return cls(
            insight=item.get("memory", item.get("text", "")),
            category=meta.get("category", "tip"),
            timestamp=meta.get("timestamp", time.time()),
            run_id=meta.get("run_id", ""),
            relevance_score=float(item.get("score", 1.0)),
        )


def _build_mem0_config(qdrant_path: Path) -> dict[str, Any]:
    """Build mem0 config using local file-based Qdrant + OpenAI embeddings."""
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "retrai_memory",
                "path": str(qdrant_path),
                "embedding_model_dims": 1536,  # text-embedding-3-small
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {"model": "text-embedding-3-small"},
        },
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o-mini"},
        },
    }


class MemoryStore:
    """mem0-backed persistent memory store for a project.

    Stores learnings, strategies, and error patterns that persist
    across agent runs. Uses local Qdrant (no server) for vector storage
    and OpenAI text-embedding-3-small for semantic search.

    Qdrant data is persisted at `.retrai/qdrant/` in the project directory.

    Requires the `memory` optional extra:
        uv pip install "retrai[memory]"

    Usage:
        store = MemoryStore("/path/to/project")
        store.add(Memory(insight="Tests require DB", category="project_fact"))
        memories = store.search("database")
    """

    def __init__(self, cwd: str) -> None:
        self.cwd = Path(cwd).resolve()
        self._qdrant_path = self.cwd / ".retrai" / "qdrant"
        self._qdrant_path.mkdir(parents=True, exist_ok=True)
        self._client = self._init_client()

    def _init_client(self) -> Any:
        try:
            from mem0 import Memory as Mem0Memory  # type: ignore[import-untyped]

            config = _build_mem0_config(self._qdrant_path)
            return Mem0Memory.from_config(config)
        except ImportError as e:
            raise ImportError(
                "mem0ai is required for MemoryStore. "
                "Install it with: uv pip install 'retrai[memory]'"
            ) from e

    def add(self, memory: Memory) -> None:
        """Add a memory insight."""
        self._client.add(
            memory.insight,
            user_id=MEMORY_USER_ID,
            metadata={
                "category": memory.category,
                "timestamp": memory.timestamp,
                "run_id": memory.run_id,
                "relevance_score": memory.relevance_score,
            },
        )

    def add_batch(self, memories: list[Memory]) -> None:
        """Add multiple memories at once."""
        for m in memories:
            self.add(m)

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        """Find memories semantically relevant to a query."""
        try:
            results = self._client.search(query, user_id=MEMORY_USER_ID, limit=limit)
            # mem0 returns a dict with a "results" key in newer versions
            items: list[dict[str, Any]] = (
                results.get("results", results) if isinstance(results, dict) else results
            )
            return [Memory.from_mem0(item) for item in items]
        except Exception as e:
            logger.warning("Memory search failed: %s", e)
            return []

    def get_all(self) -> list[Memory]:
        """Return all stored memories."""
        try:
            results = self._client.get_all(user_id=MEMORY_USER_ID)
            items: list[dict[str, Any]] = (
                results.get("results", results) if isinstance(results, dict) else results
            )
            return [Memory.from_mem0(item) for item in items]
        except Exception as e:
            logger.warning("Memory get_all failed: %s", e)
            return []

    def clear(self) -> None:
        """Remove all memories."""
        try:
            self._client.delete_all(user_id=MEMORY_USER_ID)
        except Exception as e:
            logger.warning("Memory clear failed: %s", e)

    def format_for_prompt(self, limit: int = 10) -> str:
        """Format memories as a section for the system prompt."""
        memories = self.get_all()
        if not memories:
            return ""

        # Sort by recency (timestamp desc), take top N
        recent = sorted(memories, key=lambda m: m.timestamp, reverse=True)[:limit]

        lines = ["## Past Learnings (from previous runs)\n"]
        for m in recent:
            icon = {
                "strategy": "🎯",
                "error_pattern": "⚠️",
                "project_fact": "📋",
                "tip": "💡",
            }.get(m.category, "•")
            lines.append(f"- {icon} {m.insight}")

        lines.append(
            "\nUse these learnings to avoid repeating mistakes and to apply successful strategies."
        )
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.get_all())
