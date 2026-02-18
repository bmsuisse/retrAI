# Quick Start

## Fix Failing Tests

The most common use case — point retrAI at a project with failing tests and let it fix them:

```bash
cd /path/to/your/project
retrai run pytest
```

The agent will:

1. :material-folder-search: **Scan** your project structure
2. :material-test-tube: **Run** pytest to see current failures
3. :material-file-search: **Read** failing tests and source files
4. :material-pencil: **Fix** the source code
5. :material-refresh: **Re-run** until all tests pass (or max iterations hit)

!!! info "Auto-detection"
    If you run `retrai run` without a goal name, retrAI scans your project and picks the right goal automatically — `pytest` for Python projects, `bun-test` for TypeScript, `cargo-test` for Rust, etc.

---

## Fix Type Errors

```bash
retrai run pyright
```

Runs `pyright` and iteratively fixes type errors until the project is clean.

---

## Custom Goal (YAML)

Create `.retrai.yml` in your project root:

```yaml
goal: shell-goal
check_command: "python benchmark.py"
success_condition:
  exit_code: 0
  output_contains: "PASS"
system_prompt: |
  Optimise the benchmark until it outputs PASS.
  Modify only src/algorithm.py.
```

Then run:

```bash
retrai run shell-goal
```

---

## AI Eval — Goals in Plain English

Don't have a test suite? Describe what you want in English and let the agent write both the tests and the implementation:

```bash
# Step 1: The agent writes a pytest harness from your description
retrai generate-eval "make the sort function handle empty lists and None values"

# Step 2: The agent implements the solution
retrai run ai-eval
```

---

## Web Dashboard

```bash
retrai serve
# open http://localhost:8000
```

Start a run via the UI, watch the live graph light up, and see every tool call and goal check stream in real time via WebSocket.

---

## Terminal UI

```bash
retrai tui pytest
```

A rich Textual dashboard with:

- Live event stream
- Token usage sparklines
- Tool call tree
- Iteration progress bar

---

## Choose Your Model

```bash
# Claude (default)
retrai run pytest

# GPT-4o
retrai run pytest --model gpt-4o

# Gemini
retrai run pytest --model gemini/gemini-2.0-flash

# Local Ollama
retrai run pytest --model ollama/llama3

# GitHub Copilot (auto-authenticated)
retrai run pytest --model copilot/gpt-4o
```

---

## All Options

```
retrai run --help

Usage: retrai run [OPTIONS] [GOAL]

Arguments:
  GOAL  Goal to achieve (auto-detected if omitted)

Options:
  --cwd / -C       Project directory  [default: .]
  --model / -m     LLM model  [default: claude-sonnet-4-6]
  --max-iter / -n  Maximum iterations  [default: 20]
  --hitl           Enable human-in-the-loop checkpoints
  --api-key / -k   API key (overrides env var)
  --api-base       Custom API base URL
```
