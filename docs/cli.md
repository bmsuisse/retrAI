# CLI Reference

## `retrai run <goal>`

Run an agent goal loop in the terminal.

```
Usage: retrai run [OPTIONS] GOAL

Arguments:
  GOAL  Goal to achieve (e.g. 'pytest')  [required]

Options:
  --cwd   -C  TEXT     Project directory  [default: .]
  --model -m  TEXT     LLM model (LiteLLM format)  [default: claude-sonnet-4-6]
  --max-iter -n INT    Maximum iterations  [default: 20]
  --hitl               Enable human-in-the-loop checkpoints
  --help               Show this message and exit.
```

### Examples

```bash
# Fix all tests in the current directory
retrai run pytest

# Use a different model
retrai run pytest --model gpt-4o

# In a different directory, with HITL
retrai run pytest --cwd /my/project --hitl

# Custom shell goal
retrai run shell-goal --cwd /my/project --max-iter 50

# SQL benchmark
retrai run sql-benchmark --model gemini/gemini-2.0-flash
```

## `retrai serve`

Start the web dashboard (FastAPI + Vue frontend).

```
Usage: retrai serve [OPTIONS]

Options:
  --host TEXT   Host to bind to  [default: 0.0.0.0]
  --port -p INT Port to listen on  [default: 8000]
  --reload      Enable auto-reload (dev mode)
  --help        Show this message and exit.
```

## `retrai tui`

Launch the interactive Textual TUI.

```
Usage: retrai tui [OPTIONS] GOAL

Arguments:
  GOAL  Goal to run in the TUI  [required]

Options:
  --cwd   -C  TEXT  Project directory  [default: .]
  --model -m  TEXT  LLM model  [default: claude-sonnet-4-6]
  --max-iter -n INT Max iterations  [default: 20]
  --help            Show this message and exit.
```
