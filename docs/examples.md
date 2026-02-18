# Examples

retrAI ships with ready-to-run example projects in the [`examples/`](https://github.com/bmsuisse/retrAI/tree/main/examples) directory.

---

## 01 — SQL Optimization (DuckDB)

Optimize a slow analytical query against a DuckDB database.

```bash
cd examples/01_sql_duckdb
python seed.py              # generate sample data
retrai run sql-benchmark    # agent optimises the query
```

**Goal:** Reduce query execution time below the threshold defined in `.retrai.yml`.

---

## 02 — Fix Failing Pytest

A Python utility module with deliberately broken tests.

```bash
cd examples/02_pytest_fix
retrai run pytest           # agent fixes the source code
```

**Goal:** All tests in `tests/test_utils.py` pass.

---

## 03 — ML Model Optimization

Train and optimise a churn prediction model.

```bash
cd examples/03_ml_churn
python generate_data.py     # create synthetic dataset
retrai run ml-optimize      # agent improves model accuracy
```

**Goal:** Achieve target accuracy on the holdout set.

---

## 04 — Performance Optimization

A benchmark script with a deliberately slow implementation.

```bash
cd examples/04_perf_optimize
retrai run perf-check       # agent optimises the code
```

**Goal:** `bench.py` completes under the time threshold.

---

## 05 — Pyright Type Fixes

A Python module with deliberate type errors.

```bash
cd examples/05_pyright_typing
retrai run pyright          # agent fixes all type errors
```

**Goal:** Zero pyright errors.

---

## 06 — Shell Script Linting

A Python script with style issues to be cleaned up.

```bash
cd examples/06_shell_linter
retrai run shell-goal       # agent fixes linting issues
```

**Goal:** Ruff reports zero violations.

---

## Running All Examples

```bash
for dir in examples/*/; do
  echo "=== Running $dir ==="
  retrai run --cwd "$dir"
done
```

!!! tip "Try different models"
    Each example can be run with any model:
    ```bash
    retrai run pytest --cwd examples/02_pytest_fix --model gpt-4o
    retrai run pytest --cwd examples/02_pytest_fix --model gemini/gemini-2.0-flash
    ```
