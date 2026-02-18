# 05 — Pyright Type Fixing

The agent adds proper type annotations to `processing.py` until pyright reports **0 errors** in strict mode.

## Run

```bash
retrai run --cwd .
```

No `.retrai.yml` needed — the CLI auto-detects `pyright` from `pyrightconfig.json`.

The file has ~10 functions/methods with **zero type annotations** and pyright is set to `strict` mode.
