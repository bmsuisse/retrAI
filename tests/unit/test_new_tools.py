"""Tests for the new tools: grep_search, find_files, and git_diff."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrai.tools.find_files import find_files
from retrai.tools.grep_search import grep_search

# ── grep_search ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grep_search_literal_match(tmp_path: Path):
    (tmp_path / "hello.py").write_text("def greet():\n    return 'hello world'\n")
    result = await grep_search("hello world", cwd=str(tmp_path))
    assert "hello.py" in result
    assert "hello world" in result


@pytest.mark.asyncio
async def test_grep_search_regex_match(tmp_path: Path):
    (tmp_path / "calc.py").write_text("x = 42\ny = 100\nz = 999\n")
    result = await grep_search(r"\d{3}", cwd=str(tmp_path), is_regex=True)
    assert "100" in result or "999" in result


@pytest.mark.asyncio
async def test_grep_search_case_insensitive(tmp_path: Path):
    (tmp_path / "test.py").write_text("FOO_BAR = True\n")
    result = await grep_search("foo_bar", cwd=str(tmp_path), case_insensitive=True)
    assert "FOO_BAR" in result


@pytest.mark.asyncio
async def test_grep_search_case_sensitive(tmp_path: Path):
    (tmp_path / "test.py").write_text("FOO_BAR = True\n")
    result = await grep_search("foo_bar", cwd=str(tmp_path), case_insensitive=False)
    assert "No matches" in result


@pytest.mark.asyncio
async def test_grep_search_no_match(tmp_path: Path):
    (tmp_path / "empty.py").write_text("pass\n")
    result = await grep_search("nonexistent_pattern_xyz", cwd=str(tmp_path))
    assert "No matches" in result


@pytest.mark.asyncio
async def test_grep_search_include_glob(tmp_path: Path):
    (tmp_path / "code.py").write_text("target = True\n")
    (tmp_path / "notes.txt").write_text("target = True\n")
    result = await grep_search("target", cwd=str(tmp_path), include_glob="*.py")
    assert "code.py" in result
    assert "notes.txt" not in result


@pytest.mark.asyncio
async def test_grep_search_max_results(tmp_path: Path):
    # Create a file with many matching lines
    content = "\n".join(f"line_{i} = match" for i in range(100))
    (tmp_path / "big.py").write_text(content)
    result = await grep_search("match", cwd=str(tmp_path), max_results=5)
    assert "capped at 5" in result


@pytest.mark.asyncio
async def test_grep_search_skips_git_dir(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("secret_token = abc123\n")
    (tmp_path / "main.py").write_text("# no secret here\n")
    result = await grep_search("secret_token", cwd=str(tmp_path))
    assert "No matches" in result


@pytest.mark.asyncio
async def test_grep_search_skips_node_modules(tmp_path: Path):
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = 'findme'\n")
    (tmp_path / "app.js").write_text("// nothing\n")
    result = await grep_search("findme", cwd=str(tmp_path))
    assert "No matches" in result


@pytest.mark.asyncio
async def test_grep_search_invalid_regex(tmp_path: Path):
    (tmp_path / "test.py").write_text("x = 1\n")
    result = await grep_search("[invalid", cwd=str(tmp_path), is_regex=True)
    assert "Invalid regex" in result


# ── find_files ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_files_glob_match(tmp_path: Path):
    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.py").write_text("")
    (tmp_path / "readme.md").write_text("")
    result = await find_files("*.py", cwd=str(tmp_path))
    assert "foo.py" in result
    assert "bar.py" in result
    assert "readme.md" not in result


@pytest.mark.asyncio
async def test_find_files_recursive(tmp_path: Path):
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    (sub / "nested.py").write_text("")
    result = await find_files("**/*.py", cwd=str(tmp_path))
    assert "nested.py" in result


@pytest.mark.asyncio
async def test_find_files_no_match(tmp_path: Path):
    (tmp_path / "test.txt").write_text("")
    result = await find_files("*.xyz", cwd=str(tmp_path))
    assert "No files found" in result


@pytest.mark.asyncio
async def test_find_files_skips_pycache(tmp_path: Path):
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "module.cpython-312.pyc").write_text("")
    (tmp_path / "real.py").write_text("")
    result = await find_files("**/*", cwd=str(tmp_path))
    assert "__pycache__" not in result
    assert "real.py" in result


@pytest.mark.asyncio
async def test_find_files_shows_size(tmp_path: Path):
    (tmp_path / "small.txt").write_text("hi")
    result = await find_files("*.txt", cwd=str(tmp_path))
    assert "B" in result  # size shows bytes


@pytest.mark.asyncio
async def test_find_files_max_results(tmp_path: Path):
    for i in range(20):
        (tmp_path / f"file_{i}.txt").write_text("")
    result = await find_files("*.txt", cwd=str(tmp_path), max_results=5)
    assert "capped at 5" in result
