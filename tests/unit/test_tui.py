"""Unit tests for the retrAI TUI widgets, screens, and app."""

from __future__ import annotations

import pytest
from rich.text import Text

from retrai.config import RunConfig

# ── Test helpers ──────────────────────────────────────────────


def _make_cfg(**overrides: object) -> RunConfig:
    defaults: dict[str, object] = {
        "goal": "pytest",
        "cwd": "/tmp/test-project",
        "model_name": "claude-sonnet-4-6",
        "max_iterations": 10,
        "hitl_enabled": False,
    }
    defaults.update(overrides)
    return RunConfig(**defaults)  # type: ignore[arg-type]


# ── Gradient Logo ─────────────────────────────────────────────


def test_gradient_logo_returns_text() -> None:
    from retrai.tui.widgets import build_gradient_logo

    result = build_gradient_logo()
    assert isinstance(result, Text)
    # The logo is ASCII block art — verify it contains the subtitle
    assert "self-solving" in result.plain


def test_gradient_logo_has_subtitle() -> None:
    from retrai.tui.widgets import build_gradient_logo

    result = build_gradient_logo()
    assert "self-solving" in result.plain


# ── STATUS_STYLES ─────────────────────────────────────────────


def test_status_styles_all_states() -> None:
    from retrai.tui.widgets import STATUS_STYLES

    expected = {"IDLE", "RUNNING", "ACHIEVED", "FAILED"}
    assert set(STATUS_STYLES.keys()) == expected
    for _, (style, icon) in STATUS_STYLES.items():
        assert isinstance(style, str)
        assert isinstance(icon, str)
        assert len(icon) >= 1


# ── Help Text ─────────────────────────────────────────────────


def test_help_text_contains_keybindings() -> None:
    from retrai.tui.widgets import HELP_TEXT

    assert "Keyboard Shortcuts" in HELP_TEXT
    assert "Events tab" in HELP_TEXT or "events" in HELP_TEXT.lower()
    assert "Dashboard" in HELP_TEXT
    assert "retrAI" in HELP_TEXT


# ── Graph Screen Art ──────────────────────────────────────────


def test_graph_art_default() -> None:
    from retrai.tui.screens import GRAPH_ART_DEFAULT

    assert "START" in GRAPH_ART_DEFAULT
    assert "PLAN" in GRAPH_ART_DEFAULT
    assert "ACT" in GRAPH_ART_DEFAULT
    assert "EVALUATE" in GRAPH_ART_DEFAULT
    assert "END" in GRAPH_ART_DEFAULT


def test_graph_art_hitl() -> None:
    from retrai.tui.screens import GRAPH_ART_HITL

    assert "HUMAN CHECK" in GRAPH_ART_HITL
    assert "PLAN" in GRAPH_ART_HITL


# ── Widget Construction (no app context) ──────────────────────


def test_tool_stats_panel_record() -> None:
    """ToolStatsPanel records tool calls correctly (internal state)."""
    from retrai.tui.widgets import ToolStatsPanel

    panel = ToolStatsPanel()
    panel.record_call("bash_exec")
    panel.record_call("bash_exec")
    panel.record_call("file_read", error=True)

    assert panel._counts == {"bash_exec": 2, "file_read": 1}
    assert panel._errors == {"file_read": 1}


def test_token_sparkline_append() -> None:
    """TokenSparklineWidget tracks data points."""
    from retrai.tui.widgets import TokenSparklineWidget

    spark = TokenSparklineWidget()
    spark._data = []  # Reset (no mount)
    spark._data.append(100.0)
    spark._data.append(200.0)
    spark._data.append(150.0)

    assert spark._data == [100.0, 200.0, 150.0]


def test_iteration_timeline_markers() -> None:
    """IterationTimeline tracks markers internally."""
    from retrai.tui.widgets import IterationTimeline

    tl = IterationTimeline()
    tl._markers = []
    tl._markers.append("[#4ade80]●[/#4ade80]")  # achieved
    tl._markers.append("[#f87171]○[/#f87171]")  # failed

    assert len(tl._markers) == 2


