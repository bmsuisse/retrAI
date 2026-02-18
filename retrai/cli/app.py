"""Typer CLI for retrAI."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
app = typer.Typer(
    name="retrai",
    help="Self-solving AI agent loop. Run a goal, watch it fix itself.",
    add_completion=False,
    no_args_is_help=True,
)


def _interactive_setup(cwd: str) -> dict[str, str]:
    """Run interactive first-time setup — pick provider, model, and API key."""
    import os

    import yaml

    from retrai.config import get_provider_models

    console.print(
        Panel(
            "[bold cyan]Welcome to retrAI![/bold cyan]\n\n"
            "No [bold].retrai.yml[/bold] found. Let's set up your AI provider.",
            border_style="cyan",
        )
    )

    # 1. Pick provider
    PROVIDER_MODELS = get_provider_models()
    providers = list(PROVIDER_MODELS.keys())
    console.print("\n[bold]Choose your AI provider:[/bold]")
    for i, name in enumerate(providers, 1):
        console.print(f"  [cyan]{i}[/cyan]) {name}")
    choice = typer.prompt("\nProvider number", default="1")
    try:
        provider_name = providers[int(choice) - 1]
    except (ValueError, IndexError):
        provider_name = providers[0]
    provider = PROVIDER_MODELS[provider_name]
    console.print(f"\n[dim]Selected:[/dim] [bold]{provider_name}[/bold]")

    # Handle Copilot device flow
    if provider.get("auth_type") == "copilot_device_flow":
        return _copilot_setup(cwd, yaml)

    # 2. Pick model
    models = provider["models"]
    if models:
        console.print("\n[bold]Choose a model:[/bold]")
        for i, m in enumerate(models, 1):
            console.print(f"  [cyan]{i}[/cyan]) {m}")
        console.print(f"  [cyan]{len(models) + 1}[/cyan]) Custom (enter manually)")
        model_choice = typer.prompt("Model number", default="1")
        try:
            idx = int(model_choice) - 1
            model = models[idx] if 0 <= idx < len(models) else ""
        except (ValueError, IndexError):
            model = models[0]
        if not model:
            model = typer.prompt("Enter model name (LiteLLM format)")
    else:
        model = typer.prompt("Enter model name (LiteLLM format)", default="gpt-4o")
    console.print(f"[dim]Model:[/dim] [bold]{model}[/bold]")

    # 3. API key
    env_var = provider.get("env_var")
    if env_var and not os.environ.get(env_var):
        console.print(
            f"\n[yellow]No {env_var} found in environment.[/yellow]"
        )
        api_key = typer.prompt(
            f"Enter your API key (or leave blank to set {env_var} later)",
            default="",
            hide_input=True,
        )
        if api_key:
            os.environ[env_var] = api_key
    elif env_var:
        console.print(f"\n[green]✓ {env_var} already set in environment[/green]")

    # 4. Extra env vars (e.g. Azure)
    for extra in provider.get("extra_env", []):
        if not os.environ.get(extra):
            val = typer.prompt(f"Enter {extra}", default="")
            if val:
                os.environ[extra] = val

    # 5. API base for local providers
    api_base = provider.get("api_base")
    if api_base:
        os.environ["OPENAI_API_BASE"] = api_base
        console.print(f"[dim]API base:[/dim] [bold]{api_base}[/bold]")

    # Save config
    config: dict[str, str | int | bool] = {
        "model": model,
    }
    config_path = Path(cwd) / ".retrai.yml"
    config_path.write_text(
        yaml.dump(dict(config), default_flow_style=False, sort_keys=False)
    )
    console.print(
        f"\n[bold green]✓ Saved to {config_path.name}[/bold green]\n"
    )
    return {"model": model}


def _copilot_setup(cwd: str, yaml: Any) -> dict[str, str]:
    """Run GitHub Copilot device flow and model selection."""
    import webbrowser

    from retrai.providers.copilot_auth import (
        initiate_device_flow,
        list_copilot_models,
        poll_for_access_token,
    )

    # Start device flow
    dc = initiate_device_flow()
    console.print(
        Panel(
            f"[bold cyan]GitHub Copilot Login[/bold cyan]\n\n"
            f"  1. Open [bold underline]{dc.verification_uri}[/bold underline]\n"
            f"  2. Enter code: [bold yellow]{dc.user_code}[/bold yellow]\n\n"
            f"[dim]Waiting for authorization...[/dim]",
            border_style="cyan",
        )
    )
    # Try to open browser automatically
    try:
        webbrowser.open(dc.verification_uri)
    except Exception:
        pass

    # Poll until authorized
    try:
        github_token = poll_for_access_token(
            dc.device_code,
            interval=dc.interval,
            timeout=dc.expires_in,
        )
    except (TimeoutError, PermissionError) as e:
        console.print(f"\n[red]✗ {e}[/red]")
        raise typer.Exit(code=1) from e

    console.print("\n[bold green]✓ Authenticated with GitHub Copilot![/bold green]")

    # Fetch available models
    models = list_copilot_models(github_token)
    console.print("\n[bold]Choose a model:[/bold]")
    for i, m in enumerate(models, 1):
        console.print(f"  [cyan]{i}[/cyan]) {m}")
    console.print(f"  [cyan]{len(models) + 1}[/cyan]) Custom (enter manually)")
    model_choice = typer.prompt("Model number", default="1")
    try:
        idx = int(model_choice) - 1
        model = models[idx] if 0 <= idx < len(models) else ""
    except (ValueError, IndexError):
        model = models[0]
    if not model:
        model = typer.prompt("Enter model name")
    console.print(f"[dim]Model:[/dim] [bold]{model}[/bold]")

    # Save config with copilot provider marker
    config: dict[str, str | int | bool] = {
        "provider": "copilot",
        "model": model,
    }
    config_path = Path(cwd) / ".retrai.yml"
    config_path.write_text(
        yaml.dump(dict(config), default_flow_style=False, sort_keys=False)
    )
    console.print(
        f"\n[bold green]✓ Saved to {config_path.name}[/bold green]\n"
    )
    return {"provider": "copilot", "model": model}


def _resolve_config(
    cwd: str,
    *,
    goal: str | None,
    model: str,
    max_iter: int,
    hitl: bool,
    api_key: str | None,
    api_base: str | None,
) -> dict[str, str | int | bool]:
    """Load config from .retrai.yml, falling back to interactive setup.

    CLI flags always take priority over config file values.
    Returns a dict with resolved goal, model, max_iterations, hitl_enabled.
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()

    from retrai.config import load_config
    from retrai.goals.detector import detect_goal
    from retrai.goals.registry import list_goals

    # Try loading config file
    file_cfg = load_config(cwd)
    if file_cfg is None:
        # No config file — run interactive setup
        setup_result = _interactive_setup(cwd)
        file_cfg = setup_result

    # Merge: CLI args > config file > defaults
    resolved_model = model if model != "claude-sonnet-4-6" else file_cfg.get("model", model)
    resolved_max_iter = (
        max_iter if max_iter != 50
        else int(file_cfg.get("max_iterations", max_iter))
    )
    resolved_hitl = hitl or bool(file_cfg.get("hitl_enabled", False))

    # Handle Copilot provider — inject token and API base
    if file_cfg.get("provider") == "copilot" and not api_key:
        from retrai.providers.copilot_auth import (
            COPILOT_API_BASE,
            get_or_refresh_copilot_token,
        )

        try:
            ct = get_or_refresh_copilot_token()
            os.environ["OPENAI_API_KEY"] = ct.token
            os.environ["OPENAI_API_BASE"] = COPILOT_API_BASE
            # Copilot models are OpenAI-compatible, prefix with openai/
            model_name = str(resolved_model)
            if not model_name.startswith(("openai/", "copilot/")):
                resolved_model = f"openai/{model_name}"
            console.print(
                "[dim]Using GitHub Copilot subscription[/dim]"
            )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            console.print(
                "[yellow]Run [bold]retrai init[/bold] and select "
                "GitHub Copilot to re-authenticate.[/yellow]"
            )
            raise typer.Exit(code=1) from e

    # Resolve goal: CLI arg > config file > auto-detect
    if goal is None:
        goal = file_cfg.get("goal") if isinstance(file_cfg.get("goal"), str) else None
    if goal is None:
        detected = detect_goal(cwd)
        if detected is None:
            available = ", ".join(list_goals())
            console.print(
                "[yellow]Could not auto-detect a test framework.[/yellow]\n"
                f"Available goals: [bold]{available}[/bold]\n"
                "Pass a goal argument or run [bold]retrai init[/bold]."
            )
            raise typer.Exit(code=1)
        console.print(f"[dim]Auto-detected goal:[/dim] [bold cyan]{detected}[/bold cyan]")
        goal = detected

    # Validate goal
    available_goals = list_goals()
    if goal not in available_goals:
        console.print(f"[red]Unknown goal: '{goal}'. Available: {', '.join(available_goals)}[/red]")
        raise typer.Exit(code=1)

    # Apply auth overrides
    if api_key:
        for env_var in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "AZURE_API_KEY"]:
            if not os.environ.get(env_var):
                os.environ[env_var] = api_key
    if api_base:
        os.environ["OPENAI_API_BASE"] = api_base

    return {
        "goal": goal,
        "model": str(resolved_model),
        "max_iterations": resolved_max_iter,
        "hitl_enabled": resolved_hitl,
    }


