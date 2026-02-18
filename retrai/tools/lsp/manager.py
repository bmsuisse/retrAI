"""LSP Manager singleton.

Manages active LSP clients to ensure we don't spawn a new process 
for every tool call.
"""

from __future__ import annotations

import asyncio
import logging

from retrai.tools.lsp.client import LSPClient

logger = logging.getLogger(__name__)


class LSPManager:
    """Singleton manager for LSP clients."""

    _instance: LSPManager | None = None
    _clients: dict[tuple[str, str], LSPClient] = {}  # (cwd, lang) -> Client
    _lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> LSPManager:
        if cls._instance is None:
            cls._instance = LSPManager()
        return cls._instance

    async def get_client(self, cwd: str, lang: str = "python") -> LSPClient:
        """Get or create an LSP client for the given directory and language."""
        key = (cwd, lang)
        async with self._lock:
            if key in self._clients:
                client = self._clients[key]
                if client.process and client.process.poll() is None:
                    return client
                else:
                    # Zombie/dead process, cleanup
                    logger.warning(f"LSP server for {key} is dead, restarting...")
                    await client.stop()
                    del self._clients[key]

            # Create new client
            # Try to find pyright-langserver in the local .venv first
            import os
            venv_bin = os.path.join(cwd, ".venv", "bin", "pyright-langserver")
            if os.path.exists(venv_bin):
                cmd = [venv_bin, "--stdio"]
            else:
                cmd = ["pyright-langserver", "--stdio"]

            client = LSPClient(cmd, f"file://{cwd}")
            await client.start()
            
            try:
                await client.initialize()
                await client.initialized()
            except Exception as e:
                logger.error(f"Failed to initialize LSP: {e}")
                await client.stop()
                raise

            self._clients[key] = client
            return client

    async def shutdown_all(self):
        """Shutdown all active clients."""
        async with self._lock:
            for key, client in self._clients.items():
                logger.info(f"Shutting down LSP for {key}")
                await client.stop()
            self._clients.clear()
