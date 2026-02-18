"""Sandboxed JavaScript/TypeScript execution via Bun subprocess."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class JsResult:
    """Result of a sandboxed JS/TS execution."""

    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


# Minimal allowlist of env vars passed to the sandbox process.
_SAFE_ENV_KEYS: frozenset[str] = frozenset({
    "HOME",
    "USER",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
})


def _js_sandbox_dir(cwd: str) -> Path:
    """Return the JS sandbox path inside the project."""
    return Path(cwd).resolve() / ".retrai" / "js-sandbox"


def _has_bun() -> bool:
    """Check if bun is available on PATH."""
    return shutil.which("bun") is not None


def _auto_install_bun() -> str | None:
    """Auto-install bun if not present. Returns the bun binary path or None."""
    import subprocess

    try:
        # Try the official install script
        result = subprocess.run(
            ["bash", "-c", "curl -fsSL https://bun.sh/install | bash"],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            # Bun installs to ~/.bun/bin/bun
            home = Path.home()
            bun_path = home / ".bun" / "bin" / "bun"
            if bun_path.exists():
                return str(bun_path)
    except Exception:
        pass

    # Try npm as fallback
    npm = shutil.which("npm")
    if npm:
        try:
            subprocess.run(
                [npm, "install", "-g", "bun"],
                capture_output=True,
                timeout=120,
            )
            found = shutil.which("bun")
            if found:
                return found
        except Exception:
            pass

    return None


def _ensure_js_sandbox(sandbox: Path) -> Path:
    """Create the JS sandbox directory with a package.json if needed.

    Auto-installs bun if not found on PATH.
    Returns the path to the bun binary.
    """
    bun = shutil.which("bun")

    if bun is None:
        # Check ~/.bun/bin (common install location)
        home_bun = Path.home() / ".bun" / "bin" / "bun"
        if home_bun.exists():
            bun = str(home_bun)
        else:
            # Auto-install
            bun = _auto_install_bun()

    if bun is None:
        raise RuntimeError(
            "Could not install bun automatically. "
            "Install manually: curl -fsSL https://bun.sh/install | bash"
        )

    if not (sandbox / "package.json").exists():
        sandbox.mkdir(parents=True, exist_ok=True)
        (sandbox / "package.json").write_text('{"name": "retrai-sandbox", "private": true}\n')

    return Path(bun)


async def _install_packages(
    bun: Path,
    packages: list[str],
    sandbox: Path,
    timeout: float = 60.0,
) -> tuple[str, bool]:
    """Install npm packages into the JS sandbox. Returns (output, had_error)."""
    proc = await asyncio.create_subprocess_exec(
        str(bun), "add", *packages,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(sandbox),
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return "Package installation timed out", True

    if proc.returncode != 0:
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")
        return f"bun add failed (exit {proc.returncode}): {stderr_str}", True

    return "", False


def _build_sandbox_env(sandbox: Path) -> dict[str, str]:
    """Build a restricted env dict for the sandbox subprocess."""
    env: dict[str, str] = {}

    # Copy only safe env vars from host
    for key in _SAFE_ENV_KEYS:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val

    # Set node paths so require/import finds sandbox node_modules
    env["NODE_PATH"] = str(sandbox / "node_modules")
    env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

    # Add bun to PATH if it's in a non-standard location
    bun_path = shutil.which("bun")
    if bun_path:
        bun_dir = str(Path(bun_path).parent)
        env["PATH"] = bun_dir + os.pathsep + env["PATH"]

    return env


async def js_exec(
    code: str,
    cwd: str,
    packages: list[str] | None = None,
    timeout: float = 30.0,
) -> JsResult:
    """Execute JavaScript/TypeScript code in an isolated Bun sandbox.

    The sandbox lives at ``<cwd>/.retrai/js-sandbox/`` and is lazily
    created on first use.  A restricted set of environment variables is
    passed to the subprocess so that host secrets (API keys, tokens, etc.)
    are **not** leaked into the sandbox.

    Bun runs TypeScript natively — you can pass TS code directly.

    Args:
        code: JavaScript or TypeScript source code to execute.
        cwd: Project working directory (sandbox is created relative to this).
        packages: Optional list of npm packages to install before execution.
        timeout: Max seconds for the code execution (default 30).

    Returns:
        A ``JsResult`` with stdout, stderr, returncode, and timed_out flag.
    """
    sandbox = _js_sandbox_dir(cwd)
    bun = _ensure_js_sandbox(sandbox)

    # Install requested packages
    if packages:
        pkg_out, pkg_err = await _install_packages(bun, packages, sandbox)
        if pkg_err:
            return JsResult(stdout="", stderr=pkg_out, returncode=-1)

    # Write code to a temporary .ts file (Bun handles TS natively)
    script_fd, script_path = tempfile.mkstemp(
        suffix=".ts", prefix="_retrai_js_exec_", dir=cwd
    )
    try:
        with os.fdopen(script_fd, "w") as f:
            f.write(code)

        env = _build_sandbox_env(sandbox)

        proc = await asyncio.create_subprocess_exec(
            str(bun), "run", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return JsResult(
                stdout="", stderr="", returncode=-1, timed_out=True
            )

        return JsResult(
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
