"""Dependency graph tool — analyze Python import and call graphs via AST.

Supports:
- ``imports``: Build a module-level import graph for a package directory.
- ``calls``: Build a function call graph within a single .py file.
- ``cycles``: Detect circular import chains in a package.

Output formats: ``json`` (adjacency list), ``mermaid``, ``dot`` (Graphviz).
"""

from __future__ import annotations

import ast
import json
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Import graph ──────────────────────────────────────────────────────────────


def _module_name(path: Path, root: Path) -> str:
    """Convert a file path to a dotted module name relative to root."""
    rel = path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _collect_imports(source: str, module_name: str) -> list[str]:
    """Return list of imported module names from source."""
    imports: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module
                if node.level > 0:
                    # Relative import — resolve against current module
                    parts = module_name.split(".")
                    base_parts = parts[: len(parts) - node.level]
                    if node.module:
                        base_parts.append(node.module)
                    base = ".".join(base_parts)
                imports.append(base)
    return imports


def _build_import_graph(
    root: Path,
    max_depth: int,
) -> dict[str, list[str]]:
    """Walk a package directory and build an import adjacency list."""
    graph: dict[str, list[str]] = defaultdict(list)
    py_files = list(root.rglob("*.py"))

    # Map module names to file paths
    module_to_file: dict[str, Path] = {}
    for f in py_files:
        try:
            name = _module_name(f, root.parent)
            module_to_file[name] = f
        except ValueError:
            continue

    known_modules = set(module_to_file.keys())

    for mod_name, file_path in module_to_file.items():
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        imports = _collect_imports(source, mod_name)
        for imp in imports:
            # Only include imports that are within the package
            if any(imp == km or imp.startswith(km + ".") for km in known_modules):
                # Normalize to the closest known module
                target = imp
                for km in sorted(known_modules, key=len, reverse=True):
                    if imp == km or imp.startswith(km + "."):
                        target = km
                        break
                if target != mod_name and target not in graph[mod_name]:
                    graph[mod_name].append(target)

    return dict(graph)


def _detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles in the import graph using DFS."""
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle — extract it
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                if cycle not in cycles:
                    cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [])

    return cycles


# ── Call graph ────────────────────────────────────────────────────────────────


def _build_call_graph(source: str) -> dict[str, list[str]]:
    """Build a function call graph from Python source using AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"__error__": [str(e)]}

    graph: dict[str, list[str]] = {}
    current_func: list[str] = []

    class CallVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            name = node.name
            if current_func:
                name = f"{current_func[-1]}.{node.name}"
            current_func.append(name)
            graph[name] = []
            self.generic_visit(node)
            current_func.pop()

        visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

        def visit_Call(self, node: ast.Call) -> None:
            if not current_func:
                self.generic_visit(node)
                return
            caller = current_func[-1]
            # Extract callee name
            callee: str | None = None
            if isinstance(node.func, ast.Name):
                callee = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee = node.func.attr
            if callee and callee not in graph.get(caller, []):
                graph.setdefault(caller, []).append(callee)
            self.generic_visit(node)

    CallVisitor().visit(tree)
    return graph


# ── Output formatters ─────────────────────────────────────────────────────────


def _to_mermaid(graph: dict[str, list[str]], title: str = "graph") -> str:
    """Convert adjacency list to Mermaid flowchart syntax."""
    lines = ["graph TD"]
    seen_edges: set[tuple[str, str]] = set()
    for src, targets in sorted(graph.items()):
        src_id = src.replace(".", "_").replace("-", "_")
        for tgt in targets:
            tgt_id = tgt.replace(".", "_").replace("-", "_")
            edge = (src_id, tgt_id)
            if edge not in seen_edges:
                lines.append(f"    {src_id}[\"{src}\"] --> {tgt_id}[\"{tgt}\"]")
                seen_edges.add(edge)
    return "\n".join(lines)


def _to_dot(graph: dict[str, list[str]], title: str = "G") -> str:
    """Convert adjacency list to Graphviz DOT syntax."""
    lines = [f'digraph "{title}" {{', "    rankdir=LR;"]
    seen_edges: set[tuple[str, str]] = set()
    for src, targets in sorted(graph.items()):
        for tgt in targets:
            edge = (src, tgt)
            if edge not in seen_edges:
                lines.append(f'    "{src}" -> "{tgt}";')
                seen_edges.add(edge)
    lines.append("}")
    return "\n".join(lines)


# ── Public async API ──────────────────────────────────────────────────────────


async def dependency_graph(
    action: str,
    path: str,
    cwd: str,
    fmt: str = "json",
    max_depth: int = 3,
) -> str:
    """Analyze Python import/call dependencies.

    Args:
        action: One of ``imports``, ``calls``, ``cycles``.
        path: File or directory path relative to ``cwd``.
        cwd: Working directory.
        fmt: Output format: ``json``, ``mermaid``, or ``dot``.
        max_depth: Max import depth to traverse.

    Returns:
        JSON string with graph data (or diagram string for mermaid/dot).
    """
    action = action.lower().strip()
    fmt = fmt.lower().strip()
    target = Path(cwd) / path

    if not target.exists():
        return json.dumps({"error": f"Path not found: {path}"})

    try:
        if action in ("imports", "cycles"):
            root = target if target.is_dir() else target.parent
            graph = _build_import_graph(root, max_depth)

            if action == "cycles":
                cycles = _detect_cycles(graph)
                return json.dumps(
                    {
                        "action": "cycles",
                        "path": path,
                        "cycle_count": len(cycles),
                        "cycles": cycles,
                        "has_cycles": len(cycles) > 0,
                    },
                    indent=2,
                )

            # imports action
            if fmt == "mermaid":
                diagram = _to_mermaid(graph, title=path)
                return json.dumps(
                    {"action": "imports", "format": "mermaid", "diagram": diagram},
                    indent=2,
                )
            elif fmt == "dot":
                diagram = _to_dot(graph, title=path)
                return json.dumps(
                    {"action": "imports", "format": "dot", "diagram": diagram},
                    indent=2,
                )
            else:
                return json.dumps(
                    {
                        "action": "imports",
                        "path": path,
                        "node_count": len(graph),
                        "edge_count": sum(len(v) for v in graph.values()),
                        "graph": graph,
                    },
                    indent=2,
                )

        elif action == "calls":
            if target.is_dir():
                return json.dumps(
                    {"error": "action 'calls' requires a single .py file, not a directory"}
                )
            source = target.read_text(encoding="utf-8", errors="replace")
            graph = _build_call_graph(source)

            if fmt == "mermaid":
                diagram = _to_mermaid(graph, title=path)
                return json.dumps(
                    {"action": "calls", "format": "mermaid", "diagram": diagram},
                    indent=2,
                )
            elif fmt == "dot":
                diagram = _to_dot(graph, title=path)
                return json.dumps(
                    {"action": "calls", "format": "dot", "diagram": diagram},
                    indent=2,
                )
            else:
                return json.dumps(
                    {
                        "action": "calls",
                        "path": path,
                        "function_count": len(graph),
                        "graph": graph,
                    },
                    indent=2,
                )
        else:
            return json.dumps(
                {
                    "error": (
                        f"Unknown action '{action}'. "
                        "Use: imports, calls, cycles"
                    )
                }
            )

    except Exception as e:
        logger.exception("dependency_graph failed")
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
