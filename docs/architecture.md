# Architecture

## High-Level Overview

```mermaid
graph TB
    subgraph CLI["CLI / TUI"]
        cli["retrai run"]
        tui["retrai tui"]
    end

    subgraph Server["Web Server"]
        api["FastAPI"]
        ws["WebSocket"]
        vue["Vue 3 Frontend"]
    end

    subgraph Core["Agent Core"]
        graph["LangGraph StateGraph"]
        plan["Plan Node"]
        act["Act Node"]
        eval["Evaluate Node"]
        hitl["Human Check"]
    end

    subgraph Infra["Infrastructure"]
        bus["AsyncEventBus"]
        llm["LiteLLM"]
        tools["Tool Registry"]
        goals["Goal Registry"]
        mem["Agent Memory"]
    end

    cli --> graph
    tui --> graph
    api --> graph
    graph --> plan
    plan --> act
    act --> eval
    eval --> hitl
    plan --> llm
    act --> tools
    eval --> goals
    graph --> bus
    bus --> ws
    bus --> tui
    bus --> cli
    graph --> mem

    style graph fill:#7c3aed,color:#fff
    style bus fill:#2563eb,color:#fff
    style llm fill:#059669,color:#fff
```

## Package Structure

```
retrai/
├── agent/              # LangGraph agent
│   ├── graph.py        # StateGraph definition
│   ├── state.py        # AgentState TypedDict
│   ├── routers.py      # Edge routing logic
│   └── nodes/          # Graph nodes
│       ├── plan.py     # LLM reasoning
│       ├── act.py      # Tool execution
│       ├── evaluate.py # Goal checking
│       ├── reflect.py  # Strategy extraction
│       └── human_check.py
├── cli/                # Typer CLI
│   ├── app.py          # Commands
│   ├── commands.py     # Subcommands
│   └── runners.py      # Run orchestration
├── events/             # Event system
│   ├── bus.py          # AsyncEventBus
│   └── types.py        # AgentEvent dataclass
├── goals/              # Goal definitions
│   ├── base.py         # GoalBase ABC
│   ├── registry.py     # Goal registry
│   ├── detector.py     # Auto-detection
│   ├── pytest_goal.py
│   ├── pyright_goal.py
│   ├── bun_goal.py
│   ├── sql_goal.py
│   ├── perf_goal.py
│   ├── ml_goal.py
│   ├── ai_eval.py
│   └── ...
├── llm/                # LLM integration
│   └── factory.py      # get_llm() → ChatLiteLLM
├── memory/             # Persistent memory
│   ├── store.py        # JSON-based store
│   └── extractor.py    # Strategy extraction
├── tools/              # Agent tools
│   ├── base.py         # BaseTool ABC
│   ├── builtins.py     # Tool registry
│   ├── bash_exec.py
│   ├── file_read.py
│   ├── file_write.py
│   ├── grep_search.py
│   └── ...
├── server/             # FastAPI server
│   ├── app.py          # ASGI app
│   ├── run_manager.py  # Run lifecycle
│   └── routes/
│       ├── runs.py     # REST endpoints
│       └── ws.py       # WebSocket
├── tui/                # Textual TUI
│   ├── app.py          # Main app
│   ├── widgets.py      # Custom widgets
│   ├── screens.py      # Modal screens
│   ├── wizard.py       # Setup wizard
│   └── styles.tcss     # Stylesheet
├── swarm/              # Multi-agent orchestration
│   ├── orchestrator.py
│   ├── worker.py
│   ├── roles.py
│   └── decomposer.py
├── benchmark.py        # Model comparison
├── watcher.py          # File watcher
├── pipeline/           # Pipeline mode
├── review.py           # Code review
├── history.py          # Run history
├── config.py           # RunConfig
└── safety/             # Guardrails
    └── guardrails.py
```

## Key Design Decisions

### LangGraph StateGraph

The agent is a **cyclic graph** with conditional edges, not a linear pipeline. This means:

- The agent can loop as many times as needed
- Routing is determined at runtime by the state
- HITL interrupts are first-class via `interrupt()`
- State is checkpointed automatically via `MemorySaver`

### LiteLLM for Multi-Model

Instead of binding to one provider, retrAI uses [LiteLLM](https://docs.litellm.ai) which provides a unified interface to 100+ LLM providers. Switching models is a single CLI flag.

### Event-Driven Architecture

All agent activity flows through the `AsyncEventBus` — a pub/sub system using `asyncio.Queue` per subscriber. This decouples the agent from its consumers (CLI, TUI, WebSocket) and allows multiple frontends to observe the same run simultaneously.

### Tool Registry

Tools are registered via a decorator pattern:

```python
from retrai.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"

    async def execute(self, **kwargs) -> str:
        return "result"
```

The registry is extensible via Python entry points for plugin discovery.
