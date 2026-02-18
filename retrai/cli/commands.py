"""Extra CLI commands: pipeline, review, watch, bench."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from retrai.benchmark import BenchmarkResult
    from retrai.pipeline import PipelineResult
    from retrai.review import ReviewResult

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from retrai.cli.app import app

console = Console()


@app.command()
def pipeline(
    steps: str = typer.Argument(
        ...,
        help=("Comma-separated goal names to run in sequence, e.g. 'pytest,pyright'"),
    ),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model"),
    max_iter: int = typer.Option(30, "--max-iter", "-n", help="Max iterations per step"),
    continue_on_error: bool = typer.Option(
        False,
        "--continue-on-error",
        help="Continue to next step even if one fails",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key",
        envvar="LLM_API_KEY",
    ),
    api_base: str | None = typer.Option(None, "--api-base", help="Custom API base URL"),
) -> None:
    """Run a pipeline of goals in sequence.

    Each goal runs until achieved or max iterations, then the next
    goal starts. Context is preserved across steps.

    Examples:
        retrai pipeline "pytest,pyright"
        retrai pipeline "pytest,pyright" --continue-on-error
    """
    import os

    if api_key:
        os.environ["LLM_API_KEY"] = api_key
    if api_base:
        os.environ["LLM_API_BASE"] = api_base

    step_list = [s.strip() for s in steps.split(",") if s.strip()]
    if not step_list:
        console.print("[red]No steps provided.[/red]")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]Pipeline: {' → '.join(step_list)}[/bold]\n"
            f"Model: {model}  ·  Max iter/step: {max_iter}",
            title="[bold cyan]🔗 Pipeline Mode[/bold cyan]",
            border_style="cyan",
        )
    )

    result = asyncio.run(_run_pipeline(step_list, cwd, model, max_iter, continue_on_error))

    # Show results table
    table = Table(title="Pipeline Results", show_lines=True)
    table.add_column("Step", style="bold")
    table.add_column("Goal")
    table.add_column("Status")
    table.add_column("Iterations", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Time", justify="right")

    for i, step in enumerate(result.steps, 1):
        status = "[green]✅ Achieved[/green]" if step.achieved else "[red]❌ Failed[/red]"
        table.add_row(
            str(i),
            step.goal_name,
            status,
            str(step.iterations_used),
            f"{step.tokens_used:,}",
            f"{step.duration_seconds:.1f}s",
        )

    console.print(table)

    status_color = {
        "achieved": "green",
        "partial": "yellow",
        "failed": "red",
    }.get(result.status, "red")

    console.print(
        f"\n[bold {status_color}]Pipeline {result.status.upper()}"
        f"[/bold {status_color}] — "
        f"{result.passed}/{len(result.steps)} steps passed  ·  "
        f"Tokens: {result.total_tokens:,}  ·  "
        f"Cost: ${result.total_cost:.4f}  ·  "
        f"Time: {result.total_duration:.1f}s"
    )

    raise typer.Exit(0 if result.status == "achieved" else 1)


async def _run_pipeline(
    steps: list[str],
    cwd: str,
    model_name: str,
    max_iter: int,
    continue_on_error: bool,
) -> PipelineResult:
    """Run the pipeline."""
    from retrai.pipeline import PipelineRunner

    runner = PipelineRunner(
        steps=steps,
        cwd=cwd,
        model_name=model_name,
        max_iterations_per_step=max_iter,
        continue_on_error=continue_on_error,
    )
    return await runner.run()


@app.command()
def review(
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model"),
    staged: bool = typer.Option(False, "--staged", help="Review only staged changes"),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Save review to markdown file",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Auto-fix issues using the agent",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key",
        envvar="LLM_API_KEY",
    ),
    api_base: str | None = typer.Option(None, "--api-base", help="Custom API base URL"),
) -> None:
    """AI-powered code review of your changes.

    Reviews uncommitted changes and provides categorized feedback:
    bugs, issues, suggestions, and praise.

    Examples:
        retrai review
        retrai review --staged
        retrai review --fix
        retrai review --output report.md
    """
    import os

    if api_key:
        os.environ["LLM_API_KEY"] = api_key
    if api_base:
        os.environ["LLM_API_BASE"] = api_base

    console.print(
        Panel(
            f"Reviewing {'staged' if staged else 'all'} changes...",
            title="[bold magenta]🔍 Code Review[/bold magenta]",
            border_style="magenta",
        )
    )

    result = asyncio.run(_run_review(cwd, model, staged))

    if not result.findings and result.score == 100:
        console.print("[dim]No changes to review.[/dim]")
        raise typer.Exit(0)

    # Display findings
    for finding in result.findings:
        loc = finding.file
        if finding.line:
            loc += f":{finding.line}"

        severity_color = {
            "critical": "red",
            "warning": "yellow",
            "info": "blue",
        }.get(finding.severity, "white")

        console.print(
            f"  {finding.icon} [{severity_color}]{loc}[/{severity_color}] — {finding.message}"
        )
        if finding.suggestion:
            console.print(f"    [dim]💡 {finding.suggestion}[/dim]")

    # Summary
    score_color = "green" if result.score >= 70 else "yellow" if result.score >= 50 else "red"
    console.print(
        f"\n[bold {score_color}]Score: {result.score}/100[/bold {score_color}] — {result.summary}"
    )
    console.print(
        f"  🐛 {len(result.bugs)} bugs · "
        f"⚠️  {len(result.issues)} issues · "
        f"💡 {len(result.suggestions)} suggestions · "
        f"✅ {len(result.praises)} praises"
    )

    # Save to file
    if output:
        from pathlib import Path

        from retrai.review import format_review_markdown

        Path(output).write_text(format_review_markdown(result), encoding="utf-8")
        console.print(f"\n[dim]Report saved to {output}[/dim]")

    # Auto-fix mode
    if fix and (result.bugs or result.issues):
        issues_text = "\n".join(
            f"- {f.icon} {f.file}:{f.line or '?'}: {f.message}"
            for f in result.findings
            if f.category in ("bug", "issue")
        )
        console.print("\n[bold]Auto-fixing issues...[/bold]")
        from retrai.cli.app import solve

        solve(description=f"Fix the following code review issues:\n{issues_text}")

    raise typer.Exit(0 if result.score >= 70 else 1)


async def _run_review(cwd: str, model_name: str, staged: bool) -> ReviewResult:
    """Run the code review."""
    from retrai.review import run_review

    return await run_review(cwd=cwd, model_name=model_name, staged=staged)


@app.command()
def watch(
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    goal: str | None = typer.Option(
        None, "--goal", "-g", help="Goal to run (auto-detected if omitted)"
    ),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="LLM model"),
    max_iter: int = typer.Option(20, "--max-iter", "-n", help="Max iterations per run"),
    debounce: int = typer.Option(1000, "--debounce", "-d", help="Debounce interval in ms"),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key",
        envvar="LLM_API_KEY",
    ),
    api_base: str | None = typer.Option(None, "--api-base", help="Custom API base URL"),
) -> None:
    """Watch for file changes and auto-run goals.

    Monitors the project directory for file changes, debounces them,
    and triggers an agent run when files are modified.

    Examples:
        retrai watch
        retrai watch --goal pytest
        retrai watch --goal pyright --debounce 2000
    """
    import os

    if api_key:
        os.environ["LLM_API_KEY"] = api_key
    if api_base:
        os.environ["LLM_API_BASE"] = api_base

    console.print(
        Panel(
            f"Goal: {goal or 'auto-detect'}  ·  "
            f"Model: {model}  ·  "
            f"Debounce: {debounce}ms\n"
            f"Press Ctrl+C to stop",
            title="[bold green]👁 Watch Mode[/bold green]",
            border_style="green",
        )
    )

    async def on_change(files: list[str]) -> None:
        n = len(files)
        console.print(
            f"  [dim]{n} file{'s' if n > 1 else ''} changed: "
            f"{', '.join(files[:3])}{'...' if n > 3 else ''}[/dim]"
        )

    async def on_run_start(files: list[str]) -> None:
        console.print("\n[bold cyan]▶ Running agent...[/bold cyan]")

    async def on_run_end(goal_name: str, result: dict) -> None:
        achieved = result.get("goal_achieved", False)
        if achieved:
            console.print("[bold green]✅ Goal achieved![/bold green]")
        else:
            console.print("[yellow]⏳ Goal not yet achieved[/yellow]")
        console.print("[dim]Watching for more changes...[/dim]\n")

    from retrai.watcher import FileWatcher

    watcher = FileWatcher(
        cwd=cwd,
        goal_name=goal,
        model_name=model,
        max_iterations=max_iter,
        debounce_ms=debounce,
        on_change=on_change,
        on_run_start=on_run_start,
        on_run_end=on_run_end,
    )

    try:
        asyncio.run(watcher.run())
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


@app.command()
def bench(
    models: str = typer.Argument(
        ...,
        help=("Comma-separated model names to compare, e.g. 'claude-sonnet-4-6,gpt-4o'"),
    ),
    goal: str = typer.Option("pytest", "--goal", "-g", help="Goal to benchmark"),
    cwd: str = typer.Option(".", "--cwd", "-C", help="Project directory"),
    max_iter: int = typer.Option(20, "--max-iter", "-n", help="Max iterations per run"),
    rounds: int = typer.Option(
        1, "--rounds", "-r", help="Rounds per model (for statistical significance)"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key",
        envvar="LLM_API_KEY",
    ),
    api_base: str | None = typer.Option(None, "--api-base", help="Custom API base URL"),
) -> None:
    """Benchmark multiple models on the same task.

    Runs the same goal with different models and compares results.
    Git state is reset between each run for fairness.

    Examples:
        retrai bench "claude-sonnet-4-6,gpt-4o"
        retrai bench "claude-sonnet-4-6,o4-mini" --goal pytest --rounds 3
    """
    import os

    if api_key:
        os.environ["LLM_API_KEY"] = api_key
    if api_base:
        os.environ["LLM_API_BASE"] = api_base

    model_list = [m.strip() for m in models.split(",") if m.strip()]
    if len(model_list) < 2:
        console.print("[red]Need at least 2 models to compare.[/red]")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"Models: {', '.join(model_list)}\n"
            f"Goal: {goal}  ·  Rounds: {rounds}  ·  Max iter: {max_iter}",
            title="[bold yellow]⚡ Benchmark Mode[/bold yellow]",
            border_style="yellow",
        )
    )

    console.print("[bold red]⚠ WARNING: Git working tree will be reset between runs![/bold red]\n")

    result = asyncio.run(_run_benchmark(model_list, goal, cwd, max_iter, rounds))

    # Display comparison table
    table = Table(title=f"Benchmark: {goal}", show_lines=True)
    table.add_column("Model", style="bold")
    table.add_column("Success Rate", justify="center")
    table.add_column("Avg Iterations", justify="right")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Total Cost", justify="right")
    table.add_column("Avg Time", justify="right")

    for m in sorted(result.models, key=lambda x: x.success_rate, reverse=True):
        is_winner = m.model_name == result.winner
        name = f"🏆 {m.model_name}" if is_winner else m.model_name
        rate_color = (
            "green" if m.success_rate >= 0.8 else "yellow" if m.success_rate >= 0.5 else "red"
        )
        table.add_row(
            name,
            f"[{rate_color}]{m.success_rate:.0%}[/{rate_color}]",
            f"{m.avg_iterations:.1f}",
            f"{m.avg_tokens:,.0f}",
            f"${m.total_cost:.4f}",
            f"{m.avg_duration:.1f}s",
        )

    console.print(table)

    if result.winner:
        console.print(f"\n[bold green]🏆 Winner: {result.winner}[/bold green]")

    raise typer.Exit(0)


async def _run_benchmark(
    models: list[str],
    goal_name: str,
    cwd: str,
    max_iter: int,
    rounds: int,
) -> BenchmarkResult:
    """Run the benchmark."""
    from retrai.benchmark import BenchmarkRunner

    runner = BenchmarkRunner(
        models=models,
        goal_name=goal_name,
        cwd=cwd,
        max_iterations=max_iter,
        rounds=rounds,
    )
    return await runner.run()


@app.command()
def ml(
    data: str = typer.Argument(
        ...,
        help="Path to dataset file (CSV/JSON/Excel/Parquet)",
    ),
    target: str = typer.Argument(
        ...,
        help="Target column name to predict",
    ),
    cwd: str = typer.Option(
        ".", "--cwd", "-C", help="Project directory",
    ),
    model: str = typer.Option(
        "claude-sonnet-4-6",
        "--model", "-m",
        help="LLM model for the agent",
    ),
    metric: str = typer.Option(
        "auc",
        "--metric",
        help="Scoring metric: auc, f1, accuracy, r2, rmse, mae",
    ),
    target_value: float = typer.Option(
        0.85,
        "--target-value", "-t",
        help="Target metric value to achieve",
    ),
    task_type: str | None = typer.Option(
        None,
        "--task-type",
        help="classification or regression (auto-detected)",
    ),
    max_iter: int = typer.Option(
        30, "--max-iter", "-n", help="Max iterations",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key", "-k",
        help="API key",
        envvar="LLM_API_KEY",
    ),
    api_base: str | None = typer.Option(
        None, "--api-base", help="Custom API base URL",
    ),
) -> None:
    """Run iterative ML model optimization.

    The agent trains sklearn/xgboost/lightgbm models, evaluates them,
    and iterates to reach the target metric score.

    Examples:
        retrai ml data.csv churn --metric auc --target-value 0.90
        retrai ml data.csv price --metric r2 --target-value 0.85
    """
    import os
    from pathlib import Path

    import yaml

    if api_key:
        os.environ["LLM_API_KEY"] = api_key
    if api_base:
        os.environ["LLM_API_BASE"] = api_base

    # Write ML config to .retrai.yml
    project_dir = Path(cwd).resolve()
    config_path = project_dir / ".retrai.yml"
    config: dict = {}
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text()) or {}
        except Exception:
            config = {}

    config.update({
        "goal": "ml-optimize",
        "data_file": data,
        "target_column": target,
        "target_metric": metric,
        "target_value": target_value,
    })
    if task_type:
        config["task_type"] = task_type

    config_path.write_text(yaml.dump(config, default_flow_style=False))

    console.print(
        Panel(
            f"[bold]Dataset: {data}[/bold]\n"
            f"Target: {target}  ·  Metric: {metric.upper()} "
            f"≥ {target_value}\n"
            f"Model: {model}  ·  Max iterations: {max_iter}",
            title="[bold cyan]🧠 ML Optimization[/bold cyan]",
            border_style="cyan",
        )
    )

    result = asyncio.run(
        _run_pipeline(
            ["ml-optimize"], cwd, model, max_iter,
            continue_on_error=False,
        )
    )

    step = result.steps[0] if result.steps else None
    if step and step.achieved:
        console.print(
            f"\n[bold green]🎯 Target reached![/bold green] "
            f"{metric.upper()} ≥ {target_value}\n"
            f"Iterations: {step.iterations_used}  ·  "
            f"Tokens: {step.tokens_used:,}  ·  "
            f"Cost: ${result.total_cost:.4f}"
        )
        raise typer.Exit(0)
    else:
        console.print(
            f"\n[bold red]❌ Target not reached[/bold red] "
            f"({metric.upper()} < {target_value})\n"
            f"Iterations: {step.iterations_used if step else 0}  ·  "
            f"Tokens: {result.total_tokens:,}  ·  "
            f"Cost: ${result.total_cost:.4f}"
        )
        raise typer.Exit(1)

