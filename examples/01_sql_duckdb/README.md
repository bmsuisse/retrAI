# 01 — SQL Query Optimization (DuckDB)

The agent optimizes a slow SQL query against a local DuckDB database.

## Setup

```bash
pip install duckdb
python seed.py
```

## Run

```bash
retrai run --cwd .
```

The goal: get `query.sql` to execute in **< 50 ms** while returning exactly 10 rows.
