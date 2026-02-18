"""Textual TUI for retrAI — immersive dashboard with tabs, sparklines, and live stats."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import (
    Footer,
    Header,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from retrai.tui.screens import GraphScreen
from retrai.tui.widgets import (
    DashboardSparkline,
    FileTreeWidget,
    HelpPanel,
    IterationTimeline,
    StatusPanel,
    TokenSparklineWidget,
    ToolStatsPanel,
    ToolUsageTable,
    build_gradient_logo,
)
from retrai.tui.wizard import WizardScreen

if TYPE_CHECKING:
    from retrai.config import RunConfig

# ── Tool-name → file-action mapping ──────────────────────────

_TOOL_FILE_ACTIONS: dict[str, str] = {
    "file_read": "read",
    "file_write": "write",
    "file_patch": "patch",
    "file_list": "list",
    "bash_exec": "exec",
}


class RetrAITUI(App[None]):
    """Immersive Textual TUI with tabbed dashboard, sparklines, and live stats."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("1", "switch_tab('events')", "Events"),
        ("2", "switch_tab('dashboard')", "Dashboard"),
        ("3", "switch_tab('files')", "Files"),
        ("4", "switch_tab('help')", "Help"),
        ("s", "toggle_sidebar", "Sidebar"),
        ("t", "scroll_top", "Top"),
        ("b", "scroll_bottom", "Bottom"),
        ("c", "clear_log", "Clear"),
        ("g", "show_graph", "Graph"),
        ("w", "show_wizard", "Wizard"),
        ("question_mark", "switch_tab('help')", "Help"),
    ]

    def __init__(self, cfg: RunConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self._status_panel: StatusPanel | None = None
        self._tool_stats: ToolStatsPanel | None = None
        self._token_spark: TokenSparklineWidget | None = None
        self._rich_log: RichLog | None = None
        self._timeline: IterationTimeline | None = None
        self._tool_table: ToolUsageTable | None = None
        self._dash_spark: DashboardSparkline | None = None
        self._file_tree: FileTreeWidget | None = None
        self._iter_tokens: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # Logo banner
        logo = Static(build_gradient_logo(), id="logo-label")
        yield Container(logo, id="logo-banner")

        # Main layout: sidebar + tabbed content
        with Horizontal(id="main-layout"):
            # ── Sidebar ──
            with Vertical(id="sidebar"):
                self._status_panel = StatusPanel(self.cfg)
                yield self._status_panel

                yield Static("", classes="sidebar-divider")

                self._tool_stats = ToolStatsPanel()
                yield self._tool_stats

                yield Static("", classes="sidebar-divider")

                self._token_spark = TokenSparklineWidget()
                yield self._token_spark

            # ── Content Area ──
            with Vertical(id="content-area"):
                with TabbedContent(id="tabs"):
                    # Tab 1: Event Log
                    with TabPane("📋 Events", id="events"):
                        self._rich_log = RichLog(
                            highlight=True,
                            markup=True,
                            wrap=True,
                            id="event-log",
                        )
                        yield self._rich_log

                    # Tab 2: Dashboard
                    with TabPane("📊 Dashboard", id="dashboard"):
                        with VerticalScroll(id="dashboard-pane"):
                            # Timeline
                            self._timeline = IterationTimeline()
                            yield self._timeline

                            # Grid: tool table + sparkline
                            with Horizontal(id="dashboard-grid"):
                                with Container(classes="dash-card"):
                                    self._tool_table = ToolUsageTable()
                                    yield self._tool_table

                                with Container(classes="dash-card"):
                                    self._dash_spark = DashboardSparkline()
                                    yield self._dash_spark

                    # Tab 3: Files
                    with TabPane("📁 Files", id="files"):
                        self._file_tree = FileTreeWidget()
                        yield self._file_tree

                    # Tab 4: Help
                    with TabPane("❓ Help", id="help"):
                        yield HelpPanel()

        yield Footer()

    def on_mount(self) -> None:
        self.title = f"retrAI — {self.cfg.goal}"
        self.sub_title = self.cfg.model_name
        if not self.cfg.goal:
            # No goal configured — show setup wizard
            self.action_show_wizard()
        else:
            self._write("[bold #a78bfa]▶ Starting agent…[/bold #a78bfa]")
            self.run_worker(self._run_agent(), exclusive=True)

    # ── Actions ───────────────────────────────────────────────

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab by ID."""
        try:
            self.query_one(TabbedContent).active = tab_id
        except NoMatches:
            pass

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility."""
        try:
            sidebar = self.query_one("#sidebar")
            sidebar.display = not sidebar.display
        except NoMatches:
            pass

    def action_scroll_top(self) -> None:
        """Scroll event log to top."""
        if self._rich_log:
            self._rich_log.scroll_home()

    def action_scroll_bottom(self) -> None:
        """Scroll event log to bottom."""
        if self._rich_log:
            self._rich_log.scroll_end()

    def action_clear_log(self) -> None:
        """Clear the event log."""
        if self._rich_log:
            self._rich_log.clear()
            self._write("[dim]Log cleared[/dim]")

    def action_show_graph(self) -> None:
        """Show the agent graph visualization."""
        self.push_screen(GraphScreen(hitl_enabled=self.cfg.hitl_enabled))

    def action_show_wizard(self) -> None:
        """Show the experiment setup wizard."""

        def on_wizard_result(result: RunConfig | None) -> None:
            if result is None:
                if not self.cfg.goal:
                    # No goal was ever set — quit
                    self.exit()
                return
            self.cfg = result
            self.title = f"retrAI — {self.cfg.goal}"
            self.sub_title = self.cfg.model_name
            self._write("[bold #a78bfa]▶ Starting agent…[/bold #a78bfa]")
            self.run_worker(self._run_agent(), exclusive=True)

        self.push_screen(WizardScreen(cwd=self.cfg.cwd), on_wizard_result)

    # ── Agent Runner ──────────────────────────────────────────

    async def _run_agent(self) -> None:
        from retrai.agent.graph import build_graph
        from retrai.events.bus import AsyncEventBus
        from retrai.goals.registry import get_goal

        goal = get_goal(self.cfg.goal)
        bus = AsyncEventBus()
        graph = build_graph(hitl_enabled=self.cfg.hitl_enabled)

        initial_state = {
            "messages": [],
            "pending_tool_calls": [],
            "tool_results": [],
            "goal_achieved": False,
            "goal_reason": "",
            "iteration": 0,
            "max_iterations": self.cfg.max_iterations,
            "hitl_enabled": self.cfg.hitl_enabled,
            "model_name": self.cfg.model_name,
            "cwd": self.cfg.cwd,
            "run_id": self.cfg.run_id,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "failed_strategies": [],
            "consecutive_failures": 0,
        }
        run_config = {
            "configurable": {
                "thread_id": self.cfg.run_id,
                "event_bus": bus,
                "goal": goal,
            }
        }

        if self._status_panel:
            self._status_panel.status = "RUNNING"

        q = await bus.subscribe()
        graph_task = asyncio.create_task(
            graph.ainvoke(initial_state, config=run_config)  # type: ignore[arg-type]
        )

        async def consume() -> None:
            async for event in bus.iter_events(q):
                self._handle_event(event)

        consumer_task = asyncio.create_task(consume())

        try:
            final_state = await graph_task
        except Exception as e:
            self._write(f"[bold red]✗ ERROR: {e}[/bold red]")
            final_state = None
        finally:
            await bus.close()
            await consumer_task

        if final_state:
            achieved = final_state.get("goal_achieved", False)
            if self._status_panel:
                self._status_panel.status = "ACHIEVED" if achieved else "FAILED"
                self._status_panel.iteration = final_state.get("iteration", 0)

            if achieved:
                self._write(
                    "\n[bold #4ade80]✓ GOAL ACHIEVED[/bold #4ade80]"
                )
                self.notify(
                    "Goal achieved! 🎉",
                    title="retrAI",
                    severity="information",
                )
                self.bell()
            else:
                self._write(
                    "\n[bold #f87171]✗ GOAL NOT ACHIEVED[/bold #f87171]"
                )
                self.notify(
                    "Goal not achieved.",
                    title="retrAI",
                    severity="warning",
                )

    # ── Event Handler ─────────────────────────────────────────

    def _handle_event(self, event: object) -> None:
        kind = getattr(event, "kind", "")
        payload: dict = getattr(event, "payload", {})
        iteration: int = getattr(event, "iteration", 0)

        if kind == "step_start":
            node = payload.get("node", "?")
            self._iter_tokens = 0  # Reset per-iteration token counter
            header = (
                f"\n[bold #7c3aed]┌─[/bold #7c3aed]"
                f" [bold #a78bfa]iter {iteration}[/bold #a78bfa]"
                f" [dim #64748b]▸[/dim #64748b]"
                f" [bold #e2e8f0]{node.upper()}[/bold #e2e8f0]"
            )
            self._write(header)
            if self._status_panel:
                self._status_panel.iteration = iteration
            if self._timeline and node == "plan":
                self._timeline.add_running_marker()

        elif kind == "tool_call":
            tool = payload.get("tool", "?")
            args = payload.get("args", {})
            arg_str = self._format_tool_args(tool, args)
            self._write(
                f"  [#38bdf8]⟶ {tool}[/#38bdf8] [dim]{arg_str}[/dim]"
            )
            # Track file activity
            self._track_file(tool, args)

        elif kind == "tool_result":
            tool = payload.get("tool", "?")
            err = payload.get("error", False)
            content = str(payload.get("content", ""))[:150]
            if err:
                self._write(
                    f"  [#f87171]✗ {tool}[/#f87171] [dim]{content!r}[/dim]"
                )
            else:
                self._write(
                    f"  [#4ade80]✓ {tool}[/#4ade80] [dim]{content!r}[/dim]"
                )
            # Update tool stats
            if self._tool_stats:
                self._tool_stats.record_call(tool, error=err)
            if self._tool_table:
                self._tool_table.record(tool, error=err)

        elif kind == "llm_usage":
            total = payload.get("total_tokens", 0)
            prompt = payload.get("prompt_tokens", 0)
            completion = payload.get("completion_tokens", 0)
            self._iter_tokens += total
            self._write(
                f"  [#a78bfa]◈ tokens:[/#a78bfa] "
                f"[dim]{prompt}in + {completion}out = {total}[/dim]"
            )
            if self._status_panel:
                self._status_panel.total_tokens += total

        elif kind == "goal_check":
            achieved = payload.get("achieved", False)
            reason = payload.get("reason", "")
            if achieved:
                self._write(
                    f"  [bold #4ade80]◉ GOAL: {reason}[/bold #4ade80]"
                )
            else:
                self._write(f"  [#fbbf24]◌ {reason}[/#fbbf24]")
            if self._timeline:
                self._timeline.replace_last_marker(achieved)

        elif kind == "human_check_required":
            self._write(
                "[bold #fb923c]⏸  Human approval required[/bold #fb923c]"
            )
            self.notify(
                "Human approval required",
                title="retrAI — HITL",
                severity="warning",
            )

        elif kind == "iteration_complete":
            n = payload.get("iteration", 0)
            self._write(
                f"[dim #2e1065]└───────────────────────"
                f"──── iteration {n} ──[/dim #2e1065]"
            )
            if self._status_panel:
                self._status_panel.iteration = n
            # Feed sparklines with this iteration's token usage
            if self._iter_tokens > 0:
                if self._token_spark:
                    self._token_spark.append(self._iter_tokens)
                if self._dash_spark:
                    self._dash_spark.append(self._iter_tokens)
            self._iter_tokens = 0

        elif kind == "run_end":
            status = payload.get("status", "?")
            self._write(f"\n[bold]Run ended: {status}[/bold]")

        elif kind == "error":
            err = payload.get("error", "?")
            self._write(f"[bold #f87171]ERROR: {err}[/bold #f87171]")

        elif kind == "log":
            msg = payload.get("message", "")
            self._write(f"[dim]{msg}[/dim]")

    # ── Helpers ────────────────────────────────────────────────

    def _write(self, text: str) -> None:
        if self._rich_log:
            self._rich_log.write(text)

    def _format_tool_args(self, tool: str, args: dict) -> str:
        """Format tool args for compact display."""
        if tool in ("bash_exec",):
            cmd = args.get("command", "")
            return cmd[:80] if len(cmd) <= 80 else cmd[:77] + "…"
        if tool in ("file_read", "file_write", "file_patch", "file_list"):
            path = args.get("path", "")
            return path[:60]
        if tool == "web_search":
            return args.get("query", "")[:60]
        # Generic fallback
        parts: list[str] = []
        for k, v in args.items():
            v_str = repr(v) if not isinstance(v, str) else v[:40]
            parts.append(f"{k}={v_str}")
        return ", ".join(parts)[:80]

    def _track_file(self, tool: str, args: dict) -> None:
        """Track file activity in the file tree."""
        action = _TOOL_FILE_ACTIONS.get(tool)
        if not action or not self._file_tree:
            return
        path = args.get("path") or args.get("command", "")
        if tool == "bash_exec":
            # Try to extract file paths from commands, skip generic commands
            return
        if path:
            # Normalize path
            clean = path.lstrip("./")
            if clean:
                self._file_tree.add_file(clean, action=action)
