"""LSP Client implementation.

Handles the JSON-RPC 2.0 protocol over stdio with a subprocess.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Any

# Configure logging to print to stderr for now
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)


class LSPClient:
    """A client for a Language Server Protocol (LSP) server."""

    def __init__(self, command: list[str], root_uri: str):
        self.command = command
        self.root_uri = root_uri
        self.process: subprocess.Popen | None = None
        self._seq = 1
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the LSP server subprocess."""
        logger.info(f"Starting LSP server: {self.command}")
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # Binary mode for reliable Content-Length parsing
            bufsize=0,
        )

    async def stop(self) -> None:
        """Stop the LSP server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    async def initialize(self) -> dict:
        """Initialize the session."""
        return await self.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": self.root_uri,
                "capabilities": {
                    "textDocument": {
                        "synchronization": {"dynamicRegistration": True},
                        "hover": {"dynamicRegistration": True},
                        "completion": {"dynamicRegistration": True},
                        "definition": {"dynamicRegistration": True},
                        "references": {"dynamicRegistration": True},
                    }
                },
            },
        )

    async def initialized(self) -> None:
        """Send initialized notification."""
        await self.notify("initialized", {})

    async def request(self, method: str, params: dict | None = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        # Note: This is a simplified synchronous implementation for the prototype.
        # A full implementation would use a proper async reader loop.
        # However, since we are inside an async agent tool, we can wrap blocking I/O
        # in run_in_executor if needed, but for now we'll stick to a simple
        # request-response cycle assuming the server replies promptly.
        
        # Real LSP servers might send notifications or log messages interleaved
        # with responses. We need to handle that.
        
        return await asyncio.get_event_loop().run_in_executor(
            None, self._send_and_receive, method, params
        )

    def _send_and_receive(self, method: str, params: dict | None) -> Any:
        """Blocking I/O breakdown of the request-response cycle."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("LSP server not running")

        # 1. Prepare Request
        req_id = self._seq
        self._seq += 1
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
    def _send_and_receive(self, method: str, params: dict | None) -> Any:
        """Blocking I/O breakdown of the request-response cycle."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("LSP server not running")

        # 1. Prepare Request
        req_id = self._seq
        self._seq += 1
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")

        # 2. Send
        self.process.stdin.write(header + body)
        self.process.stdin.flush()

        # 3. Read loop until we get OUR response
        while True:
            # Read header
            content_length = 0
            while True:
                line = self.process.stdout.readline()
                if not line:
                    raise EOFError("Server closed connection")
                line_str = line.decode("ascii").strip()
                if not line_str:
                    break  # End of headers
                if line_str.startswith("Content-Length:"):
                    content_length = int(line_str.split(":")[1].strip())
            
            # Read body
            body_data = self.process.stdout.read(content_length)
            if not body_data:
                raise EOFError("Unexpected EOF reading body")
            
            msg = json.loads(body_data.decode("utf-8"))

            if "id" in msg and msg["id"] == req_id:
                if "error" in msg:
                    raise RuntimeError(f"LSP Error: {msg['error']}")
                return msg.get("result")
            
            # If it's not our response (e.g. logMessage notification), ignore it
            # In a real implementation we would log it.

    async def notify(self, method: str, params: dict | None = None) -> None:
        """Send a notification (no response expected)."""
        if not self.process or not self.process.stdin:
            return

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.process.stdin.write(header + body) or self.process.stdin.flush() # type: ignore
        )
