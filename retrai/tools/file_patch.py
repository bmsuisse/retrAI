"""Async file patch tool — surgical text replacement within files."""

from __future__ import annotations

import asyncio
from pathlib import Path


def _safe_resolve(path: str, cwd: str) -> Path:
    """Resolve *path* relative to *cwd* and ensure it stays inside the tree."""
    root = Path(cwd).resolve()
    full = (root / path).resolve()
    if not (full == root or str(full).startswith(str(root) + "/")):
        raise PermissionError(
            f"Path traversal blocked: '{path}' resolves outside project root"
        )
    return full


async def file_patch(path: str, old: str, new: str, cwd: str) -> str:
    """Replace an exact occurrence of *old* with *new* in a file.

    Much more context-efficient than rewriting entire files — the LLM only
    needs to specify the exact text to find and its replacement.

    Raises ``ValueError`` if *old* is not found or appears more than once.
    Returns a confirmation string with the line number of the match.
    """
    full_path = _safe_resolve(path, cwd)

    def _patch() -> str:
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")

        content = full_path.read_text(encoding="utf-8")
        count = content.count(old)
        if count == 0:
            raise ValueError(
                f"Target text not found in {path}. "
                f"Searched for: {old[:200]!r}"
            )
        if count > 1:
            raise ValueError(
                f"Target text found {count} times in {path} — must be unique. "
                f"Searched for: {old[:200]!r}"
            )

        # Find the line number of the match
        offset = content.index(old)
        line_number = content[:offset].count("\n") + 1

        patched = content.replace(old, new, 1)
        full_path.write_text(patched, encoding="utf-8")
        return f"Patched {path} at line {line_number} ({len(old)} chars → {len(new)} chars)"

    return await asyncio.get_event_loop().run_in_executor(None, _patch)
