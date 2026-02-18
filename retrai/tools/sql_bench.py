"""SQL bench tool — run, explain, and profile SQL queries on Databricks or SQLAlchemy."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_FILE = ".retrai.yml"


# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class QueryResult:
    """Result of running a SQL query."""

    elapsed_ms: list[float] = field(default_factory=list)
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    sample_rows: list[list[Any]] = field(default_factory=list)
    warmup_ms: float | None = None
    error: str | None = None


@dataclass
class ExplainResult:
    """Result of EXPLAIN on a query."""

    plan_text: str = ""
    plan_type: str = "unknown"  # "extended", "analyze", "query_plan"
    error: str | None = None


@dataclass
class TableProfile:
    """Profiling data for a single table."""

    table_name: str = ""
    row_count: int | None = None
    columns: list[dict[str, str]] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    size_bytes: int | None = None
    partitions: list[str] = field(default_factory=list)
    error: str | None = None


# ── Connection helpers ────────────────────────────────────────────────────────


def _load_config(cwd: str) -> dict[str, Any]:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _detect_backend(cfg: dict[str, Any]) -> str:
    """Detect whether to use 'databricks' or 'sqlalchemy' backend."""
    explicit = cfg.get("backend", "").lower()
    if explicit in ("databricks", "sqlalchemy"):
        return explicit
    dsn = cfg.get("dsn", "")
    if isinstance(dsn, str) and dsn.startswith("databricks://"):
        return "databricks"
    if cfg.get("server_hostname") or cfg.get("http_path"):
        return "databricks"
    return "sqlalchemy"


class _SqlAlchemyBackend:
    """Execute queries via SQLAlchemy."""

    def __init__(self, dsn: str) -> None:
        from sqlalchemy import create_engine

        self._engine = create_engine(dsn)

    def execute(self, query: str) -> tuple[list[str], list[list[Any]]]:
        from sqlalchemy import text

        with self._engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys()) if result.returns_rows else []
            rows = [list(r) for r in result.fetchall()] if result.returns_rows else []
        return columns, rows

    def explain(self, query: str) -> str:
        """Run EXPLAIN on the query. SQLite uses EXPLAIN QUERY PLAN."""
        dialect = self._engine.dialect.name
        if dialect == "sqlite":
            explain_sql = f"EXPLAIN QUERY PLAN {query}"
        else:
            explain_sql = f"EXPLAIN ANALYZE {query}"
        _, rows = self.execute(explain_sql)
        return "\n".join(" | ".join(str(c) for c in row) for row in rows)

    def describe_table(self, table: str) -> tuple[list[dict[str, str]], dict[str, str]]:
        """Get column info and properties for a table."""
        dialect = self._engine.dialect.name
        if dialect == "sqlite":
            _, rows = self.execute(f"PRAGMA table_info({table})")
            columns = [
                {"name": str(r[1]), "type": str(r[2]), "nullable": str(r[3] == 0)} for r in rows
            ]
            return columns, {}
        else:
            from sqlalchemy import inspect as sa_inspect

            inspector = sa_inspect(self._engine)
            cols = inspector.get_columns(table)
            columns = [
                {
                    "name": c["name"],
                    "type": str(c["type"]),
                    "nullable": str(c.get("nullable", True)),
                }
                for c in cols
            ]
            return columns, {}

    def row_count(self, table: str) -> int:
        _, rows = self.execute(f"SELECT COUNT(*) FROM {table}")
        return int(rows[0][0]) if rows else 0

    def close(self) -> None:
        self._engine.dispose()


class _DatabricksBackend:
    """Execute queries via Databricks SQL Connector."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        import os

        from databricks import sql as dbsql

        host = cfg.get("server_hostname") or os.getenv("DATABRICKS_HOST", "")
        http_path = cfg.get("http_path") or os.getenv("DATABRICKS_HTTP_PATH", "")
        token = cfg.get("token") or os.getenv("DATABRICKS_TOKEN")

        connect_kwargs: dict[str, Any] = {
            "server_hostname": host,
            "http_path": http_path,
        }
        if token:
            connect_kwargs["access_token"] = token

        self._connection = dbsql.connect(**connect_kwargs)

    def execute(self, query: str) -> tuple[list[str], list[list[Any]]]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(query)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [list(r) for r in cursor.fetchall()]
            else:
                columns, rows = [], []
        finally:
            cursor.close()
        return columns, rows

    def explain(self, query: str) -> str:
        """Run EXPLAIN EXTENDED on the query."""
        _, rows = self.execute(f"EXPLAIN EXTENDED {query}")
        return "\n".join(" | ".join(str(c) for c in row) for row in rows)

    def describe_table(self, table: str) -> tuple[list[dict[str, str]], dict[str, str]]:
        """Get column info and table properties."""
        # DESCRIBE EXTENDED
        _, desc_rows = self.execute(f"DESCRIBE EXTENDED {table}")
        columns: list[dict[str, str]] = []
        properties: dict[str, str] = {}
        in_props = False
        for row in desc_rows:
            name = str(row[0]).strip() if row[0] else ""
            if name == "" or name.startswith("#"):
                in_props = True
                continue
            if in_props and name:
                properties[name] = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            elif not in_props:
                col_type = str(row[1]).strip() if len(row) > 1 and row[1] else "unknown"
                comment = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                columns.append({"name": name, "type": col_type, "comment": comment})

        # SHOW TABLE PROPERTIES
        try:
            _, prop_rows = self.execute(f"SHOW TBLPROPERTIES {table}")
            for row in prop_rows:
                if len(row) >= 2:
                    properties[str(row[0])] = str(row[1])
        except Exception:
            pass  # Not all tables support SHOW TBLPROPERTIES

        return columns, properties

    def row_count(self, table: str) -> int:
        _, rows = self.execute(f"SELECT COUNT(*) FROM {table}")
        return int(rows[0][0]) if rows else 0

    def close(self) -> None:
        self._connection.close()


