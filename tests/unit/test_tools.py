"""Tests for the async tool implementations."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrai.tools.bash_exec import bash_exec
from retrai.tools.file_read import file_list, file_read
from retrai.tools.file_write import file_write
from retrai.tools.pytest_runner import PytestRunResult, run_pytest

# ── bash_exec ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bash_exec_simple_command(tmp_path: Path):
    result = await bash_exec("echo hello", cwd=str(tmp_path))
    assert result.returncode == 0
    assert "hello" in result.stdout
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_bash_exec_exit_code_propagated(tmp_path: Path):
    result = await bash_exec("exit 42", cwd=str(tmp_path))
    assert result.returncode == 42


@pytest.mark.asyncio
async def test_bash_exec_stderr_captured(tmp_path: Path):
    result = await bash_exec("echo errout >&2", cwd=str(tmp_path))
    assert "errout" in result.stderr


@pytest.mark.asyncio
async def test_bash_exec_timeout(tmp_path: Path):
    result = await bash_exec("sleep 10", cwd=str(tmp_path), timeout=0.1)
    assert result.timed_out is True
    assert result.returncode == -1


@pytest.mark.asyncio
async def test_bash_exec_cwd_is_respected(tmp_path: Path):
    (tmp_path / "marker.txt").write_text("yes")
    result = await bash_exec("ls", cwd=str(tmp_path))
    assert "marker.txt" in result.stdout


@pytest.mark.asyncio
async def test_bash_exec_env_injection(tmp_path: Path):
    result = await bash_exec("echo $MY_VAR", cwd=str(tmp_path), env={"MY_VAR": "hello123"})
    assert "hello123" in result.stdout


# ── file_read ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_read_basic(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("world")
    content = await file_read("hello.txt", cwd=str(tmp_path))
    assert content == "world"


@pytest.mark.asyncio
async def test_file_read_nested_path(tmp_path: Path):
    sub = tmp_path / "sub" / "dir"
    sub.mkdir(parents=True)
    (sub / "f.py").write_text("x = 1")
    content = await file_read("sub/dir/f.py", cwd=str(tmp_path))
    assert "x = 1" in content


@pytest.mark.asyncio
async def test_file_read_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        await file_read("no_such_file.txt", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_read_directory_raises(tmp_path: Path):
    (tmp_path / "adir").mkdir()
    with pytest.raises(IsADirectoryError):
        await file_read("adir", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_file_read_truncation(tmp_path: Path):
    (tmp_path / "big.txt").write_text("x" * 1000)
    content = await file_read("big.txt", cwd=str(tmp_path), max_bytes=100)
    assert "truncated" in content
    assert len(content) < 200


# ── file_list ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_list_basic(tmp_path: Path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "sub").mkdir()
    entries = await file_list(".", cwd=str(tmp_path))
    assert any("a.py" in e for e in entries)
    assert any("b.py" in e for e in entries)
    assert any("sub/" in e for e in entries)


@pytest.mark.asyncio
async def test_file_list_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        await file_list("nonexistent", cwd=str(tmp_path))


# ── file_write ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_write_creates_file(tmp_path: Path):
    await file_write("out.txt", "hello world", cwd=str(tmp_path))
    assert (tmp_path / "out.txt").read_text() == "hello world"


@pytest.mark.asyncio
async def test_file_write_creates_parent_dirs(tmp_path: Path):
    await file_write("deep/nested/file.py", "x = 1", cwd=str(tmp_path))
    assert (tmp_path / "deep" / "nested" / "file.py").read_text() == "x = 1"


@pytest.mark.asyncio
async def test_file_write_overwrites_existing(tmp_path: Path):
    (tmp_path / "f.txt").write_text("old")
    await file_write("f.txt", "new", cwd=str(tmp_path))
    assert (tmp_path / "f.txt").read_text() == "new"


@pytest.mark.asyncio
async def test_file_write_returns_absolute_path(tmp_path: Path):
    result = await file_write("sub/f.txt", "data", cwd=str(tmp_path))
    assert Path(result).is_absolute()
    assert "sub/f.txt" in result or "sub" in result


# ── pytest_runner ─────────────────────────────────────────────────────────────


def test_pytest_runner_passing_project(passing_project: Path):
    result = run_pytest(str(passing_project))
    assert isinstance(result, PytestRunResult)
    assert result.exit_code == 0
    assert result.passed >= 1
    assert result.failed == 0
    assert result.failures == []


def test_pytest_runner_failing_project(failing_project: Path):
    result = run_pytest(str(failing_project))
    assert result.exit_code != 0
    assert result.failed >= 1
    assert len(result.failures) >= 1
    assert result.failures[0]["nodeid"]


def test_pytest_runner_empty_project(tmp_path: Path):
    result = run_pytest(str(tmp_path))
    # exit code 5 = no tests collected
    assert result.exit_code == 5 or result.total == 0


def test_pytest_runner_timed_out(tmp_path: Path, monkeypatch):
    import subprocess

    from retrai.tools import pytest_runner

    monkeypatch.setattr(
        pytest_runner.subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("pytest", 1)),
    )
    result = run_pytest(str(tmp_path))
    assert result.timed_out is True
    assert result.exit_code == -1
