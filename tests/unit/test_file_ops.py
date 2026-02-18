"""Tests for file_delete, file_rename, file_insert tools and enhanced file_patch."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrai.tools.file_delete import file_delete
from retrai.tools.file_insert import file_insert
from retrai.tools.file_patch import file_patch
from retrai.tools.file_rename import file_rename

# ── file_delete ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_delete_basic(tmp_path: Path) -> None:
    (tmp_path / "trash.txt").write_text("bye")
    result = await file_delete("trash.txt", cwd=str(tmp_path))
    assert "Deleted" in result
    assert not (tmp_path / "trash.txt").exists()


@pytest.mark.asyncio
async def test_file_delete_empty_dir(tmp_path: Path) -> None:
    (tmp_path / "empty_dir").mkdir()
    result = await file_delete("empty_dir", cwd=str(tmp_path))
    assert "Deleted" in result
    assert not (tmp_path / "empty_dir").exists()


@pytest.mark.asyncio
async def test_file_delete_nonempty_dir_rejected(tmp_path: Path) -> None:
    d = tmp_path / "full_dir"
    d.mkdir()
    (d / "keep.txt").write_text("data")
    with pytest.raises(OSError, match="non-empty"):
        await file_delete("full_dir", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_delete_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await file_delete("nope.txt", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_delete_traversal_blocked(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_delete("../../etc/passwd", cwd=str(tmp_path))


# ── file_rename ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_rename_basic(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_text("content")
    result = await file_rename("old.txt", "new.txt", cwd=str(tmp_path))
    assert "Renamed" in result
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").read_text() == "content"


@pytest.mark.asyncio
async def test_file_rename_creates_parents(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("code")
    result = await file_rename("src.py", "deep/nested/dst.py", cwd=str(tmp_path))
    assert "Renamed" in result
    assert (tmp_path / "deep" / "nested" / "dst.py").read_text() == "code"


@pytest.mark.asyncio
async def test_file_rename_source_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await file_rename("nope.txt", "dest.txt", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_rename_dest_exists(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    with pytest.raises(FileExistsError):
        await file_rename("a.txt", "b.txt", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_rename_traversal_blocked(tmp_path: Path) -> None:
    (tmp_path / "src.txt").write_text("data")
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_rename("src.txt", "../../evil.txt", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_rename_src_traversal_blocked(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_rename("../../etc/passwd", "stolen.txt", cwd=str(tmp_path))


# ── file_insert ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_insert_at_line(tmp_path: Path) -> None:
    (tmp_path / "code.py").write_text("line1\nline2\nline3\n")
    result = await file_insert("code.py", 2, "inserted", cwd=str(tmp_path))
    assert "Inserted" in result
    content = (tmp_path / "code.py").read_text()
    lines = content.splitlines()
    assert lines[0] == "line1"
    assert lines[1] == "inserted"
    assert lines[2] == "line2"


@pytest.mark.asyncio
async def test_file_insert_prepend(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("existing\n")
    await file_insert("f.txt", 0, "first", cwd=str(tmp_path))
    content = (tmp_path / "f.txt").read_text()
    assert content.startswith("first\n")


@pytest.mark.asyncio
async def test_file_insert_append(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("line1\nline2\n")
    await file_insert("f.txt", 9999, "appended", cwd=str(tmp_path))
    content = (tmp_path / "f.txt").read_text()
    assert content.endswith("appended\n")


@pytest.mark.asyncio
async def test_file_insert_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await file_insert("nope.py", 1, "text", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_insert_directory_raises(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    with pytest.raises(IsADirectoryError):
        await file_insert("dir", 1, "text", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_insert_traversal_blocked(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_insert("../../etc/passwd", 1, "pwned", cwd=str(tmp_path))


# ── file_patch (occurrence parameter) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_patch_occurrence_second(tmp_path: Path) -> None:
    (tmp_path / "code.py").write_text("x = 1\ny = 2\nx = 1\n")
    result = await file_patch("code.py", "x = 1", "x = 99", cwd=str(tmp_path), occurrence=2)
    assert "Patched" in result
    content = (tmp_path / "code.py").read_text()
    assert content == "x = 1\ny = 2\nx = 99\n"


@pytest.mark.asyncio
async def test_file_patch_occurrence_all(tmp_path: Path) -> None:
    (tmp_path / "code.py").write_text("x = 1\ny = 2\nx = 1\nz = x = 1\n")
    result = await file_patch("code.py", "x = 1", "x = 0", cwd=str(tmp_path), occurrence=0)
    assert "all" in result.lower()
    content = (tmp_path / "code.py").read_text()
    assert content.count("x = 0") == 3
    assert content.count("x = 1") == 0


@pytest.mark.asyncio
async def test_file_patch_occurrence_exceeds(tmp_path: Path) -> None:
    (tmp_path / "code.py").write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError, match="only 2"):
        await file_patch("code.py", "x = 1", "x = 99", cwd=str(tmp_path), occurrence=5)


@pytest.mark.asyncio
async def test_file_patch_default_still_rejects_multiple(tmp_path: Path) -> None:
    """Default behaviour: multiple matches without occurrence raises."""
    (tmp_path / "code.py").write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError, match="2 times"):
        await file_patch("code.py", "x = 1", "x = 99", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_patch_default_unique_still_works(tmp_path: Path) -> None:
    """Default behaviour with a unique match still works."""
    (tmp_path / "code.py").write_text("x = 1\ny = 2\n")
    result = await file_patch("code.py", "x = 1", "x = 42", cwd=str(tmp_path))
    assert "Patched" in result
    assert (tmp_path / "code.py").read_text() == "x = 42\ny = 2\n"


# ── Safety guardrails ────────────────────────────────────────────────────────


def test_safety_guard_blocks_critical_file_delete() -> None:
    from retrai.safety.guardrails import SafetyGuard

    guard = SafetyGuard()
    violations = guard.check_tool_call("file_delete", {"path": ".retrai.yml"})
    assert len(violations) == 1
    assert violations[0].rule == "critical_file_delete"


def test_safety_guard_blocks_git_delete() -> None:
    from retrai.safety.guardrails import SafetyGuard

    guard = SafetyGuard()
    violations = guard.check_tool_call("file_delete", {"path": ".git/HEAD"})
    assert len(violations) == 1
    assert violations[0].rule == "git_delete"


def test_safety_guard_allows_normal_delete() -> None:
    from retrai.safety.guardrails import SafetyGuard

    guard = SafetyGuard()
    violations = guard.check_tool_call("file_delete", {"path": "temp/output.txt"})
    assert violations == []
