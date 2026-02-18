# retrAI

```
 ██████╗ ███████╗████████╗██████╗  █████╗ ██╗
 ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██║
 ██████╔╝█████╗     ██║   ██████╔╝███████║██║
 ██╔══██╗██╔══╝     ██║   ██╔══██╗██╔══██║██║
 ██║  ██║███████╗   ██║   ██║  ██║██║  ██║██║
 ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
  self-solving AI agent loop
```

[![PyPI](https://img.shields.io/pypi/v/retrai?color=7c3aed)](https://pypi.org/project/retrai/)
[![Python](https://img.shields.io/pypi/pyversions/retrai)](https://pypi.org/project/retrai/)
[![License](https://img.shields.io/github/license/bmsuisse/retrAI)](https://github.com/bmsuisse/retrAI/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-bmsuisse.github.io%2FretrAI-7c3aed)](https://bmsuisse.github.io/retrAI)

**`cd` into any project. Run `retrai run`. Watch it fix itself.**

retrAI is an autonomous AI agent that:
1. Scans your project to understand its structure
2. Runs the appropriate test suite (pytest, `bun test`, `cargo test`, `go test`, …)
3. Reads the failures, reasons about them, and edits the source code
4. Re-runs the tests and loops until everything passes (or max iterations hit)

It's like reinforcement learning for your codebase — goal-oriented, iterative, and fully autonomous.

---

## Installation

```bash
# Recommended — isolated global CLI (like az, gh, ruff)
pipx install retrai

# Or with uv
uv tool install retrai

# Or with pip
pip install retrai
```

> Requires Python 3.12+. `pipx` or `uv tool` install into an isolated virtualenv
> so retrAI's dependencies never conflict with your project.

---

## Quick Start

```bash
# Go to any project with failing tests
cd /path/to/my-project

# Run — auto-detects pytest, bun test, cargo test, etc.
retrai run

# Or specify explicitly
retrai run pytest
retrai run bun-test --model gpt-4o
retrai run cargo-test --max-iter 30

# Launch the web dashboard
retrai serve                # opens on http://localhost:8000

# Launch the Textual TUI
retrai tui pytest
```

---

## How It Works

retrAI uses a **LangGraph StateGraph** that cycles until the goal is achieved:

```
START
  │
  ▼
[plan] ──── LLM decides what tools to call ────────────┐
  │                                                     │
  │ has tool calls?                                     │
  ▼                                                     │
[act] ─── executes bash, reads/writes files ───────────┤
  │                                                     │
  ▼                                                     │
[evaluate] ── runs goal.check() ── goal achieved? ─── END
  │                                                     │
  │ not yet, iterations left?                           │
  ├── hitl enabled? ── [human_check] ── approve? ──────┘
  │                                      abort? ── END  │
  │                                                     │
  └──────────────────────────────── [plan] ◀────────────┘
```

Every step emits structured **`AgentEvent`** objects that stream to:
- The terminal (CLI mode)
- The Textual TUI (rich log + status panel)
- WebSocket clients (Vue dashboard)

---

## Supported Goals

| Goal | Command | What it does |
|---|---|---|
| `pytest` | `retrai run pytest` | Run `pytest` and fix Python failures |
| `pyright` | `retrai run pyright` | Fix all pyright type errors |
| `bun-test` | `retrai run bun-test` | Run `bun test` and fix JS/TS failures |
| `npm-test` | `retrai run npm-test` | Run `npm test` (Jest/Vitest) |
| `cargo-test` | `retrai run cargo-test` | Run `cargo test` and fix Rust failures |
| `go-test` | `retrai run go-test` | Run `go test ./...` and fix Go failures |
| `make-test` | `retrai run make-test` | Run `make test` |
| `shell-goal` | `retrai run shell-goal` | Any custom command via `.retrai.yml` |
| `perf-check` | `retrai run perf-check` | Make a command run within a time limit |
| `sql-benchmark` | `retrai run sql-benchmark` | Make a SQL query run within a time limit |
| `ai-eval` | `retrai run ai-eval` | Pass an AI-generated eval harness |

### Auto-Detection

If you run `retrai run` with no goal, it scans the project:

```
.retrai.yml present?    → shell-goal
pyproject.toml/pytest?  → pytest
pyrightconfig.json?     → pyright
Cargo.toml?             → cargo-test
go.mod?                 → go-test
package.json + bun.lock → bun-test
package.json + jest?    → npm-test
Makefile with test:?    → make-test
```

---

## AI-Generated Eval Harness

For goals that can't be expressed as "make tests pass", retrAI can **generate the test harness itself**:

```bash
# Describe what you want to achieve in plain English
retrai generate-eval "make the sort function in utils.py handle duplicates correctly"
retrai generate-eval "optimize the SQL query in queries.py to complete in < 50ms"
retrai generate-eval "make the API endpoint return JSON with a 'data' wrapper"

# The planning agent reads your project and writes .retrai/eval_harness.py
# Then run the implementation loop:
retrai run ai-eval
```

This is two-phase:
1. **Planning agent**: reads your project → writes a pytest harness to `.retrai/eval_harness.py`
2. **Implementation agent**: fixes your code until the harness passes

---

## Project Init

Scaffold a `.retrai.yml` config:

```bash
retrai init              # auto-detect goal and create config
retrai init --goal pytest --max-iter 50
```

This creates `.retrai.yml`:
```yaml
goal: pytest
model: claude-sonnet-4-6
max_iterations: 20
hitl_enabled: false
```

---

## CLI Reference

```
retrai run [GOAL] [OPTIONS]        Run an agent loop
  GOAL                             Goal name (auto-detected if omitted)
  --cwd, -C PATH                   Project directory (default: .)
  --model, -m MODEL                LLM model in LiteLLM format
  --max-iter, -n INT               Maximum iterations (default: 20)
  --hitl                           Enable human-in-the-loop checkpoints

retrai serve [OPTIONS]             Start the web dashboard
  --host HOST                      Bind host (default: 0.0.0.0)
  --port, -p PORT                  Port (default: 8000)
  --reload                         Dev mode with auto-reload

retrai tui GOAL [OPTIONS]          Launch the Textual TUI
  --cwd, -C PATH                   Project directory
  --model, -m MODEL                LLM model

retrai init [OPTIONS]              Create .retrai.yml config
  --goal, -g GOAL                  Goal to use
  --model, -m MODEL                LLM model
  --max-iter, -n INT               Max iterations
  --hitl                           Enable HITL

retrai generate-eval DESCRIPTION   Generate an AI eval harness
  --cwd, -C PATH                   Project directory
  --model, -m MODEL                LLM model
```

---

## Multi-Model Support

retrAI uses **LiteLLM** — pass any model in LiteLLM format:

```bash
retrai run pytest --model claude-opus-4-6
retrai run pytest --model gpt-4o
retrai run pytest --model gemini/gemini-2.0-flash
retrai run pytest --model ollama/qwen2.5-coder
```

Set your API keys in a `.env` file (loaded automatically):

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```

---

## Web Dashboard

```bash
retrai serve
# Open http://localhost:8000
```

Features:
- Start / monitor runs
- Live event log with colour-coded steps
- Agent graph visualization (Vue Flow)
- Human-in-the-loop approve/abort modal
- WebSocket real-time streaming

---

## Human-in-the-Loop (HITL)

```bash
retrai run pytest --hitl
```

With `--hitl`, the agent pauses after each evaluate step and waits for your approval before continuing. Approve or abort via the web dashboard at `http://localhost:8000`.

---

## Architecture

```
retrai/
├── config.py           RunConfig dataclass
├── events/
│   ├── types.py        AgentEvent + EventKind
│   └── bus.py          AsyncEventBus (asyncio.Queue fan-out)
├── llm/
│   └── factory.py      get_llm() via LiteLLM
├── goals/
│   ├── base.py         GoalBase ABC
│   ├── detector.py     Auto-detect goal from project files
│   ├── planner.py      AI eval harness generator
│   ├── registry.py     Goal registry
│   └── *.py            Goal implementations
├── agent/
│   ├── state.py        AgentState TypedDict
│   ├── nodes/          plan, act, evaluate, human_check
│   ├── routers.py      Graph routing logic
│   └── graph.py        LangGraph StateGraph assembly
├── server/
│   ├── app.py          FastAPI app
│   ├── run_manager.py  Run registry
│   └── routes/         REST API + WebSocket
├── tui/
│   └── app.py          Textual TUI
└── cli/
    └── app.py          Typer CLI
```

---

## Development

```bash
# Clone and install
git clone https://github.com/bmsuisse/retrAI
cd retrAI
uv sync --dev

# Run tests
uv run pytest tests/ -x -q

# Lint & type check
uv run ruff check retrai tests
uv run pyright

# Build docs
uv run mkdocs serve
```

---

## License

MIT
