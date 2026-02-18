<div class="hero">
  <h1>retrAI</h1>
  <p>A self-solving AI agent loop. Point it at any project, give it a goal, watch it fix itself.</p>
  <span class="badge">pytest</span>
  <span class="badge">sql-benchmark</span>
  <span class="badge">perf-check</span>
  <span class="badge">shell-goal</span>
</div>

## What is retrAI?

retrAI is an autonomous AI agent that runs a **goal loop**:

1. **Plan** — ask the LLM what to do next
2. **Act** — execute tool calls (read files, run commands, write code)
3. **Evaluate** — check if the goal is achieved
4. **Repeat** — until success or max iterations

```bash
cd /my/project
retrai run pytest              # fix all failing tests
retrai run perf-check          # optimise until benchmarks pass
retrai run sql-benchmark       # tune a query until it's fast enough
retrai run shell-goal          # any custom shell-based goal
```

## Key Features

| Feature | Detail |
|---|---|
| **Generic goals** | pytest, perf-check, sql-benchmark, shell-goal, or custom YAML |
| **Multi-model** | Claude, GPT-4o, Gemini — anything LiteLLM supports |
| **Live dashboard** | Vue 3 + Vue Flow graph + WebSocket event stream |
| **Textual TUI** | Rich terminal UI with gradient logo |
| **HITL** | Human-in-the-loop approval gates |
| **FastAPI server** | REST + WebSocket, embeddable in any pipeline |

## Quick Start

```bash
pip install retrai          # or: uv add retrai
retrai run pytest           # uses current directory
retrai serve                # start web dashboard on :8000
```
