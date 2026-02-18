"""Tests for the sandboxed Python execution tool."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from retrai.tools.python_exec import (
    PythonResult,
    _build_sandbox_env,
    _ensure_venv,
    _sandbox_dir,
    python_exec,
)

# ── sandbox_dir ───────────────────────────────────────────────────────────────


def test_sandbox_dir_path(tmp_path: Path) -> None:
    result = _sandbox_dir(str(tmp_path))
    assert result == tmp_path / ".retrai" / "sandbox"


# ── ensure_venv ───────────────────────────────────────────────────────────────


def test_ensure_venv_creates_python(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "sandbox"
    python = _ensure_venv(sandbox)
    assert python.exists()
    assert python.name == "python"


def test_ensure_venv_reuses_existing(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "sandbox"
    python1 = _ensure_venv(sandbox)
    python2 = _ensure_venv(sandbox)
    assert python1 == python2


# ── build_sandbox_env ─────────────────────────────────────────────────────────


def test_build_sandbox_env_excludes_secrets(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "sandbox"
    # Set a secret-like env var on the host
    os.environ["SUPER_SECRET_API_KEY"] = "hunter2"
    try:
        env = _build_sandbox_env(sandbox)
        assert "SUPER_SECRET_API_KEY" not in env
        assert "VIRTUAL_ENV" in env
        assert str(sandbox) in env["PATH"]
    finally:
        del os.environ["SUPER_SECRET_API_KEY"]


def test_build_sandbox_env_passes_safe_vars(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "sandbox"
    env = _build_sandbox_env(sandbox)
    # HOME should be present if it's in the host env
    if "HOME" in os.environ:
        assert env["HOME"] == os.environ["HOME"]


# ── python_exec ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_python_exec_basic(tmp_path: Path) -> None:
    result = await python_exec('print("hello sandbox")', cwd=str(tmp_path))
    assert isinstance(result, PythonResult)
    assert result.returncode == 0
    assert "hello sandbox" in result.stdout
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_python_exec_stderr(tmp_path: Path) -> None:
    code = 'import sys; print("err", file=sys.stderr)'
    result = await python_exec(code, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "err" in result.stderr


@pytest.mark.asyncio
async def test_python_exec_exit_code(tmp_path: Path) -> None:
    result = await python_exec("import sys; sys.exit(42)", cwd=str(tmp_path))
    assert result.returncode == 42


@pytest.mark.asyncio
async def test_python_exec_timeout(tmp_path: Path) -> None:
    result = await python_exec(
        "import time; time.sleep(60)",
        cwd=str(tmp_path),
        timeout=0.5,
    )
    assert result.timed_out is True
    assert result.returncode == -1


@pytest.mark.asyncio
async def test_python_exec_syntax_error(tmp_path: Path) -> None:
    result = await python_exec("def bad(:\n  pass", cwd=str(tmp_path))
    assert result.returncode != 0
    assert "SyntaxError" in result.stderr


@pytest.mark.asyncio
async def test_python_exec_cwd_respected(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("found_it")
    code = 'print(open("data.txt").read())'
    result = await python_exec(code, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "found_it" in result.stdout


@pytest.mark.asyncio
async def test_python_exec_no_host_env_vars(tmp_path: Path) -> None:
    """Verify that host env vars like API keys are NOT visible in sandbox."""
    os.environ["_RETRAI_TEST_SECRET"] = "should_not_leak"
    try:
        code = (
            "import os\n"
            "val = os.environ.get('_RETRAI_TEST_SECRET', 'MISSING')\n"
            "print(val)\n"
        )
        result = await python_exec(code, cwd=str(tmp_path))
        assert result.returncode == 0
        assert "MISSING" in result.stdout
        assert "should_not_leak" not in result.stdout
    finally:
        del os.environ["_RETRAI_TEST_SECRET"]


@pytest.mark.asyncio
async def test_python_exec_venv_reused(tmp_path: Path) -> None:
    """Second call should reuse the same sandbox venv (fast)."""
    result1 = await python_exec("print('first')", cwd=str(tmp_path))
    assert result1.returncode == 0

    result2 = await python_exec("print('second')", cwd=str(tmp_path))
    assert result2.returncode == 0
    assert "second" in result2.stdout

    # Sandbox dir should exist
    assert (tmp_path / ".retrai" / "sandbox" / "bin" / "python").exists()


@pytest.mark.asyncio
async def test_python_exec_temp_script_cleaned_up(tmp_path: Path) -> None:
    """Temp script file should be deleted after execution."""
    await python_exec("print('cleanup')", cwd=str(tmp_path))
    # No _retrai_exec_ files should remain
    leftover = list(tmp_path.glob("_retrai_exec_*.py"))
    assert leftover == []


@pytest.mark.asyncio
async def test_python_exec_multiline_code(tmp_path: Path) -> None:
    code = """\
x = 10
y = 20
print(f"sum={x + y}")
"""
    result = await python_exec(code, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "sum=30" in result.stdout
