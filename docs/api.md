# API Reference

The retrAI server exposes a REST API and WebSocket endpoint for controlling agent runs programmatically.

Start the server:

```bash
retrai serve                   # http://localhost:8000
retrai serve --port 9000       # custom port
```

---

## REST Endpoints

### `POST /api/runs` — Start a Run

**Request:**

```json
{
  "goal": "pytest",
  "cwd": "/path/to/project",
  "model_name": "claude-sonnet-4-6",
  "max_iterations": 20,
  "hitl_enabled": false
}
```

**Response** `201 Created`:

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

---

### `GET /api/runs` — List All Runs

**Response** `200 OK`:

```json
[
  {
    "run_id": "550e8400-...",
    "goal": "pytest",
    "status": "achieved",
    "created_at": "2026-02-18T12:00:00Z"
  }
]
```

---

### `GET /api/runs/{run_id}` — Get Run Details

**Response** `200 OK`:

```json
{
  "run_id": "550e8400-...",
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
    "goal_reason": "All 42 tests passed",
    "total_tokens": 12450,
    "estimated_cost_usd": 0.037
  }
}
```

---

### `POST /api/runs/{run_id}/resume` — Resume HITL Run

**Request:**

```json
{ "decision": "approve" }
```

Possible decisions: `approve`, `abort`.

---

## WebSocket

### `WS /api/ws/{run_id}` — Live Event Stream

Subscribe to a real-time stream of `AgentEvent` objects.

**Connect:**

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/550e8400-...');
ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  console.log(event.kind, event.payload);
};
```

**Event format:**

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

### Event Kinds

| Kind | When Emitted | Payload |
|---|---|---|
| `step_start` | Node begins execution | `{ "node": "plan" }` |
| `tool_call` | LLM requests a tool | `{ "tool": "bash_exec", "args": {...} }` |
| `tool_result` | Tool execution completes | `{ "tool": "bash_exec", "output": "...", "exit_code": 0 }` |
| `llm_usage` | After LLM call | `{ "input_tokens": 1200, "output_tokens": 340 }` |
| `goal_check` | Goal evaluated | `{ "achieved": false, "reason": "3 tests failing" }` |
| `human_check_required` | HITL gate reached | `{ "iteration": 2, "summary": "..." }` |
| `human_check_response` | Human responded | `{ "decision": "approve" }` |
| `iteration_complete` | Full iteration done | `{ "iteration": 2, "tokens": 1540 }` |
| `run_end` | Run finished | `{ "achieved": true, "iterations": 3, "total_tokens": 4620 }` |
| `error` | Unexpected error | `{ "message": "...", "traceback": "..." }` |
