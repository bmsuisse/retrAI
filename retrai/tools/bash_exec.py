"""Async bash execution tool."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class BashResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


async def bash_exec(
    command: str,
    cwd: str,
    timeout: float = 60.0,
    env: dict[str, str] | None = None,
) -> BashResult:
    """Run a shell command asynchronously with timeout and cwd.

    Returns a BashResult with stdout, stderr, returncode, and timed_out flag.
    """
    import os

    merged_env = {**os.environ, **(env or {})}

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=merged_env,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return BashResult(stdout="", stderr="", returncode=-1, timed_out=True)

        return BashResult(
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            returncode=proc.returncode or 0,
        )
    except Exception as e:
        return BashResult(stdout="", stderr=str(e), returncode=-1)
