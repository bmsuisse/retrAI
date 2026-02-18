"""Async file delete tool (cwd-relative paths) with path-traversal protection."""

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


async def file_delete(path: str, cwd: str) -> str:
    """Delete a file or empty directory relative to cwd.

    Refuses to delete non-empty directories (use bash_exec for that).
    Returns a confirmation string on success.
    """
    full_path = _safe_resolve(path, cwd)

    def _delete() -> str:
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if full_path.is_dir():
            try:
                full_path.rmdir()
            except OSError as exc:
                raise OSError(
                    f"Cannot delete non-empty directory: {path}. "
                    "Remove contents first or use bash_exec."
                ) from exc
            return f"Deleted directory: {full_path}"
        full_path.unlink()
        return f"Deleted file: {full_path}"

    return await asyncio.get_event_loop().run_in_executor(None, _delete)
