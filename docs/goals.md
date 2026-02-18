# Goals

A **goal** is the thing retrAI tries to achieve. Goals are defined by subclassing `GoalBase`.

## Built-in Goals

### `pytest`

Runs `pytest --json-report` and succeeds when all tests pass.

```bash
retrai run pytest
```

### `shell-goal`

Runs any shell command and checks the result.

```bash
retrai run shell-goal
```

Configured via `.retrai.yml`:

```yaml
goal: shell-goal
check_command: "make check"
success_condition:
  exit_code: 0          # require this exit code
  output_contains: "OK" # and/or this string in stdout
  max_seconds: 10       # and/or run under this time
```

### `perf-check`

Runs a Python script/function repeatedly and succeeds when it completes under a time threshold.

```yaml
goal: perf-check
check_command: "python bench.py"
max_seconds: 0.5
```

### `sql-benchmark`

Connects to a database, runs a query, and checks execution time.

```yaml
goal: sql-benchmark
dsn: "sqlite:///mydb.sqlite"
query: "SELECT * FROM orders WHERE ..."
max_ms: 50
```

## Writing a Custom Goal

```python
from retrai.goals.base import GoalBase, GoalResult

class MyGoal(GoalBase):
    name = "my-goal"

    async def check(self, state: dict, cwd: str) -> GoalResult:
        # inspect state, run tools, check files…
        return GoalResult(achieved=True, reason="Done!", details={})

    def system_prompt(self) -> str:
        return "Achieve my custom goal by doing X, Y, Z."
```

Register it:

```python
# in your project's conftest.py or plugin entry point
from retrai.goals.registry import _REGISTRY
from mypackage.goals import MyGoal
_REGISTRY["my-goal"] = MyGoal()
```
