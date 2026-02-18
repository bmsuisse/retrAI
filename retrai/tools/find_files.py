"""Find files by name/pattern in the project tree."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

# Directories to always skip
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "dist", "build", ".eggs", "target", "vendor",
})


@dataclass
class FileEntry:
    path: str
    size: int
    is_dir: bool


async def find_files(
    pattern: str,
    cwd: str,
    *,
    max_results: int = 100,
    include_dirs: bool = False,
) -> str:
    """Find files matching a glob pattern in the project tree.

    Args:
        pattern: Glob pattern (e.g. ``*.py``, ``**/test_*.ts``).
        cwd: Project root directory.
        max_results: Maximum entries to return.
        include_dirs: If True, include directories in results.

    Returns:
        Formatted list of matching paths with sizes.
    """
    entries = await asyncio.get_event_loop().run_in_executor(
        None, _find_sync, pattern, cwd, max_results, include_dirs
    )

    if not entries:
        return f"No files found matching: {pattern}"

    lines: list[str] = []
    for e in entries:
        if e.is_dir:
            lines.append(f"  {e.path}/")
        else:
            size_str = _human_size(e.size)
            lines.append(f"  {e.path}  ({size_str})")

    result = "\n".join(lines)
    if len(entries) >= max_results:
        result += f"\n\n[... capped at {max_results} results ...]"
    return result


def _find_sync(
    pattern: str,
    cwd: str,
    max_results: int,
    include_dirs: bool,
) -> list[FileEntry]:
    """Synchronous file finder."""
    root = Path(cwd).resolve()
    entries: list[FileEntry] = []

    for p in root.rglob(pattern):
        if _should_skip(p, root):
            continue

        if p.is_dir():
            if include_dirs:
                rel = str(p.relative_to(root))
                entries.append(FileEntry(path=rel, size=0, is_dir=True))
        elif p.is_file():
            rel = str(p.relative_to(root))
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            entries.append(FileEntry(path=rel, size=size, is_dir=False))

        if len(entries) >= max_results:
            break

    return sorted(entries, key=lambda e: e.path)


def _should_skip(path: Path, root: Path) -> bool:
    """Return True if the path should be excluded."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True

    for part in rel.parts:
        if part in _SKIP_DIRS:
            return True
    return False


def _human_size(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} TB"
