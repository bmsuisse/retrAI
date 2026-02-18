# Quick Start

## Fix Failing Tests

```bash
cd /path/to/your/project
retrai run pytest
```

The agent will:

1. Scan your project structure
2. Run pytest to see the current state
3. Read failing tests and source files
4. Fix the source code
5. Re-run until all tests pass (or max iterations hit)

## Custom Goal (YAML)

Create `.retrai.yml` in your project:

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

## Web Dashboard

```bash
retrai serve
# open http://localhost:8000
```

Start a run via the UI, watch the live Vue Flow graph light up, and see every
tool call and goal check stream into the event log in real time.

## All Options

```
retrai run pytest --help

  goal               Goal name (pytest, shell-goal, perf-check, sql-benchmark)
  --cwd / -C         Project directory [default: .]
  --model / -m       LLM model [default: claude-sonnet-4-6]
  --max-iter / -n    Maximum iterations [default: 20]
  --hitl             Enable human-in-the-loop checkpoints
```
