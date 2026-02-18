"""Tests for path traversal protection and file_patch tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrai.tools.file_patch import file_patch
from retrai.tools.file_read import file_list, file_read
from retrai.tools.file_write import file_write

# ── Path traversal guards ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_read_blocks_traversal(tmp_path: Path):
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_read("../../etc/passwd", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_read_blocks_absolute_traversal(tmp_path: Path):
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_read("/etc/passwd", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_write_blocks_traversal(tmp_path: Path):
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_write("../../tmp/evil.txt", "pwned", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_list_blocks_traversal(tmp_path: Path):
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_list("../../", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_patch_blocks_traversal(tmp_path: Path):
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        await file_patch("../../etc/passwd", "root", "pwned", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_safe_paths_still_work(tmp_path: Path):
    """Ensure normal nested paths are not blocked."""
    sub = tmp_path / "src" / "lib"
    sub.mkdir(parents=True)
    (sub / "main.py").write_text("hello")
    content = await file_read("src/lib/main.py", cwd=str(tmp_path))
    assert content == "hello"


# ── file_patch ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_patch_basic(tmp_path: Path):
    (tmp_path / "code.py").write_text("x = 1\ny = 2\n")
    result = await file_patch("code.py", "x = 1", "x = 42", cwd=str(tmp_path))
    assert "Patched" in result
    assert "line 1" in result
    assert (tmp_path / "code.py").read_text() == "x = 42\ny = 2\n"


@pytest.mark.asyncio
async def test_file_patch_multiline(tmp_path: Path):
    content = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    (tmp_path / "code.py").write_text(content)
    result = await file_patch(
        "code.py",
        "def foo():\n    return 1",
        "def foo():\n    return 42",
        cwd=str(tmp_path),
    )
    assert "Patched" in result
    assert "return 42" in (tmp_path / "code.py").read_text()


@pytest.mark.asyncio
async def test_file_patch_not_found(tmp_path: Path):
    (tmp_path / "code.py").write_text("x = 1\n")
    with pytest.raises(ValueError, match="not found"):
        await file_patch("code.py", "nonexistent text", "replacement", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_patch_multiple_matches_rejected(tmp_path: Path):
    (tmp_path / "code.py").write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError, match="2 times"):
        await file_patch("code.py", "x = 1", "x = 2", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_patch_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        await file_patch("nope.py", "old", "new", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_patch_directory_raises(tmp_path: Path):
    (tmp_path / "adir").mkdir()
    with pytest.raises(IsADirectoryError):
        await file_patch("adir", "old", "new", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_patch_creates_no_parent_dirs(tmp_path: Path):
    """file_patch should NOT create missing parent dirs (unlike file_write)."""
    with pytest.raises(FileNotFoundError):
        await file_patch("deep/nested/f.py", "old", "new", cwd=str(tmp_path))
