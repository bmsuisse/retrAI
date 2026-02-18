# CLI Reference

## `retrai run`

Run an agent goal loop.

```
Usage: retrai run [OPTIONS] [GOAL]

Arguments:
  GOAL  Goal to achieve. Auto-detected from project if omitted.

Options:
  --cwd    / -C  TEXT   Project directory  [default: .]
  --model  / -m  TEXT   LLM model (any LiteLLM format)  [default: claude-sonnet-4-6]
  --max-iter / -n INT   Maximum iterations  [default: 50]
  --pattern / -p TEXT   Agent solving pattern: default | mop | swarm  [default: default]
  --stop-mode    TEXT   Stop mode: soft | hard  [default: soft]
  --hitl                Enable human-in-the-loop checkpoints
  --api-key  / -k TEXT  API key (overrides env var)
  --api-base     TEXT   Custom API base URL (e.g. for Azure)
  --help                Show this message and exit.
```

### Agent patterns

| Pattern | Description |
|---|---|
| `default` | Standard `plan → act → evaluate → reflect` loop |
| `mop` | Mixture-of-Personas: multiple expert viewpoints merged before acting |
| `swarm` | Multi-agent swarm that decomposes and parallelises the goal |

### Examples

```bash
# Fix all tests in the current directory
retrai run pytest

# Use GPT-4o on a different project
retrai run pytest --cwd /my/project --model gpt-4o

# With human-in-the-loop approval
retrai run pytest --hitl

# Mixture-of-Personas for higher quality output
retrai run text-improve --pattern mop

# Swarm mode for a complex multi-part task
retrai run score --pattern swarm --max-iter 20

# Custom shell goal with 50 max iterations
retrai run shell-goal --cwd /my/project --max-iter 50

# SQL benchmark with Gemini
retrai run sql-benchmark --model gemini/gemini-2.0-flash

# Auto-detect the goal
retrai run
```

---

## `retrai serve`

Start the web dashboard (FastAPI + Vue 3 frontend).

```
Usage: retrai serve [OPTIONS]

Options:
  --host   TEXT   Host to bind to  [default: 0.0.0.0]
  --port / -p INT Port to listen on  [default: 8000]
  --reload        Enable auto-reload (dev mode)
  --help          Show this message and exit.
```

The dashboard provides:

- **Live agent graph** — see which node is executing in real time
- **Event log** — every tool call, result, and goal check
- **Token sparkline** — live token usage visualization
- **HITL modal** — approve/abort when human-in-the-loop is enabled
- **Run history** — browse previous runs and their outcomes
- **Settings panel** — adjust model, iterations, and HITL on the fly

---

## `retrai tui`

Launch the interactive Textual terminal UI.

```
Usage: retrai tui [OPTIONS] GOAL

Arguments:
  GOAL  Goal to run in the TUI  [required]

Options:
  --cwd    / -C  TEXT  Project directory  [default: .]
  --model  / -m  TEXT  LLM model  [default: claude-sonnet-4-6]
  --max-iter / -n INT  Max iterations  [default: 20]
  --help               Show this message and exit.
```

---

## `retrai init`

Interactive first-time setup wizard.

```
Usage: retrai init [OPTIONS]

Options:
  --copilot   Set up GitHub Copilot as the LLM provider
  --help      Show this message and exit.
```

Walks you through:

1. Choosing a provider (Anthropic, OpenAI, Google, Azure, Ollama, Copilot)
2. Selecting a model
3. Setting your API key
4. Creating a `.retrai.yml` config file

---

## `retrai generate-eval`

Generate a pytest test harness from a natural-language description.

```
Usage: retrai generate-eval [OPTIONS] DESCRIPTION

Arguments:
  DESCRIPTION  What you want to achieve, in plain English  [required]

Options:
  --model / -m TEXT  LLM model  [default: claude-sonnet-4-6]
  --cwd   / -C TEXT  Project directory  [default: .]
  --help             Show this message and exit.
```

### Example

```bash
retrai generate-eval "make the sort function handle empty lists and None values"
# Creates .retrai/eval_harness.py

retrai run ai-eval
# Agent implements the solution
```

---

## `retrai watch`

Watch for file changes and auto-trigger agent runs.

```
Usage: retrai watch [OPTIONS] GOAL

Arguments:
  GOAL  Goal to run on file changes  [required]

Options:
  --cwd    / -C  TEXT  Project directory  [default: .]
  --model  / -m  TEXT  LLM model  [default: claude-sonnet-4-6]
  --max-iter / -n INT  Max iterations per run  [default: 20]
  --help               Show this message and exit.
```

---

## `retrai benchmark`

Compare models on the same task.

```
Usage: retrai benchmark [OPTIONS] GOAL

Arguments:
  GOAL  Goal to benchmark  [required]

Options:
  --models TEXT         Comma-separated model list  [required]
  --rounds / -r INT    Rounds per model  [default: 3]
  --cwd    / -C TEXT   Project directory  [default: .]
  --max-iter / -n INT  Max iterations per round  [default: 20]
  --help               Show this message and exit.
```

### Example

```bash
retrai benchmark pytest \
  --models "claude-sonnet-4-6,gpt-4o,gemini/gemini-2.0-flash" \
  --rounds 3
```
