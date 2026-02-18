"""Base tool class and registry for extensible tool management."""

from __future__ import annotations

import importlib.metadata
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


@dataclass
class ToolSchema:
    """JSON-schema description of a tool for the LLM.

    This is what gets sent to the model so it knows
    how to call the tool.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    Subclass this to create a new tool. Each tool bundles:
    - **name** — unique identifier (used in dispatch)
    - **schema** — JSON-schema for the LLM
    - **parallel_safe** — whether it can run concurrently
    - **execute()** — the actual implementation

    Example::

        class MyTool(BaseTool):
            name = "my_tool"
            parallel_safe = True

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name=self.name,
                    description="Does something cool",
                    parameters={
                        "type": "object",
                        "properties": {
                            "input": {"type": "string", "description": "The input"},
                        },
                        "required": ["input"],
                    },
                )

            async def execute(self, args: dict, cwd: str) -> tuple[str, bool]:
                return f"Result for {args['input']}", False
    """

    name: ClassVar[str] = ""
    parallel_safe: ClassVar[bool] = False

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Return the JSON-schema definition for LLM consumption."""
        ...

    @abstractmethod
    async def execute(self, args: dict[str, Any], cwd: str) -> tuple[str, bool]:
        """Execute the tool. Returns ``(content, is_error)``."""
        ...


class ToolRegistry:
    """Registry that maps tool names to ``BaseTool`` instances.

    Tools can be registered:
    1. Programmatically via ``register()``
    2. Via Python entry points (``retrai.tools`` group)

    Example::

        registry = ToolRegistry()
        registry.register(MyTool())

        # Dispatch
        content, err = await registry.dispatch("my_tool", {"input": "hi"}, "/tmp")

        # List definitions for the LLM
        definitions = registry.list_definitions()
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Overwrites if name already exists."""
        if not tool.name:
            raise ValueError(f"{type(tool).__name__} has no 'name' class variable set")
        self._tools[tool.name] = tool

    def register_many(self, tools: list[BaseTool]) -> None:
        """Register multiple tools at once."""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

    # ------------------------------------------------------------------
    # Discovery via entry points
    # ------------------------------------------------------------------

    def discover_plugins(self, group: str = "retrai.tools") -> int:
        """Load tools from installed packages via entry points.

        Each entry point should resolve to either:
        - A ``BaseTool`` *class* (instantiated automatically)
        - A ``BaseTool`` *instance* (registered directly)
        - A *list* of ``BaseTool`` instances

        Returns the number of tools loaded.
        """
        loaded = 0
        try:
            eps = importlib.metadata.entry_points()
            # Python 3.12+: eps is a dict-like with .select()
            tool_eps = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
        except Exception:
            return 0

        for ep in tool_eps:
            try:
                obj = ep.load()
                if isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, BaseTool):
                            self.register(item)
                            loaded += 1
                elif isinstance(obj, BaseTool):
                    self.register(obj)
                    loaded += 1
                elif isinstance(obj, type) and issubclass(obj, BaseTool):
                    self.register(obj())
                    loaded += 1
                else:
                    logger.warning(
                        "Entry point '%s' did not resolve to a BaseTool: %s",
                        ep.name,
                        type(obj),
                    )
            except Exception:
                logger.exception("Failed to load tool entry point '%s'", ep.name)

        if loaded:
            logger.info("Discovered %d plugin tool(s) from '%s'", loaded, group)
        return loaded

    # ------------------------------------------------------------------
    # Lookup & Dispatch
    # ------------------------------------------------------------------

    def get(self, name: str) -> BaseTool | None:
        """Return a tool by name, or ``None``."""
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    async def dispatch(
        self,
        name: str,
        args: dict[str, Any],
        cwd: str,
    ) -> tuple[str, bool]:
        """Dispatch a tool call by name. Returns ``(content, is_error)``."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}", True
        try:
            return await tool.execute(args, cwd)
        except Exception as e:
            return f"Tool error: {type(e).__name__}: {e}", True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_definitions(self) -> list[dict[str, Any]]:
        """Return JSON-schema definitions for all registered tools.

        This is what gets sent to the LLM so it can choose which tools
        to invoke.
        """
        return [tool.get_schema().to_dict() for tool in self._tools.values()]

    def list_names(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def parallel_safe_names(self) -> frozenset[str]:
        """Return the set of tool names that are safe to run in parallel."""
        return frozenset(name for name, tool in self._tools.items() if tool.parallel_safe)
