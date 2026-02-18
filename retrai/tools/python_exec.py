"""Sandboxed Python execution via isolated venv subprocess."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PythonResult:
    """Result of a sandboxed Python execution."""

    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


# Minimal allowlist of env vars passed to the sandbox process.
_SAFE_ENV_KEYS: frozenset[str] = frozenset(
    {
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "TERM",
        "TMPDIR",
    }
)


def _sandbox_dir(cwd: str) -> Path:
    """Return the sandbox venv path inside the project."""
    return Path(cwd).resolve() / ".retrai" / "sandbox"


def _has_uv() -> bool:
    """Check if uv is available on PATH."""
    return shutil.which("uv") is not None


def _auto_install_uv() -> bool:
    """Auto-install uv if not present. Returns True on success."""
    import subprocess

    try:
        result = subprocess.run(
            ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            # uv installs to ~/.local/bin or ~/.cargo/bin
            home = Path.home()
            for candidate in [
                home / ".local" / "bin" / "uv",
                home / ".cargo" / "bin" / "uv",
            ]:
                if candidate.exists():
                    return True
    except Exception:
        pass
    return False


def _find_uv() -> str | None:
    """Find uv binary, checking common install locations."""
    found = shutil.which("uv")
    if found:
        return found

    home = Path.home()
    for candidate in [
        home / ".local" / "bin" / "uv",
        home / ".cargo" / "bin" / "uv",
    ]:
        if candidate.exists():
            return str(candidate)

    return None


def _ensure_venv(sandbox: Path) -> Path:
    """Create the sandbox venv if it doesn't exist. Returns the python binary path."""
    python = sandbox / "bin" / "python"
    if python.exists():
        return python

    sandbox.parent.mkdir(parents=True, exist_ok=True)

    uv = _find_uv()
    if uv is None:
        # Auto-install uv
        if _auto_install_uv():
            uv = _find_uv()

    if uv:
        # Prefer uv — avoids ensurepip/dyld issues with uv-managed Pythons
        import subprocess

        subprocess.run(
            [uv, "venv", str(sandbox)],
            check=True,
            capture_output=True,
        )
    else:
        # Fallback to stdlib venv (without pip to avoid ensurepip issues)
        import venv

        venv.create(str(sandbox), with_pip=False, clear=False)

    if not python.exists():
        raise RuntimeError(f"Failed to create sandbox venv at {sandbox}")

    return python


async def _install_packages(
    packages: list[str],
    sandbox: Path,
    cwd: str,
    timeout: float = 120.0,
) -> tuple[str, bool]:
    """Install packages into the sandbox venv. Returns (output, had_error)."""
    uv = _find_uv()
    if uv:
        cmd = [uv, "pip", "install", "--python", str(sandbox / "bin" / "python"), *packages]
    else:
        cmd = [str(sandbox / "bin" / "python"), "-m", "pip", "install", "--quiet", *packages]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return "Package installation timed out", True

    if proc.returncode != 0:
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")
        return f"pip install failed (exit {proc.returncode}): {stderr_str}", True

    return "", False


def _build_sandbox_env(sandbox: Path) -> dict[str, str]:
    """Build a restricted env dict for the sandbox subprocess."""
    env: dict[str, str] = {}

    # Copy only safe env vars from host
    for key in _SAFE_ENV_KEYS:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val

    # Set venv paths
    env["VIRTUAL_ENV"] = str(sandbox)
    env["PATH"] = str(sandbox / "bin") + os.pathsep + "/usr/bin:/bin:/usr/sbin:/sbin"

    return env


async def python_exec(
    code: str,
    cwd: str,
    packages: list[str] | None = None,
    timeout: float = 30.0,
) -> PythonResult:
    """Execute Python code in an isolated sandbox venv.

    The sandbox venv lives at ``<cwd>/.retrai/sandbox/`` and is lazily
    created on first use.  A restricted set of environment variables is
    passed to the subprocess so that host secrets (API keys, tokens, etc.)
    are **not** leaked into the sandbox.

    Args:
        code: Python source code to execute.
        cwd: Project working directory (sandbox is created relative to this).
        packages: Optional list of pip packages to install before execution.
        timeout: Max seconds for the code execution (default 30).

    Returns:
        A ``PythonResult`` with stdout, stderr, returncode, and timed_out flag.
    """
    sandbox = _sandbox_dir(cwd)
    python = _ensure_venv(sandbox)

    # Install requested packages
    if packages:
        pip_out, pip_err = await _install_packages(packages, sandbox, cwd)
        if pip_err:
            return PythonResult(stdout="", stderr=pip_out, returncode=-1)

    # Write code to a temporary file inside the project dir
    script_fd, script_path = tempfile.mkstemp(suffix=".py", prefix="_retrai_exec_", dir=cwd)
    try:
        with os.fdopen(script_fd, "w") as f:
            f.write(code)

        env = _build_sandbox_env(sandbox)

        proc = await asyncio.create_subprocess_exec(
            str(python),
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return PythonResult(stdout="", stderr="", returncode=-1, timed_out=True)

        return PythonResult(
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            returncode=proc.returncode or 0,
        )
    finally:
        # Clean up temp script
        try:
            os.unlink(script_path)
        except OSError:
            pass