@app.command()
def run(
    goal: str | None = typer.Argument(
        None,
        help=(
            "Goal to achieve (e.g. 'pytest', 'bun-test', 'cargo-test'). "
            "Omit to auto-detect from project files."
        ),
    ),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory (default: current dir)"),
    model: str = typer.Option(
        "claude-sonnet-4-6", "--model", "-m", help="LLM model name (LiteLLM format)"
    ),
    max_iter: int = typer.Option(50, "--max-iter", "-n", help="Maximum agent iterations"),
    hitl: bool = typer.Option(False, "--hitl", help="Enable human-in-the-loop checkpoints"),
    api_key: str | None = typer.Option(
        None, "--api-key", "-k", help="API key (overrides env var)", envvar="LLM_API_KEY"
    ),
    api_base: str | None = typer.Option(
        None, "--api-base", help="Custom API base URL (e.g. for Azure, Ollama, vLLM)"
    ),
) -> None:
    """Run an agent goal loop in the terminal.

    If no goal is given, retrAI scans the project and auto-detects the right one.
    """
    from retrai.config import RunConfig

    resolved_cwd = str(Path(cwd).resolve())
    resolved = _resolve_config(
        resolved_cwd,
        goal=goal,
        model=model,
        max_iter=max_iter,
        hitl=hitl,
        api_key=api_key,
        api_base=api_base,
    )

    cfg = RunConfig(
        goal=str(resolved["goal"]),
        cwd=resolved_cwd,
        model_name=str(resolved["model"]),
        max_iterations=int(resolved["max_iterations"]),
        hitl_enabled=bool(resolved["hitl_enabled"]),
    )

    console.print(
        Panel(
            Text.from_markup(
                f"[bold cyan]retrAI[/bold cyan]  [dim]—[/dim]  goal=[bold]{cfg.goal}[/bold]  "
                f"model=[bold]{cfg.model_name}[/bold]  max-iter=[bold]{cfg.max_iterations}[/bold]  "
                f"hitl=[bold]{'on' if cfg.hitl_enabled else 'off'}[/bold]\n"
                f"[dim]cwd: {resolved_cwd}[/dim]"
            ),
            border_style="cyan",
        )
    )

    exit_code = asyncio.run(_run_cli(cfg))
    raise typer.Exit(code=exit_code)


