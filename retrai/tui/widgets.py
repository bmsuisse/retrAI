"""Custom Textual widgets for the retrAI TUI dashboard."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Label, ProgressBar, Sparkline, Static, Tree

if TYPE_CHECKING:
    from retrai.config import RunConfig

# ── Logo Art ──────────────────────────────────────────────────

LOGO_ART = r"""
 ██████╗ ███████╗████████╗██████╗  █████╗ ██╗
 ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██║
 ██████╔╝█████╗     ██║   ██████╔╝███████║██║
 ██╔══██╗██╔══╝     ██║   ██╔══██╗██╔══██║██║
 ██║  ██║███████╗   ██║   ██║  ██║██║  ██║██║
 ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
"""

GRADIENT_COLORS = [
    "#e879f9", "#d946ef", "#c026d3", "#a855f7",
    "#8b5cf6", "#7c3aed", "#6d28d9", "#5b21b6",
]

STATUS_STYLES: dict[str, tuple[str, str]] = {
    "IDLE": ("dim", "○"),
    "RUNNING": ("bold #a78bfa", "◉"),
    "ACHIEVED": ("bold #4ade80", "✓"),
    "FAILED": ("bold #f87171", "✗"),
}


def build_gradient_logo() -> Text:
    """Return the ASCII logo as a Rich Text with purple→magenta gradient."""
    text = Text()
    lines = LOGO_ART.strip("\n").split("\n")
    for i, line in enumerate(lines):
        color = GRADIENT_COLORS[min(i, len(GRADIENT_COLORS) - 1)]
        text.append(line + "\n", style=f"bold {color}")
    text.append(
        "  self-solving AI agent loop  ",
        style="italic #64748b",
    )
    return text


# ── Status Panel (sidebar) ────────────────────────────────────

class StatusPanel(Static):
    """Sidebar panel showing run config, live timer, and status."""

    status: reactive[str] = reactive("IDLE")
    iteration: reactive[int] = reactive(0)
    elapsed: reactive[float] = reactive(0.0)
    total_tokens: reactive[int] = reactive(0)

    def __init__(self, cfg: RunConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self._max = cfg.max_iterations
        self._start_time = time.monotonic()

    def compose(self) -> ComposeResult:
        from rich.markup import escape

        yield Label("⚡ STATUS", id="status-title")
        yield Label(
            f"[dim]Goal:[/dim]  [#e2e8f0]{escape(self.cfg.goal)}[/#e2e8f0]",
            classes="info-row",
        )
        model_display = self.cfg.model_name[:28]
        yield Label(
            f"[dim]Model:[/dim] [#e2e8f0]{escape(model_display)}[/#e2e8f0]",
            classes="info-row",
        )
        cwd_display = self.cfg.cwd
        if len(cwd_display) > 28:
            cwd_display = "…" + cwd_display[-27:]
        yield Label(
            f"[dim]CWD:[/dim]   [#e2e8f0]{escape(cwd_display)}[/#e2e8f0]",
            classes="info-row",
        )
        yield Label("", id="status-badge")
        yield Label("⏱  00:00:00", id="timer-label")
        yield ProgressBar(total=self._max, show_eta=False, id="iteration-progress")
        yield Label(
            f"[dim]Iter:[/dim]  [#e2e8f0]0/{self._max}[/#e2e8f0]  [dim]0%[/dim]",
            id="iter-info",
        )
        yield Label(
            "[dim]Tokens:[/dim] [#e2e8f0]0[/#e2e8f0]",
            id="token-count",
            classes="info-row",
        )

    def on_mount(self) -> None:
        self._refresh_badge()
        self.set_interval(1.0, self._tick_timer)

    def _tick_timer(self) -> None:
        if self.status == "RUNNING":
            self.elapsed = time.monotonic() - self._start_time

    def watch_status(self, value: str) -> None:
        self._refresh_badge()
        if value == "RUNNING":
            self._start_time = time.monotonic()
        self._refresh_badge()

    def watch_iteration(self, value: int) -> None:
        pct = min(100, round((value / max(self._max, 1)) * 100))
        try:
            self.query_one("#iter-info", Label).update(
                f"[dim]Iter:[/dim]  [#e2e8f0]{value}/{self._max}[/#e2e8f0]"
                f"  [dim]{pct}%[/dim]"
            )
            self.query_one("#iteration-progress", ProgressBar).update(
                progress=value,
            )
        except Exception:
            pass

    def watch_elapsed(self, value: float) -> None:
        h = int(value // 3600)
        m = int((value % 3600) // 60)
        s = int(value % 60)
        try:
            self.query_one("#timer-label", Label).update(
                f"⏱  {h:02d}:{m:02d}:{s:02d}"
            )
        except Exception:
            pass

    def watch_total_tokens(self, value: int) -> None:
        if value >= 1_000_000:
            display = f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            display = f"{value / 1_000:.1f}k"
        else:
            display = str(value)
        try:
            self.query_one("#token-count", Label).update(
                f"[dim]Tokens:[/dim] [#38bdf8]{display}[/#38bdf8]"
            )
        except Exception:
            pass

    def _refresh_badge(self) -> None:
        style, icon = STATUS_STYLES.get(self.status, ("white", "?"))
        try:
            self.query_one("#status-badge", Label).update(
                f"[{style}]  {icon}  {self.status}  [/{style}]"
            )
        except Exception:
            pass


# ── Tool Stats Panel (sidebar) ────────────────────────────────

class ToolStatsPanel(Static):
    """Compact sidebar panel showing tool call counts."""

    def __init__(self) -> None:
        super().__init__()
        self._counts: dict[str, int] = {}
        self._errors: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        yield Label("[bold #a78bfa]🔧 TOOLS[/bold #a78bfa]", id="tool-stats-title")
        yield Label("[dim]No tool calls yet[/dim]", id="tool-stats-body")

    def record_call(self, tool: str, error: bool = False) -> None:
        self._counts[tool] = self._counts.get(tool, 0) + 1
        if error:
            self._errors[tool] = self._errors.get(tool, 0) + 1
        self._refresh()

    def _refresh(self) -> None:
        if not self._counts:
            return
        lines: list[str] = []
        for tool, count in sorted(
            self._counts.items(), key=lambda x: x[1], reverse=True
        ):
            errs = self._errors.get(tool, 0)
            if errs:
                lines.append(
                    f"[#38bdf8]{tool}[/#38bdf8] "
                    f"[#e2e8f0]{count}×[/#e2e8f0] "
                    f"[#f87171]({errs}✗)[/#f87171]"
                )
            else:
                lines.append(
                    f"[#38bdf8]{tool}[/#38bdf8] "
                    f"[#4ade80]{count}×[/#4ade80]"
                )
        try:
            self.query_one("#tool-stats-body", Label).update("\n".join(lines))
        except Exception:
            pass


# ── Token Sparkline (sidebar) ─────────────────────────────────

class TokenSparklineWidget(Static):
    """Miniature sparkline showing token usage per iteration."""

    def __init__(self) -> None:
        super().__init__()
        self._data: list[float] = []

    def compose(self) -> ComposeResult:
        yield Label("[bold #a78bfa]📊 TOKENS/ITER[/bold #a78bfa]", id="spark-title")
        yield Sparkline([], id="token-sparkline")

    def append(self, tokens: int) -> None:
        self._data.append(float(tokens))
        try:
            self.query_one("#token-sparkline", Sparkline).data = list(self._data)
        except Exception:
            pass


# ── Iteration Timeline ────────────────────────────────────────

class IterationTimeline(Static):
    """Horizontal timeline showing iteration outcomes at a glance."""

    def __init__(self) -> None:
        super().__init__()
        self._markers: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label(
            "[bold #c084fc]⏳ ITERATION TIMELINE[/bold #c084fc]",
            id="timeline-title",
        )
        yield Label("[dim]Waiting…[/dim]", id="timeline-markers")

    def add_marker(self, achieved: bool) -> None:
        if achieved:
            self._markers.append("[#4ade80]●[/#4ade80]")
        else:
            self._markers.append("[#f87171]○[/#f87171]")
        try:
            self.query_one("#timeline-markers", Label).update(
                " ".join(self._markers)
            )
        except Exception:
            pass

    def add_running_marker(self) -> None:
        """Add an in-progress marker (replaced on completion)."""
        self._markers.append("[#a78bfa]◎[/#a78bfa]")
        try:
            self.query_one("#timeline-markers", Label).update(
                " ".join(self._markers)
            )
        except Exception:
            pass

    def replace_last_marker(self, achieved: bool) -> None:
        """Replace the last marker with final status."""
        if self._markers:
            self._markers.pop()
        self.add_marker(achieved)


# ── Tool Usage DataTable (dashboard tab) ──────────────────────

class ToolUsageTable(Static):
    """Full DataTable showing tool call stats."""

    def __init__(self) -> None:
        super().__init__()
        self._stats: dict[str, dict[str, int]] = {}

    def compose(self) -> ComposeResult:
        yield Label(
            "[bold #c084fc]🔧 Tool Usage[/bold #c084fc]",
            classes="dash-card-title",
        )
        table = DataTable(id="tool-table")
        table.cursor_type = "row"
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#tool-table", DataTable)
        table.add_columns("Tool", "Calls", "Errors", "Success %")

    def record(self, tool: str, error: bool = False) -> None:
        if tool not in self._stats:
            self._stats[tool] = {"calls": 0, "errors": 0}
        self._stats[tool]["calls"] += 1
        if error:
            self._stats[tool]["errors"] += 1
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        try:
            table = self.query_one("#tool-table", DataTable)
            table.clear()
            for tool, stats in sorted(
                self._stats.items(),
                key=lambda x: x[1]["calls"],
                reverse=True,
            ):
                calls = stats["calls"]
                errors = stats["errors"]
                success = round(((calls - errors) / max(calls, 1)) * 100)
                success_color = "#4ade80" if success >= 80 else (
                    "#fbbf24" if success >= 50 else "#f87171"
                )
                table.add_row(
                    f"[#38bdf8]{tool}[/#38bdf8]",
                    str(calls),
                    str(errors) if errors else "[dim]0[/dim]",
                    f"[{success_color}]{success}%[/{success_color}]",
                )
        except Exception:
            pass


# ── Dashboard Sparkline (large) ───────────────────────────────

class DashboardSparkline(Static):
    """Large sparkline for the dashboard tab."""

    def __init__(self) -> None:
        super().__init__()
        self._data: list[float] = []

    def compose(self) -> ComposeResult:
        yield Label(
            "[bold #c084fc]📈 Token Usage Over Time[/bold #c084fc]",
            classes="dash-card-title",
        )
        yield Sparkline([], id="dash-sparkline")

    def append(self, tokens: int) -> None:
        self._data.append(float(tokens))
        try:
            self.query_one("#dash-sparkline", Sparkline).data = list(self._data)
        except Exception:
            pass


# ── File Tree Widget ──────────────────────────────────────────

class FileTreeWidget(Static):
    """Tree view showing files the agent has touched."""

    def __init__(self) -> None:
        super().__init__()
        self._known_paths: set[str] = set()

    def compose(self) -> ComposeResult:
        tree: Tree[str] = Tree("📁 Agent File Activity", id="file-tree")
        tree.root.expand()
        yield tree

    def add_file(self, path: str, action: str = "read") -> None:
        """Add a file to the tree. action: read, write, patch, exec."""
        if path in self._known_paths:
            return
        self._known_paths.add(path)

        icons = {
            "read": "📖",
            "write": "✏️ ",
            "patch": "🩹",
            "exec": "⚡",
            "list": "📂",
        }
        icon = icons.get(action, "📄")

        try:
            tree = self.query_one("#file-tree", Tree)
            parts = path.split("/")

            # Build path nodes
            current_node = tree.root
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Leaf — add with icon
                    current_node.add_leaf(f"{icon} {part}")
                else:
                    # Directory — find or create
                    found = None
                    for child in current_node.children:
                        label_str = str(child.label)
                        # Strip icon prefix for comparison
                        clean = label_str.lstrip("📁📂 ")
                        if clean == part:
                            found = child
                            break
                    if found:
                        current_node = found
                    else:
                        current_node = current_node.add(f"📁 {part}")
                        current_node.expand()
        except Exception:
            pass


# ── Help Content ──────────────────────────────────────────────

HELP_TEXT = """[bold #c084fc]⌨  Keyboard Shortcuts[/bold #c084fc]

[bold #38bdf8]Navigation[/bold #38bdf8]
  [bold #e879f9]1[/bold #e879f9]          Switch to Events tab
  [bold #e879f9]2[/bold #e879f9]          Switch to Dashboard tab
  [bold #e879f9]3[/bold #e879f9]          Switch to Files tab
  [bold #e879f9]4[/bold #e879f9]          Switch to Help tab
  [bold #e879f9]s[/bold #e879f9]          Toggle sidebar visibility
  [bold #e879f9]Tab[/bold #e879f9]        Next tab

[bold #38bdf8]Event Log[/bold #38bdf8]
  [bold #e879f9]t[/bold #e879f9]          Scroll to top
  [bold #e879f9]b[/bold #e879f9]          Scroll to bottom
  [bold #e879f9]c[/bold #e879f9]          Clear event log

[bold #38bdf8]Views[/bold #38bdf8]
  [bold #e879f9]g[/bold #e879f9]          Show agent graph visualization
  [bold #e879f9]?[/bold #e879f9]          Switch to Help tab

[bold #38bdf8]General[/bold #38bdf8]
  [bold #e879f9]q[/bold #e879f9]          Quit
  [bold #e879f9]Ctrl+C[/bold #e879f9]     Quit

[bold #c084fc]🤖 Agent Graph[/bold #c084fc]

  The agent operates as a loop:

  [bold #a78bfa]START[/bold #a78bfa] → [bold #38bdf8]PLAN[/bold #38bdf8] → \
[bold #38bdf8]ACT[/bold #38bdf8] → [bold #38bdf8]EVALUATE[/bold #38bdf8] → \
[dim](repeat or end)[/dim]

  • [bold]PLAN[/bold]     — LLM decides next tool calls
  • [bold]ACT[/bold]      — Execute tool calls (bash, files, search…)
  • [bold]EVALUATE[/bold] — Check if the goal is achieved
  • [bold]HITL[/bold]     — Optional human-in-the-loop checkpoint

[bold #c084fc]📊 Dashboard[/bold #c084fc]

  The dashboard tab shows:
  • Token sparkline — usage per iteration
  • Tool usage table — calls, errors, success rate
  • Iteration timeline — visual history of pass/fail

[bold #c084fc]🌐 About retrAI[/bold #c084fc]

  retrAI is a self-solving AI agent loop.
  Give it a goal, and it keeps iterating
  until it achieves it — or hits max iterations.

  [dim]https://github.com/bmsuisse/retrAI[/dim]
"""


class HelpPanel(Vertical):
    """Help tab content with keybindings and info."""

    def compose(self) -> ComposeResult:
        yield Static(HELP_TEXT, id="help-content")