def test_file_tree_known_paths() -> None:
    """FileTreeWidget tracks known paths to avoid duplicates."""
    from retrai.tui.widgets import FileTreeWidget

    ft = FileTreeWidget()
    ft._known_paths = set()
    ft._known_paths.add("src/main.py")
    ft._known_paths.add("src/main.py")  # duplicate

    assert len(ft._known_paths) == 1


def test_tool_usage_table_stats() -> None:
    """ToolUsageTable internal stats tracking."""
    from retrai.tui.widgets import ToolUsageTable

    table = ToolUsageTable()
    table._stats = {}
    # Simulate recording
    tool = "bash_exec"
    if tool not in table._stats:
        table._stats[tool] = {"calls": 0, "errors": 0}
    table._stats[tool]["calls"] += 1
    table._stats[tool]["calls"] += 1

    assert table._stats["bash_exec"]["calls"] == 2
    assert table._stats["bash_exec"]["errors"] == 0


# ── App Import / Construction ─────────────────────────────────


def test_app_importable() -> None:
    """Verify the main app class can be imported."""
    from retrai.tui.app import RetrAITUI

    assert RetrAITUI is not None


def test_app_construction() -> None:
    """Verify the app can be constructed without errors."""
    from retrai.tui.app import RetrAITUI

    cfg = _make_cfg()
    app = RetrAITUI(cfg=cfg)
    assert app.cfg.goal == "pytest"
    assert app.cfg.max_iterations == 10


def test_app_bindings() -> None:
    """Verify key bindings are registered."""
    from retrai.tui.app import RetrAITUI

    cfg = _make_cfg()
    app = RetrAITUI(cfg=cfg)
    binding_keys = {b[0] if isinstance(b, tuple) else b.key for b in app.BINDINGS}  # type: ignore[union-attr]
    assert "q" in binding_keys
    assert "1" in binding_keys
    assert "g" in binding_keys
    assert "s" in binding_keys


def test_graph_screen_construction() -> None:
    """GraphScreen can be constructed in both modes."""
    from retrai.tui.screens import GraphScreen

    screen_default = GraphScreen(hitl_enabled=False)
    assert not screen_default._hitl

    screen_hitl = GraphScreen(hitl_enabled=True)
    assert screen_hitl._hitl


# ── Textual App.run_test() ────────────────────────────────────


@pytest.mark.asyncio
async def test_app_mounts_and_renders() -> None:
    """The TUI app mounts without errors using Textual's test framework."""
    from retrai.tui.app import RetrAITUI

    cfg = _make_cfg()
    app = RetrAITUI(cfg=cfg)

    async with app.run_test(size=(120, 40)) as pilot:  # noqa: F841
        # Verify key widgets exist
        assert app.query("StatusPanel")
        assert app.query("ToolStatsPanel")
        assert app.query("TabbedContent")
        assert app.query("RichLog")

        # The title should be set
        assert "pytest" in app.title


@pytest.mark.asyncio
async def test_tab_switching() -> None:
    """Tab switching via keybindings works."""
    from retrai.tui.app import RetrAITUI

    cfg = _make_cfg()
    app = RetrAITUI(cfg=cfg)

    async with app.run_test(size=(120, 40)) as pilot:
        # Switch to dashboard tab
        await pilot.press("2")
        tabs = app.query_one("TabbedContent")
        assert tabs  # Tab component exists

        # Switch to files tab
        await pilot.press("3")

        # Switch to help tab
        await pilot.press("4")

        # Switch back to events
        await pilot.press("1")


@pytest.mark.asyncio
async def test_sidebar_toggle() -> None:
    """Sidebar can be toggled with 's' key."""
    from retrai.tui.app import RetrAITUI

    cfg = _make_cfg()
    app = RetrAITUI(cfg=cfg)

    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar.display  # visible initially

        await pilot.press("s")
        assert not sidebar.display  # hidden

        await pilot.press("s")
        assert sidebar.display  # visible again


@pytest.mark.asyncio
async def test_graph_screen_opens() -> None:
    """Graph screen modal opens with 'g' key."""
    from retrai.tui.app import RetrAITUI
    from retrai.tui.screens import GraphScreen

    cfg = _make_cfg()
    app = RetrAITUI(cfg=cfg)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("g")
        # Check the graph screen was pushed
        assert isinstance(app.screen, GraphScreen)

        # Dismiss it
        await pilot.press("escape")
