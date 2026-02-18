"""SQL benchmark goal: run a query, check timing, get execution plan, profile tables."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from retrai.goals.base import GoalBase, GoalResult
from retrai.tools.sql_bench import (
    ExplainResult,
    QueryResult,
    TableProfile,
    _create_backend,
    _explain_query_sync,
    _profile_table_sync,
    _run_query_sync,
)

logger = logging.getLogger(__name__)

_CONFIG_FILE = ".retrai.yml"


def _load_config(cwd: str) -> dict[str, Any]:
    path = Path(cwd) / _CONFIG_FILE
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


class SqlBenchmarkGoal(GoalBase):
    """Optimise a SQL query to run under a time limit.

    Supports both SQLAlchemy and Databricks SQL Warehouse backends.

    `.retrai.yml`:

    ```yaml
    goal: sql-benchmark

    # SQLAlchemy backend (default)
    dsn: "sqlite:///mydb.sqlite"
    query_file: "query.sql"
    max_ms: 50
    expected_rows: 42

    # Databricks backend
    backend: databricks
    server_hostname: xxx.azuredatabricks.net
    http_path: /sql/1.0/warehouses/abc123
    query_file: "query.sql"
    max_ms: 200
    iterations: 3
    warmup: true
    explain: true
    profile_tables:
      - catalog.schema.orders
      - catalog.schema.customers
    ```
    """

    name = "sql-benchmark"

    async def check(self, state: dict[str, Any], cwd: str) -> GoalResult:
        cfg = _load_config(cwd)

        # Create backend
        try:
            backend = _create_backend(cfg)
        except ImportError as e:
            return GoalResult(
                achieved=False,
                reason=f"Missing dependency: {e}. Install with: uv pip install 'retrai[sql]'",
                details={"error": "missing_dependency"},
            )
        except ValueError as e:
            return GoalResult(
                achieved=False,
                reason=str(e),
                details={"error": "missing_config"},
            )
        except Exception as e:
            return GoalResult(
                achieved=False,
                reason=f"Connection failed: {e}",
                details={"error": str(e)},
            )

        # Load query
        query_file = cfg.get("query_file")
        if query_file:
            qpath = Path(cwd) / query_file
            if not qpath.exists():
                return GoalResult(
                    achieved=False,
                    reason=f"Query file not found: {query_file}",
                    details={"error": "file_not_found"},
                )
            query = qpath.read_text()
        else:
            query = cfg.get("query", "SELECT 1")

        max_ms = float(cfg.get("max_ms", 100))
        expected_rows = cfg.get("expected_rows")
        iterations = int(cfg.get("iterations", 1))
        warmup = bool(cfg.get("warmup", False))
        do_explain = bool(cfg.get("explain", False))
        profile_tables: list[str] = cfg.get("profile_tables", [])

        try:
            import asyncio

            loop = asyncio.get_event_loop()

            # Run the query benchmark
            qresult: QueryResult = await loop.run_in_executor(
                None,
                _run_query_sync,
                backend,
                query,
                iterations,
                warmup,
            )
        except Exception as e:
            return GoalResult(
                achieved=False,
                reason=f"Query execution failed: {e}",
                details={"error": str(e)},
            )

        if qresult.error:
            return GoalResult(
                achieved=False,
                reason=f"Query execution failed: {qresult.error}",
                details={"error": qresult.error},
            )

        # Build details dict
        details: dict[str, Any] = {
            "elapsed_ms": qresult.elapsed_ms,
            "avg_ms": qresult.avg_ms,
            "min_ms": qresult.min_ms,
            "max_ms": qresult.max_ms,
            "row_count": qresult.row_count,
            "columns": qresult.columns,
            "iterations": iterations,
        }
        if qresult.warmup_ms is not None:
            details["warmup_ms"] = qresult.warmup_ms

        # Collect EXPLAIN plan
        if do_explain:
            try:
                explain: ExplainResult = await loop.run_in_executor(
                    None,
                    _explain_query_sync,
                    backend,
                    query,
                )
                details["explain"] = {
                    "plan_type": explain.plan_type,
                    "plan_text": explain.plan_text,
                }
                if explain.error:
                    details["explain"]["error"] = explain.error
            except Exception as e:
                details["explain"] = {"error": str(e)}

        # Profile related tables
        if profile_tables:
            profiles: list[dict[str, Any]] = []
            for tbl in profile_tables:
                try:
                    prof: TableProfile = await loop.run_in_executor(
                        None,
                        _profile_table_sync,
                        backend,
                        tbl,
                    )
                    profiles.append(
                        {
                            "table": prof.table_name,
                            "row_count": prof.row_count,
                            "columns": prof.columns,
                            "properties": prof.properties,
                            "size_bytes": prof.size_bytes,
                            "partitions": prof.partitions,
                            "error": prof.error,
                        }
                    )
                except Exception as e:
                    profiles.append({"table": tbl, "error": str(e)})
            details["table_profiles"] = profiles

        # Close backend
        try:
            backend.close()
        except Exception:
            pass

        # Evaluate pass/fail
        failures: list[str] = []
        if qresult.avg_ms > max_ms:
            failures.append(f"avg query time {qresult.avg_ms:.1f}ms exceeds limit {max_ms}ms")
        if expected_rows is not None and qresult.row_count != expected_rows:
            failures.append(f"returned {qresult.row_count} rows (expected {expected_rows})")

        if failures:
            return GoalResult(
                achieved=False,
                reason="; ".join(failures),
                details=details,
            )

        return GoalResult(
            achieved=True,
            reason=(
                f"Query completed in avg {qresult.avg_ms:.1f}ms"
                f" (limit: {max_ms}ms), {qresult.row_count} rows,"
                f" {iterations} iteration(s)"
            ),
            details=details,
        )

    def system_prompt(self, cwd: str = ".") -> str:  # type: ignore[override]
        cfg = _load_config(cwd)
        custom = cfg.get("system_prompt", "")
        max_ms = cfg.get("max_ms", 100)
        qfile = cfg.get("query_file", "the SQL query")
        backend = cfg.get("backend", "sqlalchemy")
        profile_tables: list[str] = cfg.get("profile_tables", [])

        base = (
            f"Your goal is to optimise {qfile} so it executes in under {max_ms}ms.\n\n"
            "You have access to the `sql_bench` tool with three actions:\n"
            "- `run_query`: Execute the query and get timing info\n"
            "- `explain_query`: Get the execution plan (EXPLAIN EXTENDED)\n"
            "- `profile_table`: Get schema, row counts, and properties for any table\n\n"
            "Strategy:\n"
            "1. Read the current SQL query.\n"
            "2. Use `sql_bench(action='explain_query')` to analyze the execution plan.\n"
            "3. Identify bottlenecks: full scans, shuffle operations, skew, missing indexes.\n"
        )

        if profile_tables:
            tables_str = ", ".join(profile_tables)
            base += (
                f"4. Profile related tables ({tables_str}) to understand data distribution.\n"
                "5. Propose targeted changes: rewrite the query, add indexes, use CTEs.\n"
                "6. Write the improved query back to the file.\n"
                "7. Re-run `sql_bench(action='run_query')` to verify improvement.\n"
            )
        else:
            base += (
                "4. Propose targeted changes: rewrite the query, add indexes, use CTEs.\n"
                "5. Write the improved query back to the file.\n"
                "6. Re-run `sql_bench(action='run_query')` to verify improvement.\n"
            )

        if backend == "databricks":
            base += (
                "\nDatabricks-specific optimizations:\n"
                "- Use Delta table features: Z-ORDER BY, OPTIMIZE, liquid clustering.\n"
                "- Leverage partition pruning — filter on partition columns.\n"
                "- Prefer broadcast joins for small dimension tables.\n"
                "- Consider Photon engine capabilities for scan-heavy queries.\n"
                "- Check for data skew in join keys.\n"
                "- Use ANALYZE TABLE to update statistics.\n"
            )

        base += (
            "\nRules:\n"
            "- Do NOT change the expected result set (same rows, same columns).\n"
            "- You may create indexes (DDL) if needed.\n"
            "- Prefer query rewrites over schema changes.\n"
        )

        return (custom + "\n\n" + base).strip() if custom else base