async def _run_cli(cfg) -> int:
    """Run the agent loop and stream events to the terminal."""
    from retrai.agent.graph import build_graph
    from retrai.events.bus import AsyncEventBus
    from retrai.goals.registry import get_goal

    goal = get_goal(cfg.goal)
    bus = AsyncEventBus()
    graph = build_graph(hitl_enabled=cfg.hitl_enabled)

    initial_state = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": cfg.max_iterations,
        "hitl_enabled": cfg.hitl_enabled,
        "model_name": cfg.model_name,
        "cwd": cfg.cwd,
        "run_id": cfg.run_id,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }

    run_config = {
        "configurable": {
            "thread_id": cfg.run_id,
            "event_bus": bus,
            "goal": goal,
        }
    }

    q = await bus.subscribe()
    started_at = time.time()

    # Run graph and consume events concurrently
    graph_task = asyncio.create_task(graph.ainvoke(initial_state, config=run_config))  # type: ignore[arg-type]
    final_state = None
    exit_code = 1

    async def consume_events() -> None:
        nonlocal exit_code
        async for event in bus.iter_events(q):
            _render_event(event)
            if event.kind == "run_end":
                payload = event.payload
                if payload.get("status") == "achieved":
                    exit_code = 0

    consumer_task = asyncio.create_task(consume_events())

    try:
        final_state = await graph_task
    except Exception as e:
        console.print(f"\n[red]Run failed: {e}[/red]")
    finally:
        await bus.close()
        await consumer_task

    if final_state:
        achieved = final_state.get("goal_achieved", False)
        reason = final_state.get("goal_reason", "")
        iters = final_state.get("iteration", 0)
        tokens = final_state.get("total_tokens", 0)
        cost = final_state.get("estimated_cost_usd", 0.0)
        elapsed = time.time() - started_at

        # Build summary info lines
        info_parts = [f"Iterations: [bold]{iters}[/bold]"]
        if tokens:
            info_parts.append(f"Tokens: [bold]{tokens:,}[/bold]")
        if cost > 0:
            info_parts.append(f"Cost: [bold]${cost:.4f}[/bold]")
        info_parts.append(f"Time: [bold]{elapsed:.1f}s[/bold]")
        info_line = "  ·  ".join(info_parts)

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

        # Persist history
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
        except Exception:
            pass  # Don't crash on history IO

    return exit_code


