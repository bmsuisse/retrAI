"""Modal screens for the retrAI TUI."""
# ruff: noqa: E501 — ASCII art graph strings are intentionally wide

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

# ── Agent Graph Visualization Screen ──────────────────────────

GRAPH_ART_DEFAULT = """
[bold #64748b]┌──────────────────────────────────────────────────────┐[/bold #64748b]
[bold #64748b]│[/bold #64748b]                                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╔═══════╗[/bold #4ade80]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]║ START ║[/bold #4ade80]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╚═══╤═══╝[/bold #4ade80]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]│[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]▼[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #a78bfa]╔═══════╗[/bold #a78bfa]     [dim]LLM decides[/dim]                  [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #a78bfa]║  PLAN ║[/bold #a78bfa]──── [dim]next actions[/dim] ──┐              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #a78bfa]╚═══╤═══╝[/bold #a78bfa]                    [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]│[/bold #64748b] [dim]has tools?[/dim]           [bold #64748b]│[/bold #64748b] [dim]no tools[/dim]  [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]▼[/bold #64748b]                        [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #38bdf8]╔═══════╗[/bold #38bdf8]     [dim]Execute[/dim]       [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #38bdf8]║  ACT  ║[/bold #38bdf8]──── [dim]tool calls[/dim]    [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #38bdf8]╚═══╤═══╝[/bold #38bdf8]                    [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]│[/bold #64748b]                        [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]▼[/bold #64748b]                        [bold #64748b]│[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #fbbf24]╔══════════╗[/bold #fbbf24]               [bold #64748b]◀──────┘[/bold #64748b]              [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #fbbf24]║ EVALUATE ║[/bold #fbbf24]── [dim]Goal met?[/dim]                     [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #fbbf24]╚═════╤════╝[/bold #fbbf24]                                   [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]     [bold #4ade80]yes[/bold #4ade80][bold #64748b]│[/bold #64748b][bold #f87171]no[/bold #f87171]                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╔══╧══╗[/bold #4ade80] [bold #64748b]└──▶[/bold #64748b] [bold #a78bfa]PLAN[/bold #a78bfa] [dim](loop)[/dim]                    [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]║ END ║[/bold #4ade80]                                         [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╚═════╝[/bold #4ade80]                                         [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]                                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]└──────────────────────────────────────────────────────┘[/bold #64748b]
"""

GRAPH_ART_HITL = """
[bold #64748b]┌──────────────────────────────────────────────────────┐[/bold #64748b]
[bold #64748b]│[/bold #64748b]                                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╔═══════╗[/bold #4ade80]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]║ START ║[/bold #4ade80]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╚═══╤═══╝[/bold #4ade80]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]│[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]▼[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #a78bfa]╔═══════╗[/bold #a78bfa]     [dim]LLM decides[/dim]                  [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #a78bfa]║  PLAN ║[/bold #a78bfa]──── [dim]next actions[/dim]                  [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #a78bfa]╚═══╤═══╝[/bold #a78bfa]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]│[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]▼[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #38bdf8]╔═══════╗[/bold #38bdf8]     [dim]Execute tools[/dim]                [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #38bdf8]║  ACT  ║[/bold #38bdf8]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #38bdf8]╚═══╤═══╝[/bold #38bdf8]                                       [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]│[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]       [bold #64748b]▼[/bold #64748b]                                           [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #fbbf24]╔══════════╗[/bold #fbbf24]                                   [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #fbbf24]║ EVALUATE ║[/bold #fbbf24]── [dim]Goal met?[/dim]                     [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #fbbf24]╚═════╤════╝[/bold #fbbf24]                                   [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]     [bold #4ade80]yes[/bold #4ade80][bold #64748b]│[/bold #64748b][bold #f87171]no[/bold #f87171]                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╔══╧══╗[/bold #4ade80] [bold #64748b]▼[/bold #64748b]                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]║ END ║[/bold #4ade80] [bold #fb923c]╔═════════════╗[/bold #fb923c]                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]   [bold #4ade80]╚═════╝[/bold #4ade80] [bold #fb923c]║ HUMAN CHECK ║[/bold #fb923c]──▶ [bold #a78bfa]PLAN[/bold #a78bfa] [dim](loop)[/dim]    [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]            [bold #fb923c]╚═════════════╝[/bold #fb923c]                      [bold #64748b]│[/bold #64748b]
[bold #64748b]│[/bold #64748b]                                                      [bold #64748b]│[/bold #64748b]
[bold #64748b]└──────────────────────────────────────────────────────┘[/bold #64748b]
"""


class GraphScreen(ModalScreen[None]):
    """Modal overlay showing the agent graph visualization."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("g", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def __init__(self, hitl_enabled: bool = False) -> None:
        super().__init__()
        self._hitl = hitl_enabled

    def compose(self) -> ComposeResult:
        with Vertical(id="graph-container"):
            yield Label(
                "[bold #c084fc]🔗 Agent State Graph[/bold #c084fc]",
                id="graph-title",
            )
            art = GRAPH_ART_HITL if self._hitl else GRAPH_ART_DEFAULT
            yield Static(art, id="graph-art")
            yield Label(
                "[dim]Press [bold]Esc[/bold] or [bold]g[/bold] to close[/dim]",
                id="graph-legend",
            )
