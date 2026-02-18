"""retrAI TUI — immersive terminal dashboard."""

from retrai.tui.app import RetrAITUI
from retrai.tui.screens import GraphScreen
from retrai.tui.setup_graph import build_setup_graph
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

__all__ = [
    "RetrAITUI",
    "GraphScreen",
    "WizardScreen",
    "build_setup_graph",
    "StatusPanel",
    "ToolStatsPanel",
    "TokenSparklineWidget",
    "IterationTimeline",
    "ToolUsageTable",
    "DashboardSparkline",
    "FileTreeWidget",
    "HelpPanel",
    "build_gradient_logo",
]