def _render_event(event) -> None:
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


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = repr(v) if not isinstance(v, str) else repr(v[:80])
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """Start the retrAI web dashboard (FastAPI + Vue)."""
    from dotenv import load_dotenv

    load_dotenv()

    import uvicorn

    console.print(
        Panel(
            f"[bold cyan]retrAI server[/bold cyan] starting on [bold]http://{host}:{port}[/bold]",
            border_style="cyan",
        )
    )
    uvicorn.run(
        "retrai.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def tui(
    goal: str | None = typer.Argument(
        None,
        help=(
            "Goal to achieve (e.g. 'pytest', 'pyright', 'bun-test'). "
            "Omit to launch the setup wizard."
        ),
    ),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model"),
    max_iter: int = typer.Option(50, "--max-iter", "-n", help="Max iterations"),
    hitl: bool = typer.Option(False, "--hitl", help="Enable human-in-the-loop checkpoints"),
    wizard: bool = typer.Option(False, "--wizard", "-w", help="Force the setup wizard"),
    api_key: str | None = typer.Option(
        None, "--api-key", "-k", help="API key (overrides env var)", envvar="LLM_API_KEY"
    ),
    api_base: str | None = typer.Option(
        None, "--api-base", help="Custom API base URL (e.g. for Azure, Ollama, vLLM)"
    ),
) -> None:
    """Launch the interactive Textual TUI.

    If no goal is given, the experiment setup wizard is shown to guide you
    through configuring the test experiment step by step.
    """
    from retrai.config import RunConfig
    from retrai.tui.app import RetrAITUI

    resolved_cwd = str(Path(cwd).resolve())

    if wizard or goal is None:
        # Launch TUI with empty goal — wizard will auto-open on mount
        cfg = RunConfig(
            goal="",
            cwd=resolved_cwd,
            model_name=model,
            max_iterations=max_iter,
            hitl_enabled=hitl,
        )
    else:
        resolved = _resolve_config(
            resolved_cwd,
            goal=goal,
            model=model,
            max_iter=max_iter,
            hitl=hitl,
            api_key=api_key,
            api_base=api_base,
        )
        cfg = RunConfig(
            goal=str(resolved["goal"]),
            cwd=resolved_cwd,
            model_name=str(resolved["model"]),
            max_iterations=int(resolved["max_iterations"]),
            hitl_enabled=bool(resolved["hitl_enabled"]),
        )

    tui_app = RetrAITUI(cfg=cfg)
    tui_app.run()


