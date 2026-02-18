# How It Works

retrAI implements a **reinforcement-learning-inspired agent loop** using LangGraph. Instead of searching a state space, it uses a large language model to reason about what needs to change and takes targeted code-editing actions until the goal is verified as achieved.

---

## The Agent Loop

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

### Nodes

| Node | Responsibility |
|---|---|
| **plan** | Calls the LLM with the full conversation history. Extracts tool calls from the response. |
| **act** | Executes each tool call (bash, file read/write). Appends results to the message history. |
| **evaluate** | Calls `goal.check()`. Injects a status message into the conversation. Increments iteration counter. |
| **human_check** | (HITL only) Interrupts graph execution. Waits for a human resume signal via the API. |

### Routing

After each node, a router function decides the next step:

- **After plan**: has pending tool calls → `act`, otherwise → `evaluate`
- **After evaluate**: goal achieved → `END`, max iterations reached → `END`, HITL enabled → `human_check`, else → `plan`
- **After human_check**: approved → `plan`, aborted → `END`

---

## State

The entire agent state is a single `TypedDict` that flows through the graph:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # full LLM conversation
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

Two things are injected via LangGraph's `config["configurable"]` (not stored in state):
- **`goal`**: the `GoalBase` instance, used by the `evaluate` node
- **`event_bus`**: the `AsyncEventBus`, used by all nodes to emit events

---

## Goals

Every goal implements the `GoalBase` abstract class:

```python
class GoalBase(ABC):
    @abstractmethod
    async def check(self, state: dict, cwd: str) -> GoalResult:
        """Run the check and return achieved=True/False + reason."""
        ...

    @abstractmethod
    def system_prompt(self) -> str:
        """Instructions prepended to the LLM conversation."""
        ...
```

The `evaluate` node calls `goal.check()` to determine if the work is done. The `plan` node calls `goal.system_prompt()` to inject goal-specific instructions at the start of the conversation.

---

## Event System

Every agent action publishes a structured `AgentEvent`:

```python
@dataclass
class AgentEvent:
    kind: EventKind      # step_start | tool_call | tool_result | goal_check |
                         # human_check_required | iteration_complete | run_end | error
    run_id: str
    iteration: int
    ts: float
    payload: dict
```

The `AsyncEventBus` uses per-subscriber `asyncio.Queue` objects for fan-out:

```
event_bus.publish(event)
    │
    ├──▶ WebSocket route queue  ──▶ browser
    ├──▶ TUI consumer queue     ──▶ Textual app
    └──▶ CLI consumer queue     ──▶ terminal
```

---

## LangGraph + LiteLLM

- **LangGraph**: Provides the `StateGraph` with cycles, `MemorySaver` checkpointing, and the `interrupt()` primitive for HITL.
- **LiteLLM**: Provides a unified interface to Claude, GPT-4, Gemini, Ollama, etc. via `ChatLiteLLM` from `langchain_community`.

The LLM is configured per-run via `model_name` in the state. `get_llm()` is cached with `lru_cache` so the same model name always returns the same object.

---

## Tools Available to the Agent

| Tool | What it does |
|---|---|
| `bash_exec` | Run any shell command in the project directory with a configurable timeout |
| `file_read` | Read a file (path relative to project root) |
| `file_list` | List directory contents |
| `file_write` | Write/overwrite a file, creating parent directories as needed |
| `run_pytest` | Run pytest with JSON report and return structured failure data |

The agent always starts by listing files and reading key config files (pyproject.toml, package.json, etc.) to build context before making any changes.

---

## Message History Management

The conversation history grows with each iteration. To prevent unbounded context:

- Messages are trimmed to the most recent 40 entries before each LLM call
- The first message (system prompt) is always preserved
- Tool results are included in the history so the LLM understands what happened

---

## HITL (Human-in-the-Loop)

With `--hitl`, the agent pauses after each `evaluate` step using LangGraph's `interrupt()` mechanism:

1. `human_check_node` publishes a `human_check_required` event
2. The graph is suspended — persisted in `MemorySaver` checkpointer
3. A human calls `POST /api/runs/{id}/resume` with `{"decision": "approve"}` or `{"decision": "abort"}`
4. The graph resumes from the checkpoint

This allows humans to review each iteration before the agent continues.
