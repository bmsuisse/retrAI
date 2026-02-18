"""Async file write tool (cwd-relative paths) with path-traversal protection."""

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


async def file_write(path: str, content: str, cwd: str) -> str:
    """Write content to a file relative to cwd. Creates parent dirs as needed.

    Returns the resolved path string on success.
    """
    full_path = _safe_resolve(path, cwd)

    def _write() -> str:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return str(full_path)

    return await asyncio.get_event_loop().run_in_executor(None, _write)
