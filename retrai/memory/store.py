"""Agent memory — persistent cross-run knowledge store."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_MEMORIES = 50
MEMORY_FILE = ".retrai/memory.json"


@dataclass
class Memory:
    """A single learned insight from a past run."""

    insight: str
    category: str  # "strategy" | "error_pattern" | "project_fact" | "tip"
    timestamp: float = field(default_factory=time.time)
    run_id: str = ""
    relevance_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(
            insight=data.get("insight", ""),
            category=data.get("category", "tip"),
            timestamp=data.get("timestamp", 0.0),
            run_id=data.get("run_id", ""),
            relevance_score=data.get("relevance_score", 1.0),
        )


class MemoryStore:
    """JSON-backed persistent memory store for a project.

    Stores learnings, strategies, and error patterns that persist
    across agent runs. Located at `.retrai/memory.json` in the
    project directory.

    Usage:
        store = MemoryStore("/path/to/project")
        store.add(Memory(insight="Tests require DB", category="project_fact"))
        memories = store.search("database")
    """

    def __init__(self, cwd: str) -> None:
        self.cwd = Path(cwd).resolve()
        self._path = self.cwd / MEMORY_FILE
        self._memories: list[Memory] = []
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        if not self._path.exists():
            self._memories = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._memories = [Memory.from_dict(m) for m in data.get("memories", [])]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load memory store: %s", e)
            self._memories = []

    def _save(self) -> None:
        """Persist memories to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "memories": [m.to_dict() for m in self._memories],
        }
        self._path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def add(self, memory: Memory) -> None:
        """Add a memory and auto-prune if over limit."""
        self._memories.append(memory)
        self._prune()
        self._save()

    def add_batch(self, memories: list[Memory]) -> None:
        """Add multiple memories at once."""
        self._memories.extend(memories)
        self._prune()
        self._save()

    def _prune(self) -> None:
        """Keep only the most relevant/recent memories."""
        if len(self._memories) <= MAX_MEMORIES:
            return
        # Sort by relevance * recency, keep top N
        now = time.time()
        scored = sorted(
            self._memories,
            key=lambda m: m.relevance_score * (1.0 / (1.0 + (now - m.timestamp) / 86400)),
            reverse=True,
        )
        self._memories = scored[:MAX_MEMORIES]

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        """Find memories relevant to a query (simple keyword match)."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, Memory]] = []
        for m in self._memories:
            insight_lower = m.insight.lower()
            # Score by word overlap
            insight_words = set(insight_lower.split())
            overlap = len(query_words & insight_words)
            if overlap > 0 or query_lower in insight_lower:
                score = overlap + (1.0 if query_lower in insight_lower else 0.0)
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    def get_all(self) -> list[Memory]:
        """Return all stored memories."""
        return list(self._memories)

    def clear(self) -> None:
        """Remove all memories."""
        self._memories = []
        self._save()

    def format_for_prompt(self, limit: int = 10) -> str:
        """Format memories as a section for the system prompt."""
        if not self._memories:
            return ""

        # Pick most recent/relevant
        recent = sorted(
            self._memories,
            key=lambda m: m.timestamp,
            reverse=True,
        )[:limit]

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
        return len(self._memories)
