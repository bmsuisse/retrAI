# retrAI Examples

Self-contained projects for testing every major CLI goal.

> Run any example: `retrai run --cwd examples/<folder>`

| # | Folder | Goal | What the agent does |
|---|--------|------|---------------------|
| 01 | `01_sql_duckdb` | `sql-benchmark` | Optimize a slow query on 500 k rows (DuckDB) |
| 02 | `02_pytest_fix` | `pytest` | Fix 3 bugs until all 20 tests pass |
| 03 | `03_ml_churn` | `ml-optimize` | Reach F1 ≥ 0.88 on customer churn |
| 04 | `04_perf_optimize` | `perf-check` | Speed up 4 naive algorithms to < 0.5 s |
| 05 | `05_pyright_typing` | `pyright` | Add type annotations until 0 errors |
| 06 | `06_shell_linter` | `shell-goal` | Fix all Ruff lint violations |

## Quick start

```bash
# Install retrAI (if not already)
pip install -e .

# Pick an example
cd examples/01_sql_duckdb
python seed.py          # one-time data setup
retrai run              # launch the agent

# Or use --cwd from anywhere
retrai run --cwd examples/02_pytest_fix
```

## Per-example setup

Some examples need a one-time data generation step:

| Example | Setup command |
|---------|--------------|
| `01_sql_duckdb` | `python seed.py` |
| `03_ml_churn` | `python generate_data.py` |

All other examples work out of the box.
