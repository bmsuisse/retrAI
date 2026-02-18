"""Async runner functions for CLI commands (no Typer coupling)."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from retrai.config import RunConfig
    from retrai.events.types import AgentEvent

console = Console()


def _fmt_args(args: dict[str, Any]) -> str:
    parts = []
    for k, v in args.items():
        v_str = repr(v) if not isinstance(v, str) else repr(v[:80])
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def _render_event(event: AgentEvent) -> None:
    """Render an AgentEvent to the terminal."""
    kind = event.kind
    payload = event.payload
    iteration = event.iteration

    if kind == "step_start":
        node = payload.get("node", "?")
        console.print(f"\n[bold blue]▶ [{iteration}] {node.upper()}[/bold blue]")

    elif kind == "tool_call":
        tool = payload.get("tool", "?")
        args = payload.get("args", {})
        args_str = _fmt_args(args)
        console.print(f"  [cyan]⟶ {tool}[/cyan]({args_str})")

    elif kind == "tool_result":
        tool = payload.get("tool", "?")
        err = payload.get("error", False)
        content = payload.get("content", "")[:200]
        color = "red" if err else "green"
        icon = "✗" if err else "✓"
        console.print(f"  [{color}]{icon} {tool}[/{color}]: {content!r}")

    elif kind == "goal_check":
        achieved = payload.get("achieved", False)
        reason = payload.get("reason", "")
        color = "green" if achieved else "yellow"
        icon = "✓" if achieved else "…"
        console.print(f"  [{color}]{icon} Goal: {reason}[/{color}]")

    elif kind == "human_check_required":
        console.print("\n[bold yellow]⏸  Human check required[/bold yellow]")
        console.print("  [dim]Use 'retrai serve' and the web UI to approve/abort.[/dim]")

    elif kind == "iteration_complete":
        iteration = payload.get("iteration", 0)
        console.print(f"  [dim]--- iteration {iteration} complete ---[/dim]")

    elif kind == "run_end":
        status = payload.get("status", "?")
        console.print(f"\n[bold]Run ended: {status}[/bold]")

    elif kind == "error":
        err = payload.get("error", "unknown error")
        console.print(f"\n[bold red]ERROR: {err}[/bold red]")


def _save_history(
    cfg: RunConfig,
    achieved: bool,
    iters: int,
    tokens: int,
    cost: float,
    started_at: float,
    reason: str,
) -> None:
    """Persist run history. Silently ignores IO errors."""
    try:
        from retrai.history import save_run_history

        save_run_history(
            cwd=cfg.cwd,
            run_id=cfg.run_id,
            goal=cfg.goal,
            model=cfg.model_name,
            status="achieved" if achieved else "failed",
            iterations=iters,
            max_iterations=cfg.max_iterations,
            total_tokens=tokens,
            estimated_cost_usd=cost,
            started_at=started_at,
            reason=reason,
        )
    except OSError:
        pass


def _build_initial_state(cfg: RunConfig) -> dict[str, Any]:
    return {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": cfg.max_iterations,
        "stop_mode": cfg.stop_mode,
        "hitl_enabled": cfg.hitl_enabled,
        "model_name": cfg.model_name,
        "cwd": cfg.cwd,
        "run_id": cfg.run_id,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }


def _format_run_summary(final_state: dict[str, Any], elapsed: float) -> tuple[bool, str, str]:
    """Extract results from final_state and build Rich-formatted summary line."""
    achieved = final_state.get("goal_achieved", False)
    reason = final_state.get("goal_reason", "")
    iters = final_state.get("iteration", 0)
    tokens = final_state.get("total_tokens", 0)
    cost = final_state.get("estimated_cost_usd", 0.0)

    info_parts = [f"Iterations: [bold]{iters}[/bold]"]
    if tokens:
        info_parts.append(f"Tokens: [bold]{tokens:,}[/bold]")
    if cost > 0:
        info_parts.append(f"Cost: [bold]${cost:.4f}[/bold]")
    info_parts.append(f"Time: [bold]{elapsed:.1f}s[/bold]")
    return achieved, reason, "  ·  ".join(info_parts)


async def run_cli(cfg: RunConfig) -> int:
    """Run the agent loop and stream events to the terminal."""
    from retrai.agent.graph import build_graph
    from retrai.events.bus import AsyncEventBus
    from retrai.goals.registry import get_goal

    goal = get_goal(cfg.goal)
    bus = AsyncEventBus()
    graph = build_graph(hitl_enabled=cfg.hitl_enabled)

    initial_state = _build_initial_state(cfg)
    run_config = {
        "configurable": {
            "thread_id": cfg.run_id,
            "event_bus": bus,
            "goal": goal,
        }
    }

    q = await bus.subscribe()
    started_at = time.time()
    exit_code = 1

    graph_task = asyncio.create_task(graph.ainvoke(initial_state, config=run_config))  # type: ignore[arg-type]

    async def consume_events() -> None:
        nonlocal exit_code
        async for event in bus.iter_events(q):
            _render_event(event)
            if event.kind == "run_end" and event.payload.get("status") == "achieved":
                exit_code = 0

    consumer_task = asyncio.create_task(consume_events())

    final_state: dict[str, Any] | None = None
    try:
        final_state = await graph_task
    except Exception as e:
        console.print(f"\n[red]Run failed: {e}[/red]")
    finally:
        await bus.close()
        await consumer_task

    if final_state:
        elapsed = time.time() - started_at
        achieved, reason, info_line = _format_run_summary(final_state, elapsed)

        if achieved:
            console.print(
                Panel(
                    f"[bold green]✅ GOAL ACHIEVED[/bold green]\n{reason}\n\n{info_line}",
                    border_style="green",
                    title="[bold]Run Complete[/bold]",
                )
            )
            exit_code = 0
        else:
            console.print(
                Panel(
                    f"[bold red]❌ GOAL NOT ACHIEVED[/bold red]\n{reason}\n\n{info_line}",
                    border_style="red",
                    title="[bold]Run Complete[/bold]",
                )
            )
            exit_code = 1

        _save_history(
            cfg,
            achieved,
            final_state.get("iteration", 0),
            final_state.get("total_tokens", 0),
            final_state.get("estimated_cost_usd", 0.0),
            started_at,
            reason,
        )

    return exit_code


async def run_solve(cfg: RunConfig, description: str) -> int:
    """Run the agent with SolverGoal."""
    from retrai.agent.graph import build_graph
    from retrai.events.bus import AsyncEventBus
    from retrai.goals.solver import SolverGoal

    goal = SolverGoal(description=description)
    bus = AsyncEventBus()
    graph = build_graph(hitl_enabled=False)

    initial_state = _build_initial_state(cfg)
    run_config = {
        "configurable": {
            "thread_id": cfg.run_id,
            "event_bus": bus,
            "goal": goal,
        }
    }

    q = await bus.subscribe()
    started_at = time.time()
    exit_code = 1

    async def consume_events() -> None:
        nonlocal exit_code
        async for event in bus.iter_events(q):
            _render_event(event)
            if event.kind == "run_end" and event.payload.get("status") == "achieved":
                exit_code = 0

    consumer_task = asyncio.create_task(consume_events())

    final_state: dict[str, Any] | None = None
    try:
        final_state = await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]
    except Exception as e:
        console.print(f"\n[red]Solve failed: {e}[/red]")
    finally:
        await bus.close()
        await consumer_task

    if final_state:
        elapsed = time.time() - started_at
        achieved, reason, info_line = _format_run_summary(final_state, elapsed)

        if achieved:
            console.print(
                Panel(
                    f"[bold green]✅ SOLVED[/bold green]\n{reason}\n\n{info_line}",
                    border_style="green",
                    title="[bold]Problem Solved[/bold]",
                )
            )
            exit_code = 0
        else:
            console.print(
                Panel(
                    f"[bold red]❌ NOT SOLVED[/bold red]\n{reason}\n\n{info_line}",
                    border_style="red",
                    title="[bold]Solve Incomplete[/bold]",
                )
            )

        _save_history(
            cfg,
            achieved,
            final_state.get("iteration", 0),
            final_state.get("total_tokens", 0),
            final_state.get("estimated_cost_usd", 0.0),
            started_at,
            reason,
        )

    return exit_code


async def run_swarm(
    description: str,
    cwd: str,
    model_name: str,
    max_workers: int,
    max_iter: int,
) -> int:
    """Run the swarm orchestrator."""
    from retrai.swarm.orchestrator import SwarmOrchestrator

    orchestrator = SwarmOrchestrator(
        description=description,
        cwd=cwd,
        model_name=model_name,
        max_workers=max_workers,
        max_iterations_per_worker=max_iter,
    )

    console.print("\n[bold blue]Phase 1:[/bold blue] Decomposing goal…")
    started_at = time.time()

    try:
        result = await orchestrator.run()
    except Exception as e:
        console.print(f"\n[red]Swarm failed: {e}[/red]")
        return 1

    elapsed = time.time() - started_at

    console.print("\n[bold blue]Worker Results:[/bold blue]")
    for wr in result.worker_results:
        status_icon = "✅" if wr.status == "achieved" else "❌"
        console.print(f"  {status_icon} [bold]{wr.task_id}[/bold]: {wr.description[:60]}")
        if wr.findings:
            console.print(f"     [dim]{wr.findings[:120]}[/dim]")
        console.print(
            f"     [dim]iters={wr.iterations_used}  "
            f"tokens={wr.tokens_used:,}  "
            f"cost=${wr.cost_usd:.4f}[/dim]"
        )

    status_color = {
        "achieved": "green",
        "partial": "yellow",
        "failed": "red",
    }.get(result.status, "red")

    info_parts = [
        f"Workers: [bold]{len(result.worker_results)}[/bold]",
        f"Total iterations: [bold]{result.total_iterations}[/bold]",
        f"Total tokens: [bold]{result.total_tokens:,}[/bold]",
        f"Total cost: [bold]${result.total_cost:.4f}[/bold]",
        f"Time: [bold]{elapsed:.1f}s[/bold]",
    ]
    info_line = "  ·  ".join(info_parts)

    console.print(
        Panel(
            f"[bold {status_color}]{result.status.upper()}[/bold {status_color}]\n\n"
            f"{result.synthesis}\n\n{info_line}",
            border_style=status_color,
            title="[bold]Swarm Complete[/bold]",
        )
    )

    return 0 if result.status == "achieved" else 1
