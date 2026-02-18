"""Tests for the sandboxed JavaScript/TypeScript execution tool."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from retrai.tools.js_exec import (
    JsResult,
    _build_sandbox_env,
    _ensure_js_sandbox,
    _js_sandbox_dir,
    js_exec,
)


# ── js_sandbox_dir ────────────────────────────────────────────────────────────


def test_js_sandbox_dir_path(tmp_path: Path) -> None:
    result = _js_sandbox_dir(str(tmp_path))
    assert result == tmp_path / ".retrai" / "js-sandbox"


# ── ensure_js_sandbox ─────────────────────────────────────────────────────────


def test_ensure_js_sandbox_creates_package_json(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "js-sandbox"
    bun = _ensure_js_sandbox(sandbox)
    assert bun.exists()
    assert (sandbox / "package.json").exists()
    assert "retrai-sandbox" in (sandbox / "package.json").read_text()


def test_ensure_js_sandbox_reuses_existing(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "js-sandbox"
    bun1 = _ensure_js_sandbox(sandbox)
    bun2 = _ensure_js_sandbox(sandbox)
    assert bun1 == bun2


# ── build_sandbox_env ─────────────────────────────────────────────────────────


def test_build_sandbox_env_excludes_secrets(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "js-sandbox"
    os.environ["SUPER_SECRET_TOKEN"] = "hunter2"
    try:
        env = _build_sandbox_env(sandbox)
        assert "SUPER_SECRET_TOKEN" not in env
        assert "NODE_PATH" in env
        assert "node_modules" in env["NODE_PATH"]
    finally:
        del os.environ["SUPER_SECRET_TOKEN"]


def test_build_sandbox_env_passes_safe_vars(tmp_path: Path) -> None:
    sandbox = tmp_path / ".retrai" / "js-sandbox"
    env = _build_sandbox_env(sandbox)
    if "HOME" in os.environ:
        assert env["HOME"] == os.environ["HOME"]


# ── js_exec ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_js_exec_basic(tmp_path: Path) -> None:
    result = await js_exec('console.log("hello bun")', cwd=str(tmp_path))
    assert isinstance(result, JsResult)
    assert result.returncode == 0
    assert "hello bun" in result.stdout
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_js_exec_stderr(tmp_path: Path) -> None:
    code = 'console.error("err output")'
    result = await js_exec(code, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "err output" in result.stderr


@pytest.mark.asyncio
async def test_js_exec_exit_code(tmp_path: Path) -> None:
    result = await js_exec("process.exit(42)", cwd=str(tmp_path))
    assert result.returncode == 42


@pytest.mark.asyncio
async def test_js_exec_timeout(tmp_path: Path) -> None:
    result = await js_exec(
        "while(true) {}",
        cwd=str(tmp_path),
        timeout=0.5,
    )
    assert result.timed_out is True
    assert result.returncode == -1


@pytest.mark.asyncio
async def test_js_exec_syntax_error(tmp_path: Path) -> None:
    result = await js_exec("function bad( {}", cwd=str(tmp_path))
    assert result.returncode != 0


@pytest.mark.asyncio
async def test_js_exec_cwd_respected(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("found_it_js")
    code = """
const fs = require("fs");
const data = fs.readFileSync("data.txt", "utf8");
console.log(data);
"""
    result = await js_exec(code, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "found_it_js" in result.stdout


@pytest.mark.asyncio
async def test_js_exec_no_host_env_vars(tmp_path: Path) -> None:
    """Verify that host env vars like API keys are NOT visible in sandbox."""
    os.environ["_RETRAI_JS_TEST_SECRET"] = "should_not_leak"
    try:
        code = 'console.log(process.env._RETRAI_JS_TEST_SECRET || "MISSING")'
        result = await js_exec(code, cwd=str(tmp_path))
        assert result.returncode == 0
        assert "MISSING" in result.stdout
        assert "should_not_leak" not in result.stdout
    finally:
        del os.environ["_RETRAI_JS_TEST_SECRET"]


@pytest.mark.asyncio
async def test_js_exec_typescript(tmp_path: Path) -> None:
    """Bun should run TypeScript code natively."""
    code = """
const greet = (name: string): string => `Hello, ${name}!`;
console.log(greet("retrAI"));
"""
    result = await js_exec(code, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "Hello, retrAI!" in result.stdout


@pytest.mark.asyncio
async def test_js_exec_temp_script_cleaned_up(tmp_path: Path) -> None:
    await js_exec('console.log("cleanup")', cwd=str(tmp_path))
    leftover = list(tmp_path.glob("_retrai_js_exec_*.ts"))
    assert leftover == []


@pytest.mark.asyncio
async def test_js_exec_sandbox_reused(tmp_path: Path) -> None:
    result1 = await js_exec('console.log("first")', cwd=str(tmp_path))
    assert result1.returncode == 0

    result2 = await js_exec('console.log("second")', cwd=str(tmp_path))
    assert result2.returncode == 0
    assert "second" in result2.stdout
