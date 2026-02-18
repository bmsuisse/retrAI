# API Reference

Base URL: `http://localhost:8000`

## REST Endpoints

### `POST /api/runs`

Start a new agent run.

**Request body:**

```json
{
  "goal": "pytest",
  "cwd": "/path/to/project",
  "model_name": "claude-sonnet-4-6",
  "max_iterations": 20,
  "hitl_enabled": false
}
```

**Response:**

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

---

### `GET /api/runs`

List all runs.

---

### `GET /api/runs/{run_id}`

Get run details.

**Response:**

```json
{
  "run_id": "...",
  "goal": "pytest",
  "status": "achieved",
  "model_name": "claude-sonnet-4-6",
  "max_iterations": 20,
  "hitl_enabled": false,
  "cwd": "/my/project",
  "error": null,
  "final_state": {
    "iteration": 3,
    "goal_achieved": true,
    "goal_reason": "All 42 tests passed"
  }
}
```

---

### `POST /api/runs/{run_id}/resume`

Resume a HITL-paused run.

```json
{ "decision": "approve" }
```

---

## WebSocket

### `WS /api/ws/{run_id}`

Subscribe to a live stream of `AgentEvent` objects as JSON.

Each message is:

```json
{
  "kind": "tool_call",
  "run_id": "550e8400-...",
  "iteration": 2,
  "ts": 1739800000.123,
  "payload": {
    "tool": "file_read",
    "args": { "path": "src/main.py" }
  }
}
```

### Event kinds

| kind | When emitted |
|---|---|
| `step_start` | Node begins execution |
| `tool_call` | LLM requests a tool |
| `tool_result` | Tool execution completes |
| `goal_check` | Goal evaluated |
| `human_check_required` | HITL gate reached |
| `human_check_response` | Human responded |
| `iteration_complete` | Full iteration done |
| `run_end` | Run finished (achieved/failed) |
| `error` | Unexpected error |