@app.command()
def init(
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    goal: str | None = typer.Option(
        None, "--goal", "-g", help="Goal to use (auto-detected if omitted)"
    ),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model name"),
    max_iter: int = typer.Option(50, "--max-iter", "-n", help="Max agent iterations"),
    hitl: bool = typer.Option(False, "--hitl", help="Enable human-in-the-loop checkpoints"),
) -> None:
    """Scaffold a .retrai.yml config file in the project directory."""
    import yaml

    from retrai.goals.detector import detect_goal
    from retrai.goals.registry import list_goals

    resolved_cwd = str(Path(cwd).resolve())

    if goal is None:
        detected = detect_goal(resolved_cwd)
        if detected:
            console.print(f"[dim]Auto-detected:[/dim] [bold cyan]{detected}[/bold cyan]")
            goal = detected
        else:
            available = ", ".join(list_goals())
            console.print(
                "[yellow]Could not auto-detect a test framework.[/yellow]\n"
                f"Available goals: [bold]{available}[/bold]\n"
                "Pass [bold]--goal <name>[/bold] to configure manually."
            )
            raise typer.Exit(code=1)

    config: dict = {
        "goal": goal,
        "model": model,
        "max_iterations": max_iter,
        "hitl_enabled": hitl,
    }

    config_path = Path(resolved_cwd) / ".retrai.yml"
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    console.print(
        Panel(
            Text.from_markup(
                f"[bold green]✓ Created[/bold green] [bold]{config_path}[/bold]\n\n"
                f"  goal:           [cyan]{goal}[/cyan]\n"
                f"  model:          [cyan]{model}[/cyan]\n"
                f"  max_iterations: [cyan]{max_iter}[/cyan]\n"
                f"  hitl_enabled:   [cyan]{hitl}[/cyan]\n\n"
                "Run [bold]retrai run[/bold] to start the agent."
            ),
            border_style="green",
            title="retrAI init",
        )
    )


@app.command(name="generate-eval")
def generate_eval(
    description: str = typer.Argument(..., help="Natural language description of what to achieve"),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model name"),
) -> None:
    """Generate an AI eval harness from a natural-language description.

    Example:
        retrai generate-eval "make the sort function run in O(n log n) time"

    After running this, use:
        retrai run ai-eval
    """
    from dotenv import load_dotenv

    load_dotenv()

    from retrai.goals.planner import generate_eval_harness

    resolved_cwd = str(Path(cwd).resolve())

    console.print(
        Panel(
            f"[bold cyan]Generating eval harness…[/bold cyan]\n[dim]{description}[/dim]",
            border_style="cyan",
        )
    )

    harness_path = asyncio.run(
        generate_eval_harness(
            description=description,
            cwd=resolved_cwd,
            model_name=model,
        )
    )

    harness_content = harness_path.read_text()
    console.print(
        Panel(
            harness_content,
            title=(
                f"[bold green]✓ Harness saved to "
                f"{harness_path.relative_to(resolved_cwd)}[/bold green]"
            ),
            border_style="green",
        )
    )
    console.print(
        "\n[bold]Next step:[/bold] run [bold cyan]retrai run ai-eval[/bold cyan]"
        f" [dim]--cwd {resolved_cwd}[/dim]"
    )


