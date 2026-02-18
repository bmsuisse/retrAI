# Architecture

## Agent Loop

```
START → [plan] → (has tool calls?) → [act] → [evaluate] → (goal achieved?) → END
               ↘ (no tool calls)  ↗           ↓ (continue)
                            [evaluate]    (hitl?) → [human_check] → (approve?) → [plan]
                                                                   → (abort) → END
                                             ↓ (no hitl)
                                           [plan]
```

## Components

| Component | File | Role |
|---|---|---|
| `config.py` | `retrai/config.py` | `RunConfig` dataclass |
| Event bus | `retrai/events/bus.py` | Async fan-out to WS + TUI + log |
| LLM factory | `retrai/llm/factory.py` | LiteLLM → LangChain model |
| Goals | `retrai/goals/` | `GoalBase` ABC + registry |
| Tools | `retrai/tools/` | bash, file_read, file_write, pytest |
| Agent graph | `retrai/agent/graph.py` | LangGraph `StateGraph` |
| Server | `retrai/server/app.py` | FastAPI + WebSocket |
| CLI | `retrai/cli/app.py` | Typer commands |
| TUI | `retrai/tui/app.py` | Textual app |
| Frontend | `frontend/` | Vue 3 + Vue Flow + Pinia |

## Event System

Every agent action emits a structured `AgentEvent` with a `kind` field:

```
step_start → tool_call → tool_result → goal_check → iteration_complete
                                                   ↓
                                     human_check_required (HITL only)
                                                   ↓
                                         run_end / error
```

The `AsyncEventBus` fans out to all subscribers via `asyncio.Queue`. Both the
WebSocket route and the TUI subscribe simultaneously.

## LangGraph State

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # full conversation history
    pending_tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    goal_achieved: bool
    goal_reason: str
    iteration: int
    max_iterations: int
    hitl_enabled: bool
    model_name: str
    cwd: str
    run_id: str
```

The `goal` object and `event_bus` are injected via `config["configurable"]`, not stored in state.
