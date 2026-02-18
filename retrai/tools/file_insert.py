"""Async file insert tool — insert text at a specific line number."""

from __future__ import annotations

import asyncio
from pathlib import Path


def _safe_resolve(path: str, cwd: str) -> Path:
    """Resolve *path* relative to *cwd* and ensure it stays inside the tree."""
    root = Path(cwd).resolve()
    full = (root / path).resolve()
    if not (full == root or str(full).startswith(str(root) + "/")):
        raise PermissionError(f"Path traversal blocked: '{path}' resolves outside project root")
    return full


async def file_insert(path: str, line: int, content: str, cwd: str) -> str:
    """Insert *content* at line *line* (1-indexed) in a file.

    - ``line <= 0`` or ``line == 1``: prepend to the file.
    - ``line > total_lines``: append to the file.
    - Otherwise: insert before the specified line.

    The file must already exist (use ``file_write`` to create new files).
    """
    full_path = _safe_resolve(path, cwd)

    def _insert() -> str:
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")

        existing = full_path.read_text(encoding="utf-8")
        lines = existing.splitlines(keepends=True)
        total = len(lines)

        # Normalise line number
        insert_at = max(0, line - 1)
        if insert_at > total:
            insert_at = total

        # Ensure content ends with a newline for clean insertion
        text = content if content.endswith("\n") else content + "\n"

        lines.insert(insert_at, text)
        full_path.write_text("".join(lines), encoding="utf-8")

        display_line = insert_at + 1
        return f"Inserted {len(text)} chars at line {display_line} in {path}"

    return await asyncio.get_event_loop().run_in_executor(None, _insert)
