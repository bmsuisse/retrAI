# Goals

A **goal** defines what retrAI tries to achieve. The agent loop runs `goal.check()` after each iteration to determine if the work is done.

---

## Built-in Goals

### Testing Goals

| Goal | Command | What It Checks |
|---|---|---|
| `pytest` | `retrai run pytest` | All pytest tests pass |
| `pyright` | `retrai run pyright` | Zero pyright type errors |
| `bun-test` | `retrai run bun-test` | All Bun/Vitest tests pass |
| `npm-test` | `retrai run npm-test` | `npm test` exits cleanly |
| `cargo-test` | `retrai run cargo-test` | All Cargo tests pass |
| `go-test` | `retrai run go-test` | All Go tests pass |
| `make-test` | `retrai run make-test` | `make test` exits cleanly |

### Performance Goals

| Goal | Command | What It Checks |
|---|---|---|
| `perf-check` | `retrai run perf-check` | Script completes under time threshold |
| `sql-benchmark` | `retrai run sql-benchmark` | Query runs under target milliseconds |

### AI Goals

| Goal | Command | What It Checks |
|---|---|---|
| `ai-eval` | `retrai run ai-eval` | Generated eval harness passes |
| `ml-optimize` | `retrai run ml-optimize` | ML model hits target metric |
| `shell-goal` | `retrai run shell-goal` | Custom command meets conditions |

### LLM-Scored Goals

These goals use an LLM-as-judge to score the agent's output and provide feedback. No test runner needed — just a rubric and a target score.

| Goal | Command | What It Checks |
|---|---|---|
| `text-improve` | `retrai run text-improve` | Improved text scores ≥ target on your criteria |
| `creative` | `retrai run creative` | Creative content scores ≥ target on quality rubric |
| `score` | `retrai run score` | Any output scores ≥ target on a custom rubric |

→ See [Non-Coding Goals](non-coding-goals.md) for full documentation and examples.

## Goal Configuration

### pytest

No configuration needed — just run:

```bash
retrai run pytest
```

### shell-goal

Configured via `.retrai.yml`:

```yaml
goal: shell-goal
check_command: "make check"
success_condition:
  exit_code: 0          # require this exit code
  output_contains: "OK" # and/or this string in stdout
  max_seconds: 10       # and/or run under this time
```

### perf-check

```yaml
goal: perf-check
check_command: "python bench.py"
max_seconds: 0.5
```

### sql-benchmark

```yaml
goal: sql-benchmark
dsn: "sqlite:///mydb.sqlite"
query: "SELECT * FROM orders WHERE ..."
max_ms: 50
```

### ml-optimize

```yaml
goal: ml-optimize
target_metric: accuracy
target_value: 0.95
train_script: train.py
```

### text-improve

```yaml
goal: text-improve
input_file: draft.md
output_file: improved.md
target_score: 8
criteria:
  - clarity
  - conciseness
  - persuasiveness
```

### creative

```yaml
goal: creative
prompt: "Write a short story about an AI learning to paint"
output_file: story.md
target_score: 8
style: "literary fiction, melancholic"
max_words: 800
```

### score

```yaml
goal: score
task: "Summarise this research paper into a 1-page executive summary"
input_file: paper.md
output_file: summary.md
target_score: 8
rubric: |
  Score 0-10 on:
  - Accuracy: key findings preserved (3 pts)
  - Brevity: ≤400 words (2 pts)
  - Clarity: no jargon (2 pts)
  - Actionability: clear next steps (3 pts)
```

---

## Auto-Detection

Running `retrai run` without specifying a goal scans your project and picks the best match:

| File Found | Goal Selected |
|---|---|
| `pyproject.toml` with pytest | `pytest` |
| `pyrightconfig.json` | `pyright` |
| `package.json` with bun | `bun-test` |
| `Cargo.toml` | `cargo-test` |
| `go.mod` | `go-test` |
| `Makefile` | `make-test` |
| `.retrai.yml` | Reads from config |

---

## Writing a Custom Goal

```python
from retrai.goals.base import GoalBase, GoalResult

class MyGoal(GoalBase):
    name = "my-goal"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        # Run checks, inspect files, call tools...
        return GoalResult(achieved=True, reason="Done!", details={})

    def system_prompt(self) -> str:
        return "Achieve my custom goal by doing X, Y, Z."
```

Register it:

```python
from retrai.goals.registry import _REGISTRY
from mypackage.goals import MyGoal

_REGISTRY["my-goal"] = MyGoal()
```

!!! tip "The system prompt matters"
    A well-crafted `system_prompt()` is the single biggest factor in goal success. Be specific about what files to modify, what constraints to respect, and what "done" looks like.