def _create_backend(cfg: dict[str, Any]) -> _SqlAlchemyBackend | _DatabricksBackend:
    """Factory: create the appropriate backend from config."""
    backend_type = _detect_backend(cfg)
    if backend_type == "databricks":
        return _DatabricksBackend(cfg)
    dsn = cfg.get("dsn", "")
    if not dsn:
        raise ValueError("No 'dsn' configured for SQLAlchemy backend in .retrai.yml")
    return _SqlAlchemyBackend(dsn)


# ── Core actions ──────────────────────────────────────────────────────────────


def _run_query_sync(
    backend: _SqlAlchemyBackend | _DatabricksBackend,
    query: str,
    iterations: int = 1,
    warmup: bool = False,
    sample_limit: int = 5,
) -> QueryResult:
    """Execute a query multiple times and collect timing data."""
    result = QueryResult()
    warmup_time: float | None = None

    if warmup:
        try:
            start = time.perf_counter()
            backend.execute(query)
            warmup_time = (time.perf_counter() - start) * 1000
            result.warmup_ms = warmup_time
        except Exception as e:
            result.error = f"Warmup failed: {e}"
            return result

    for _ in range(iterations):
        try:
            start = time.perf_counter()
            columns, rows = backend.execute(query)
            elapsed = (time.perf_counter() - start) * 1000
            result.elapsed_ms.append(round(elapsed, 2))
            result.columns = columns
            result.row_count = len(rows)
            result.sample_rows = [[str(c) for c in row] for row in rows[:sample_limit]]
        except Exception as e:
            result.error = f"Query execution failed: {e}"
            return result

    if result.elapsed_ms:
        result.avg_ms = round(sum(result.elapsed_ms) / len(result.elapsed_ms), 2)
        result.min_ms = round(min(result.elapsed_ms), 2)
        result.max_ms = round(max(result.elapsed_ms), 2)

    return result


