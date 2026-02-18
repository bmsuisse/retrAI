# 04 — Performance Optimization

The agent optimizes `bench.py` to complete in **< 0.5s** (3 consecutive passes).

## Run

```bash
retrai run --cwd .
```

### Functions to optimize

| Function                    | Current    | Approach                             |
|-----------------------------|-----------|--------------------------------------|
| `find_duplicates`           | O(n²)     | Use a `set` / `Counter`              |
| `count_pairs_with_sum`      | O(n²)     | Two-pointer or hash map              |
| `matrix_multiply`           | O(n³) py  | Use `numpy` or list comprehension    |
| `longest_common_subsequence`| Exp.      | DP table with memoization            |
