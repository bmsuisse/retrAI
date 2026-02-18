"""LSP Tool wrapper."""

from __future__ import annotations

import logging
import os
from typing import Any

from retrai.tools.base import BaseTool, ToolSchema
from retrai.tools.lsp.manager import LSPManager

logger = logging.getLogger(__name__)


class LSPTool(BaseTool):
    """Query the Language Server for definitions, references, etc."""

    name = "lsp_query"
    parallel_safe = False  # Keep sequential for now to avoid race conditions in prototype

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=(
                "Query the Language Server Protocol (LSP) for code intelligence. "
                "Supported actions: 'definition', 'references', 'hover'. "
                "Requires 'path', 'line' (1-indexed), and 'character' (0-indexed)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["definition", "references", "hover"],
                        "description": "The LSP action to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path relative to project root",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number (1-indexed)",
                    },
                    "character": {
                        "type": "integer",
                        "description": "Column number (0-indexed)",
                        "default": 0,
                    },
                },
                "required": ["action", "path", "line"],
            },
        )

    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        action = args["action"]
        path = args["path"]
        line = args["line"] - 1  # LSP is 0-indexed for lines
        character = args.get("character", 0)

        manager = LSPManager.get_instance()
        
        try:
            client = await manager.get_client(cwd, "python")
        except FileNotFoundError:
             return (
                 "Error: pyright-langserver not found. "
                 "Please install with `pip install pyright` or `npm install -g pyright`."
             ), True
        except Exception as e:
            return f"Error starting LSP: {e}", True

        file_uri = f"file://{cwd}/{path}"
        
        # Open the file if needed (Pyright sometimes needs this for single-file analysis 
        # or if background analysis isn't finished)
        try:
            with open(os.path.join(cwd, path), encoding="utf-8") as f:
                text = f.read()
            
            await client.notify("textDocument/didOpen", {
                "textDocument": {
                    "uri": file_uri,
                    "languageId": "python",
                    "version": 1,
                    "text": text
                }
            })
        except Exception as e:
            logger.warning(f"Failed to open file for LSP: {e}")
        
        params = {
            "textDocument": {"uri": file_uri},
            "position": {"line": line, "character": character},
        }

        try:
            if action == "definition":
                res = await client.request("textDocument/definition", params)
                return self._format_location_result(res, cwd), False
            
            elif action == "references":
                # references needs context
                params["context"] = {"includeDeclaration": True}
                res = await client.request("textDocument/references", params)
                return self._format_location_result(res, cwd), False
            
            elif action == "hover":
                res = await client.request("textDocument/hover", params)
                if not res:
                    return "No hover info found.", False
                contents = res.get("contents", "")
                if isinstance(contents, dict):
                    return contents.get("value", ""), False
                return str(contents), False

            else:
                return f"Unknown action: {action}", True

        except Exception as e:
            return f"LSP Request Failed: {e}", True

    def _format_location_result(self, res: Any, cwd: str) -> str:
        if not res:
            return "No results found."
        
        if isinstance(res, dict):
            res = [res]
            
        output = []
        for loc in res:
            uri = loc.get("uri", "")
            if uri.startswith("file://"):
                path = uri[len("file://"):]
                # Make relative if inside cwd
                if path.startswith(cwd):
                    path = path[len(cwd):].lstrip("/")
            else:
                path = uri
            
            rng = loc.get("range", {})
            start = rng.get("start", {})
            end = rng.get("end", {})
            
            output.append(
                f"{path}:{start.get('line', 0)+1}:{start.get('character', 0)} - "
                f"{end.get('line', 0)+1}:{end.get('character', 0)}"
            )
            
        return "\n".join(output)
