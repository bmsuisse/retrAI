"""Async file rename/move tool (cwd-relative paths) with path-traversal protection."""

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


async def file_rename(old_path: str, new_path: str, cwd: str) -> str:
    """Rename or move a file within the project tree.

    Both source and destination must resolve inside the project root.
    Creates parent directories for the destination if needed.
    Raises FileExistsError if the destination already exists.
    """
    src = _safe_resolve(old_path, cwd)
    dst = _safe_resolve(new_path, cwd)

    def _rename() -> str:
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {old_path}")
        if dst.exists():
            raise FileExistsError(f"Destination already exists: {new_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return f"Renamed {old_path} → {new_path}"

    return await asyncio.get_event_loop().run_in_executor(None, _rename)
