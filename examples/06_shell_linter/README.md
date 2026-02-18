# 06 — Shell Goal: Lint Fixer (Ruff)

The agent fixes all Ruff lint errors in `messy.py` until `ruff check` exits cleanly.

## Run

```bash
retrai run --cwd .
```

### What's wrong

`messy.py` is packed with violations:
- Unused imports (`os`, `sys`)
- Inconsistent whitespace and indentation
- Lambda assignments (E731)
- Missing whitespace around operators
- Multiple imports on one line (E401)