@app.command()
def history(
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of runs to show"),
) -> None:
    """Show past run history."""
    from rich.table import Table

    from retrai.history import load_run_history

    resolved_cwd = str(Path(cwd).resolve())
    records = load_run_history(resolved_cwd, limit=limit)

    if not records:
        console.print(
            "[dim]No run history found.[/dim] "
            "Run [bold cyan]retrai run[/bold cyan] first."
        )
        return

    table = Table(
        title="[bold cyan]retrAI Run History[/bold cyan]",
        border_style="cyan",
        show_lines=True,
    )
    table.add_column("Run ID", style="dim", max_width=12)
    table.add_column("Goal", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Status")
    table.add_column("Iters", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("When", style="dim")

    for r in records:
        status_str = (
            "[green]✅ achieved[/green]"
            if r.status == "achieved"
            else "[red]❌ failed[/red]"
        )
        cost_str = f"${r.estimated_cost_usd:.4f}" if r.estimated_cost_usd else "-"
        token_str = f"{r.total_tokens:,}" if r.total_tokens else "-"
        dur_str = f"{r.duration_seconds:.1f}s"
        when = datetime.fromtimestamp(r.started_at, tz=UTC).strftime(
            "%Y-%m-%d %H:%M"
        )
        table.add_row(
            r.run_id[:12],
            r.goal,
            r.model,
            status_str,
            str(r.iterations),
            token_str,
            cost_str,
            dur_str,
            when,
        )

    console.print(table)


@app.command()
def rollback(
    run_id: str = typer.Argument(..., help="Run ID to rollback (first 8+ chars)"),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
) -> None:
    """Undo changes from a specific run using git.

    This restores files that were modified during the given run by checking out
    their pre-run versions from git.
    """
    import subprocess

    from retrai.history import load_run_history

    resolved_cwd = str(Path(cwd).resolve())

    # Find the matching run
    records = load_run_history(resolved_cwd, limit=100)
    match = None
    for r in records:
        if r.run_id.startswith(run_id):
            match = r
            break

    if not match:
        console.print(f"[red]No run found matching: {run_id}[/red]")
        raise typer.Exit(code=1)

    console.print(
        f"[dim]Rolling back run:[/dim] [bold]{match.run_id[:12]}[/bold] "
        f"({match.goal}, {match.status})"
    )

    # Use git to restore files to pre-run state
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=resolved_cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            console.print("[red]Not a git repository or git error.[/red]")
            raise typer.Exit(code=1)

        changed_files = [f for f in result.stdout.strip().split("\n") if f]
        if not changed_files:
            console.print("[yellow]No uncommitted changes to rollback.[/yellow]")
            return

        console.print(f"\n[dim]Found {len(changed_files)} changed file(s):[/dim]")
        for f in changed_files:
            console.print(f"  [dim]·[/dim] {f}")

        if typer.confirm("\nRestore these files to their last committed state?"):
            subprocess.run(
                ["git", "checkout", "--"] + changed_files,
                cwd=resolved_cwd,
                check=True,
            )
            console.print("[bold green]✓ Files restored.[/bold green]")
        else:
            console.print("[dim]Rollback cancelled.[/dim]")

    except subprocess.TimeoutExpired:
        console.print("[red]Git command timed out.[/red]")
        raise typer.Exit(code=1)


@app.command()
def solve(
    description: str = typer.Argument(..., help="Natural language description of what to achieve"),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model"),
    max_iter: int = typer.Option(30, "--max-iter", "-n", help="Maximum iterations"),
    api_key: str | None = typer.Option(
        None, "--api-key", "-k", help="API key", envvar="LLM_API_KEY"
    ),
    api_base: str | None = typer.Option(
        None, "--api-base", help="Custom API base URL"
    ),
) -> None:
    """Solve a problem described in natural language.

    Uses an LLM-as-judge to evaluate whether the goal has been met.

    Examples:
        retrai solve "refactor the auth module to use JWT tokens"
        retrai solve "add input validation to all API endpoints"
        retrai solve "make the sort function handle edge cases"
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()

    from retrai.config import RunConfig

    resolved_cwd = str(Path(cwd).resolve())

    # Apply auth overrides
    if api_key:
        for env_var in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
            if not os.environ.get(env_var):
                os.environ[env_var] = api_key
    if api_base:
        os.environ["OPENAI_API_BASE"] = api_base

    console.print(
        Panel(
            f"[bold cyan]retrAI solve[/bold cyan]\n\n"
            f"[bold]{description}[/bold]\n\n"
            f"[dim]model={model}  max-iter={max_iter}  cwd={resolved_cwd}[/dim]",
            border_style="cyan",
        )
    )

    cfg = RunConfig(
        goal="solve",
        cwd=resolved_cwd,
        model_name=model,
        max_iterations=max_iter,
        hitl_enabled=False,
    )

    exit_code = asyncio.run(_run_solve(cfg, description))
    raise typer.Exit(code=exit_code)


async def _run_solve(cfg, description: str) -> int:
    """Run the agent with SolverGoal."""
    from retrai.agent.graph import build_graph
    from retrai.events.bus import AsyncEventBus
    from retrai.goals.solver import SolverGoal

    goal = SolverGoal(description=description)
    bus = AsyncEventBus()
    graph = build_graph(hitl_enabled=False)

    initial_state = {
        "messages": [],
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "iteration": 0,
        "max_iterations": cfg.max_iterations,
        "hitl_enabled": False,
        "model_name": cfg.model_name,
        "cwd": cfg.cwd,
        "run_id": cfg.run_id,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
    }

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
            if event.kind == "run_end":
                if event.payload.get("status") == "achieved":
                    exit_code = 0

    consumer_task = asyncio.create_task(consume_events())

    try:
        final_state = await graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]
    except Exception as e:
        console.print(f"\n[red]Solve failed: {e}[/red]")
        final_state = None
    finally:
        await bus.close()
        await consumer_task

    if final_state:
        achieved = final_state.get("goal_achieved", False)
        reason = final_state.get("goal_reason", "")
        iters = final_state.get("iteration", 0)
        tokens = final_state.get("total_tokens", 0)
        cost = final_state.get("estimated_cost_usd", 0.0)
        elapsed = time.time() - started_at

        info_parts = [f"Iterations: [bold]{iters}[/bold]"]
        if tokens:
            info_parts.append(f"Tokens: [bold]{tokens:,}[/bold]")
        if cost > 0:
            info_parts.append(f"Cost: [bold]${cost:.4f}[/bold]")
        info_parts.append(f"Time: [bold]{elapsed:.1f}s[/bold]")
        info_line = "  ·  ".join(info_parts)

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

        # Persist history
        try:
            from retrai.history import save_run_history

            save_run_history(
                cwd=cfg.cwd,
                run_id=cfg.run_id,
                goal="solve",
                model=cfg.model_name,
                status="achieved" if achieved else "failed",
                iterations=iters,
                max_iterations=cfg.max_iterations,
                total_tokens=tokens,
                estimated_cost_usd=cost,
                started_at=started_at,
                reason=reason,
            )
        except Exception:
            pass

    return exit_code


@app.command()
def swarm(
    description: str = typer.Argument(
        ..., help="High-level goal to decompose and solve with multiple agents"
    ),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model"),
    workers: int = typer.Option(3, "--workers", "-w", help="Number of parallel worker agents"),
    max_iter: int = typer.Option(
        30, "--max-iter", "-n", help="Max iterations PER WORKER"
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", "-k", help="API key", envvar="LLM_API_KEY"
    ),
    api_base: str | None = typer.Option(
        None, "--api-base", help="Custom API base URL"
    ),
) -> None:
    """Run a multi-agent swarm to solve a complex goal.

    Decomposes the goal into sub-tasks, runs parallel worker agents,
    and synthesizes findings.

    Examples:
        retrai swarm "fix all type errors and add missing tests"
        retrai swarm "refactor the codebase to use async/await" --workers 5
        retrai swarm "add comprehensive error handling" --model gpt-4o
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()

    resolved_cwd = str(Path(cwd).resolve())

    if api_key:
        for env_var in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
            if not os.environ.get(env_var):
                os.environ[env_var] = api_key
    if api_base:
        os.environ["OPENAI_API_BASE"] = api_base

    console.print(
        Panel(
            f"[bold cyan]retrAI swarm[/bold cyan]  🐝\n\n"
            f"[bold]{description}[/bold]\n\n"
            f"[dim]workers={workers}  model={model}  "
            f"max-iter/worker={max_iter}[/dim]\n"
            f"[dim]cwd: {resolved_cwd}[/dim]",
            border_style="cyan",
        )
    )

    exit_code = asyncio.run(_run_swarm(
        description=description,
        cwd=resolved_cwd,
        model_name=model,
        max_workers=workers,
        max_iter=max_iter,
    ))
    raise typer.Exit(code=exit_code)


async def _run_swarm(
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

    # Display worker results
    console.print("\n[bold blue]Worker Results:[/bold blue]")
    for wr in result.worker_results:
        status_icon = "✅" if wr.status == "achieved" else "❌"
        console.print(
            f"  {status_icon} [bold]{wr.task_id}[/bold]: {wr.description[:60]}"
        )
        if wr.findings:
            console.print(f"     [dim]{wr.findings[:120]}[/dim]")
        console.print(
            f"     [dim]iters={wr.iterations_used}  "
            f"tokens={wr.tokens_used:,}  "
            f"cost=${wr.cost_usd:.4f}[/dim]"
        )

    # Display synthesis
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


# Register extra commands (pipeline, review, watch, bench)
import retrai.cli.commands as _commands  # noqa: F401, E402
