"""Recursive code search tool — find patterns across project files."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

# Directories and extensions to always skip
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "dist", "build", ".eggs", "target", "vendor",
})

_BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".svg", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".pyc", ".pyo", ".class", ".jar", ".war",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv",
    ".db", ".sqlite", ".sqlite3",
    ".wasm", ".lock",
})


@dataclass
class SearchMatch:
    file: str
    line_number: int
    line_content: str


async def grep_search(
    pattern: str,
    cwd: str,
    *,
    is_regex: bool = False,
    case_insensitive: bool = True,
    include_glob: str | None = None,
    max_results: int = 50,
) -> str:
    """Search for a text pattern across all project files.

    Args:
        pattern: The search term (literal or regex).
        cwd: Project root directory.
        is_regex: If True, treat pattern as regex; otherwise literal.
        case_insensitive: Case-insensitive matching (default True).
        include_glob: Optional glob to filter files (e.g. ``*.py``).
        max_results: Cap on results returned.

    Returns:
        Formatted string of matches, one per line.
    """
    matches = await asyncio.get_event_loop().run_in_executor(
        None,
        _search_sync,
        pattern,
        cwd,
        is_regex,
        case_insensitive,
        include_glob,
        max_results,
    )

    if not matches:
        return f"No matches found for: {pattern}"

    lines: list[str] = []
    for m in matches:
        lines.append(f"{m.file}:{m.line_number}: {m.line_content}")

    result = "\n".join(lines)
    if len(matches) >= max_results:
        result += f"\n\n[... capped at {max_results} results ...]"
    return result


def _search_sync(
    pattern: str,
    cwd: str,
    is_regex: bool,
    case_insensitive: bool,
    include_glob: str | None,
    max_results: int,
) -> list[SearchMatch]:
    """Synchronous file search."""
    root = Path(cwd).resolve()
    flags = re.IGNORECASE if case_insensitive else 0

    if is_regex:
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            return [SearchMatch(file="<error>", line_number=0, line_content=f"Invalid regex: {e}")]
    else:
        escaped = re.escape(pattern)
        compiled = re.compile(escaped, flags)

    matches: list[SearchMatch] = []

    for file_path in _walk_files(root, include_glob):
        if len(matches) >= max_results:
            break

        rel = str(file_path.relative_to(root))

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            if compiled.search(line):
                matches.append(
                    SearchMatch(
                        file=rel,
                        line_number=i,
                        line_content=line.strip()[:200],
                    )
                )
                if len(matches) >= max_results:
                    break

    return matches


def _walk_files(root: Path, include_glob: str | None) -> list[Path]:
    """Walk the project tree, skipping ignored dirs and binary files."""
    files: list[Path] = []

    if include_glob:
        # Use glob matching from the root
        for p in root.rglob(include_glob):
            if p.is_file() and not _should_skip_path(p, root):
                files.append(p)
        return sorted(files)

    for p in root.rglob("*"):
        if p.is_file() and not _should_skip_path(p, root):
            files.append(p)
    return sorted(files)


def _should_skip_path(path: Path, root: Path) -> bool:
    """Return True if the path should be excluded from search."""
    # Check if any parent directory is in the skip list
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True

    for part in rel.parts:
        if part in _SKIP_DIRS:
            return True

    # Skip binary extensions
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True

    # Skip files > 1 MB
    try:
        if path.stat().st_size > 1_000_000:
            return True
    except OSError:
        return True

    return False