def _explain_query_sync(
    backend: _SqlAlchemyBackend | _DatabricksBackend,
    query: str,
) -> ExplainResult:
    """Get the execution plan for a query."""
    try:
        plan_text = backend.explain(query)
        plan_type = "query_plan"
        if isinstance(backend, _DatabricksBackend):
            plan_type = "extended"
        elif hasattr(backend, "_engine"):
            dialect = backend._engine.dialect.name
            plan_type = "sqlite_plan" if dialect == "sqlite" else "analyze"
        return ExplainResult(plan_text=plan_text, plan_type=plan_type)
    except Exception as e:
        return ExplainResult(error=f"EXPLAIN failed: {e}")


def _profile_table_sync(
    backend: _SqlAlchemyBackend | _DatabricksBackend,
    table: str,
) -> TableProfile:
    """Profile a table: schema, row count, properties."""
    profile = TableProfile(table_name=table)
    try:
        columns, properties = backend.describe_table(table)
        profile.columns = columns
        profile.properties = properties
    except Exception as e:
        profile.error = f"DESCRIBE failed: {e}"
        return profile

    try:
        profile.row_count = backend.row_count(table)
    except Exception as e:
        logger.warning("Could not count rows for %s: %s", table, e)

    # Try to extract size from properties (Databricks)
    size_str = properties.get("size", "") or properties.get("totalSize", "")
    if size_str:
        try:
            profile.size_bytes = int(size_str)
        except (ValueError, TypeError):
            pass

    # Partitions (Databricks only)
    if isinstance(backend, _DatabricksBackend):
        try:
            _, part_rows = backend.execute(f"SHOW PARTITIONS {table}")
            profile.partitions = [str(row[0]) for row in part_rows[:50]]
        except Exception:
            pass  # Table may not be partitioned

    return profile


# ── Public async API (agent-callable) ─────────────────────────────────────────


async def sql_bench(
    action: str,
    cwd: str,
    query: str = "",
    table: str = "",
    iterations: int = 1,
    warmup: bool = False,
) -> str:
    """Run SQL benchmarks, explain queries, or profile tables.

    Args:
        action: One of "run_query", "explain_query", "profile_table".
        cwd: Working directory (must contain .retrai.yml with connection config).
        query: SQL query string (required for run_query and explain_query).
        table: Table name (required for profile_table).
        iterations: Number of times to run the query (run_query only).
        warmup: Whether to run a warmup iteration before timing (run_query only).

    Returns:
        JSON string with structured results.
    """
    cfg = _load_config(cwd)
    action = action.lower().strip()

    try:
        backend = _create_backend(cfg)
    except ImportError as e:
        return json.dumps(
            {
                "error": (f"Missing dependency: {e}. Install with: uv pip install 'retrai[sql]'"),
            }
        )
    except Exception as e:
        return json.dumps({"error": f"Connection failed: {e}"})

    loop = asyncio.get_event_loop()

    try:
        if action == "run_query":
            if not query:
                return json.dumps({"error": "No query provided for run_query"})
            result = await loop.run_in_executor(
                None,
                _run_query_sync,
                backend,
                query,
                iterations,
                warmup,
            )
            return json.dumps({"action": "run_query", **asdict(result)}, default=str)

        elif action == "explain_query":
            if not query:
                return json.dumps({"error": "No query provided for explain_query"})
            result = await loop.run_in_executor(
                None,
                _explain_query_sync,
                backend,
                query,
            )
            return json.dumps({"action": "explain_query", **asdict(result)}, default=str)

        elif action == "profile_table":
            if not table:
                return json.dumps({"error": "No table name provided for profile_table"})
            result = await loop.run_in_executor(
                None,
                _profile_table_sync,
                backend,
                table,
            )
            return json.dumps({"action": "profile_table", **asdict(result)}, default=str)

        else:
            return json.dumps(
                {
                    "error": f"Unknown action '{action}'. Use: run_query, explain_query, profile_table",
                }
            )
    finally:
        try:
            backend.close()
        except Exception:
            pass
