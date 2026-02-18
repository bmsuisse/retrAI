# 02 — Pytest Fix (Buggy Source Code)

The agent finds and fixes bugs in `utils.py` until all 20 tests pass.

## Run

```bash
retrai run --cwd .
```

No `.retrai.yml` needed — the CLI auto-detects `pytest` from `pyproject.toml`.

### Bugs planted

| Function         | Bug                                               |
|------------------|----------------------------------------------------|
| `fibonacci`      | Returns `a` instead of `b`                         |
| `merge_sorted`   | Forgets to extend with remaining `b[j:]`           |
| `binary_search`  | Uses `hi = mid` instead of `hi = mid - 1` (hangs)  |
