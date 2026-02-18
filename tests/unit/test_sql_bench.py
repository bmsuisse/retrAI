"""Unit tests for retrai.tools.sql_bench — SQLite backend only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

sa = pytest.importorskip("sqlalchemy")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_config(tmp_path: Path, db_name: str = "test.db", **extra: object) -> Path:
    """Write a .retrai.yml pointing at an SQLite DB inside tmp_path."""
    db_path = tmp_path / db_name
    lines = [
        f"dsn: 'sqlite:///{db_path}'",
        *(f"{k}: {v!r}" for k, v in extra.items()),
    ]
    cfg = tmp_path / ".retrai.yml"
    cfg.write_text("\n".join(lines) + "\n")
    return db_path


def _seed_table(db_path: Path) -> None:
    """Create a tiny 'metrics' table in the SQLite DB."""
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY, name TEXT, value REAL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO metrics (name, value) VALUES "
                "('latency', 42.5), ('throughput', 1000.0), ('errors', 0.1)"
            )
        )
    engine.dispose()


# ── run_query tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_query_basic(tmp_path: Path) -> None:
    """run_query on a simple SELECT returns timing and sample data."""
    from retrai.tools.sql_bench import sql_bench

    db = _write_config(tmp_path)
    _seed_table(db)

    raw = await sql_bench(action="run_query", cwd=str(tmp_path), query="SELECT * FROM metrics")
    data = json.loads(raw)

    assert data["action"] == "run_query"
    assert data["error"] is None
    assert data["row_count"] == 3
    assert len(data["columns"]) > 0
    assert len(data["elapsed_ms"]) == 1
    assert data["avg_ms"] > 0


@pytest.mark.asyncio
async def test_run_query_multiple_iterations(tmp_path: Path) -> None:
    """Multiple iterations populate min/max/avg correctly."""
    from retrai.tools.sql_bench import sql_bench

    db = _write_config(tmp_path)
    _seed_table(db)

    raw = await sql_bench(
        action="run_query",
        cwd=str(tmp_path),
        query="SELECT 1",
        iterations=3,
    )
    data = json.loads(raw)

    assert len(data["elapsed_ms"]) == 3
    assert data["min_ms"] <= data["avg_ms"] <= data["max_ms"]


@pytest.mark.asyncio
async def test_run_query_with_warmup(tmp_path: Path) -> None:
    """Warmup run is reflected in the result."""
    from retrai.tools.sql_bench import sql_bench

    db = _write_config(tmp_path)
    _seed_table(db)

    raw = await sql_bench(
        action="run_query",
        cwd=str(tmp_path),
        query="SELECT 1",
        warmup=True,
    )
    data = json.loads(raw)

    assert data["warmup_ms"] is not None
    assert data["warmup_ms"] >= 0


@pytest.mark.asyncio
async def test_run_query_no_query_returns_error(tmp_path: Path) -> None:
    """run_query without a query string returns a JSON error."""
    from retrai.tools.sql_bench import sql_bench

    _write_config(tmp_path)

    raw = await sql_bench(action="run_query", cwd=str(tmp_path), query="")
    data = json.loads(raw)

    assert "error" in data
    assert "no query" in data["error"].lower()


@pytest.mark.asyncio
async def test_run_query_bad_sql(tmp_path: Path) -> None:
    """A bad SQL statement returns a structured error, not a crash."""
    from retrai.tools.sql_bench import sql_bench

    _write_config(tmp_path)

    raw = await sql_bench(
        action="run_query",
        cwd=str(tmp_path),
        query="SELECT * FROM nonexistent_table_xyz",
    )
    data = json.loads(raw)

    assert data["error"] is not None


# ── explain_query tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_query(tmp_path: Path) -> None:
    """explain_query returns an execution plan for SQLite."""
    from retrai.tools.sql_bench import sql_bench

    db = _write_config(tmp_path)
    _seed_table(db)

    raw = await sql_bench(
        action="explain_query",
        cwd=str(tmp_path),
        query="SELECT * FROM metrics WHERE value > 10",
    )
    data = json.loads(raw)

    assert data["action"] == "explain_query"
    assert data["error"] is None
    assert len(data["plan_text"]) > 0
    assert data["plan_type"] == "sqlite_plan"


@pytest.mark.asyncio
async def test_explain_query_no_query(tmp_path: Path) -> None:
    from retrai.tools.sql_bench import sql_bench

    _write_config(tmp_path)

    raw = await sql_bench(action="explain_query", cwd=str(tmp_path), query="")
    data = json.loads(raw)

    assert "error" in data


# ── profile_table tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_table(tmp_path: Path) -> None:
    """profile_table returns schema and row count for a real table."""
    from retrai.tools.sql_bench import sql_bench

    db = _write_config(tmp_path)
    _seed_table(db)

    raw = await sql_bench(
        action="profile_table",
        cwd=str(tmp_path),
        table="metrics",
    )
    data = json.loads(raw)

    assert data["action"] == "profile_table"
    assert data["error"] is None
    assert data["table_name"] == "metrics"
    assert data["row_count"] == 3
    assert len(data["columns"]) == 3
    assert data["columns"][0]["name"] == "id"


@pytest.mark.asyncio
async def test_profile_table_no_name(tmp_path: Path) -> None:
    from retrai.tools.sql_bench import sql_bench

    _write_config(tmp_path)

    raw = await sql_bench(action="profile_table", cwd=str(tmp_path), table="")
    data = json.loads(raw)

    assert "error" in data


@pytest.mark.asyncio
async def test_profile_table_nonexistent(tmp_path: Path) -> None:
    """SQLite PRAGMA table_info returns empty for nonexistent tables."""
    from retrai.tools.sql_bench import sql_bench

    _write_config(tmp_path)

    raw = await sql_bench(
        action="profile_table",
        cwd=str(tmp_path),
        table="no_such_table_xyz",
    )
    data = json.loads(raw)

    # SQLite doesn't error on PRAGMA table_info for missing tables;
    # it returns empty columns instead.  The row_count SELECT will
    # fail, so row_count stays None.
    assert data["columns"] == []
    assert data["row_count"] is None


# ── Edge cases ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_action(tmp_path: Path) -> None:
    from retrai.tools.sql_bench import sql_bench

    _write_config(tmp_path)

    raw = await sql_bench(action="bad_action", cwd=str(tmp_path))
    data = json.loads(raw)

    assert "error" in data
    assert "bad_action" in data["error"]


@pytest.mark.asyncio
async def test_missing_config(tmp_path: Path) -> None:
    """No .retrai.yml means no DSN → connection error."""
    from retrai.tools.sql_bench import sql_bench

    raw = await sql_bench(action="run_query", cwd=str(tmp_path), query="SELECT 1")
    data = json.loads(raw)

    assert "error" in data


# ── Internal helpers / backend detection ──────────────────────────────────────


def test_detect_backend_databricks() -> None:
    from retrai.tools.sql_bench import _detect_backend

    assert _detect_backend({"backend": "databricks"}) == "databricks"
    assert _detect_backend({"server_hostname": "x.databricks.net"}) == "databricks"
    assert _detect_backend({"http_path": "/sql/1.0/warehouses/abc"}) == "databricks"
    assert _detect_backend({"dsn": "databricks://token:x@host"}) == "databricks"


def test_detect_backend_sqlalchemy() -> None:
    from retrai.tools.sql_bench import _detect_backend

    assert _detect_backend({"dsn": "sqlite:///test.db"}) == "sqlalchemy"
    assert _detect_backend({"dsn": "postgresql://user:pass@host/db"}) == "sqlalchemy"
    assert _detect_backend({}) == "sqlalchemy"


# ── SqlBenchTool registration ────────────────────────────────────────────────


def test_sql_bench_in_registry() -> None:
    """SqlBenchTool should be discoverable in the default registry."""
    from retrai.tools.builtins import create_default_registry

    registry = create_default_registry(discover_plugins=False)
    assert "sql_bench" in registry
    tool = registry.get("sql_bench")
    assert tool is not None
    assert tool.parallel_safe is True

    schema = tool.get_schema()
    assert schema.name == "sql_bench"
    assert "action" in schema.parameters["properties"]
