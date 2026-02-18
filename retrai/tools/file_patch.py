"""Async file patch tool — surgical text replacement within files."""

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


async def file_patch(
    path: str,
    old: str,
    new: str,
    cwd: str,
    occurrence: int = 1,
) -> str:
    """Replace an exact occurrence of *old* with *new* in a file.

    Much more context-efficient than rewriting entire files — the LLM only
    needs to specify the exact text to find and its replacement.

    Args:
        occurrence: Which occurrence to replace (1-indexed).
            - ``1`` (default): replace the first match; raises if multiple exist.
            - ``N``: replace only the N-th match.
            - ``0``: replace **all** occurrences.

    Raises ``ValueError`` if *old* is not found or if the requested
    occurrence exceeds the number of matches.
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
            raise ValueError(f"Target text not found in {path}. Searched for: {old[:200]!r}")

        # Default behaviour: unique match required
        if occurrence == 1 and count > 1:
            raise ValueError(
                f"Target text found {count} times in {path} — must be unique. "
                f"Use occurrence=N to target a specific match. "
                f"Searched for: {old[:200]!r}"
            )

        if occurrence == 0:
            # Replace all
            patched = content.replace(old, new)
            full_path.write_text(patched, encoding="utf-8")
            return (
                f"Patched all {count} occurrences in {path} "
                f"({len(old)} chars → {len(new)} chars each)"
            )

        # Replace the N-th occurrence
        if occurrence > count:
            raise ValueError(
                f"Requested occurrence {occurrence} but only {count} match(es) found in {path}"
            )

        # Walk through occurrences to find the right offset
        offset = 0
        for i in range(occurrence):
            idx = content.index(old, offset)
            if i == occurrence - 1:
                offset = idx
                break
            offset = idx + len(old)

        line_number = content[:offset].count("\n") + 1
        patched = content[:offset] + new + content[offset + len(old) :]
        full_path.write_text(patched, encoding="utf-8")
        return f"Patched {path} at line {line_number} ({len(old)} chars → {len(new)} chars)"

    return await asyncio.get_event_loop().run_in_executor(None, _patch)
