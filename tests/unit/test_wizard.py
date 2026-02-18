"""Unit tests for the experiment setup wizard and setup graph."""

from __future__ import annotations

import pytest

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


# ── Setup Graph ───────────────────────────────────────────────


class TestSetupGraph:
    """Tests for the LangGraph experiment setup graph."""

    def test_build_setup_graph_compiles(self) -> None:
        from retrai.tui.setup_graph import build_setup_graph

        graph = build_setup_graph()
        assert graph is not None

    def test_setup_steps_defined(self) -> None:
        from retrai.tui.setup_graph import SETUP_STEPS

        assert len(SETUP_STEPS) == 4
        assert "select_goal" in SETUP_STEPS
        assert "configure_model" in SETUP_STEPS
        assert "set_parameters" in SETUP_STEPS
        assert "review" in SETUP_STEPS

    def test_step_labels_match_steps(self) -> None:
        from retrai.tui.setup_graph import SETUP_STEPS, STEP_LABELS

        for step in SETUP_STEPS:
            assert step in STEP_LABELS
            assert isinstance(STEP_LABELS[step], str)
            assert len(STEP_LABELS[step]) > 0

    def test_initial_state_defaults(self) -> None:
        from retrai.tui.setup_graph import make_initial_setup_state

        state = make_initial_setup_state()
        assert state["step"] == "select_goal"
        assert state["goal"] == ""
        assert state["model_name"] == "claude-sonnet-4-6"
        assert state["max_iterations"] == 50
        assert state["hitl_enabled"] is False
        assert state["completed"] is False
        assert state["cancelled"] is False

    def test_initial_state_with_detected_goal(self) -> None:
        from retrai.tui.setup_graph import make_initial_setup_state

        state = make_initial_setup_state(detected_goal="pytest")
        assert state["goal"] == "pytest"
        assert state["detected_goal"] == "pytest"

    def test_initial_state_with_cwd(self) -> None:
        from retrai.tui.setup_graph import make_initial_setup_state

        state = make_initial_setup_state(cwd="/tmp/my-project")
        assert state["cwd"] == "/tmp/my-project"

    def test_select_goal_node(self) -> None:
        from retrai.tui.setup_graph import select_goal_node

        result = select_goal_node({"step": ""})  # type: ignore[arg-type]
        assert result["step"] == "select_goal"

    def test_configure_model_node(self) -> None:
        from retrai.tui.setup_graph import configure_model_node

        result = configure_model_node({"step": ""})  # type: ignore[arg-type]
        assert result["step"] == "configure_model"

    def test_set_parameters_node(self) -> None:
        from retrai.tui.setup_graph import set_parameters_node

        result = set_parameters_node({"step": ""})  # type: ignore[arg-type]
        assert result["step"] == "set_parameters"

    def test_review_node(self) -> None:
        from retrai.tui.setup_graph import review_node

        result = review_node({"step": ""})  # type: ignore[arg-type]
        assert result["step"] == "review"

    def test_route_after_review_completed(self) -> None:
        from retrai.tui.setup_graph import route_after_review

        result = route_after_review({"completed": True, "cancelled": False})  # type: ignore[arg-type]
        assert result == "end"

    def test_route_after_review_cancelled(self) -> None:
        from retrai.tui.setup_graph import route_after_review

        result = route_after_review({"completed": False, "cancelled": True})  # type: ignore[arg-type]
        assert result == "end"

    def test_route_after_review_back(self) -> None:
        from retrai.tui.setup_graph import route_after_review

        result = route_after_review({"completed": False, "cancelled": False})  # type: ignore[arg-type]
        assert result == "select_goal"


# ── Wizard Step Indicator ─────────────────────────────────────


class TestStepIndicator:
    """Tests for the step indicator builder."""

    def test_indicator_first_step(self) -> None:
        from retrai.tui.wizard import _build_step_indicator

        result = _build_step_indicator("select_goal")
        assert "Select Goal" in result
        assert "◉" in result  # current step marker

    def test_indicator_middle_step(self) -> None:
        from retrai.tui.wizard import _build_step_indicator

        result = _build_step_indicator("set_parameters")
        assert "●" in result  # completed steps
        assert "◉" in result  # current step
        assert "○" in result  # future steps

    def test_indicator_last_step(self) -> None:
        from retrai.tui.wizard import _build_step_indicator

        result = _build_step_indicator("review")
        assert "Review & Launch" in result
        assert "◉" in result

    def test_indicator_all_steps_present(self) -> None:
        from retrai.tui.wizard import _build_step_indicator

        result = _build_step_indicator("select_goal")
        assert "Select Goal" in result
        assert "Configure Model" in result
        assert "Set Parameters" in result
        assert "Review & Launch" in result


# ── Wizard Screen Construction ────────────────────────────────


class TestWizardScreen:
    """Tests for the WizardScreen modal."""

    def test_wizard_importable(self) -> None:
        from retrai.tui.wizard import WizardScreen

        assert WizardScreen is not None

    def test_wizard_construction(self) -> None:
        from retrai.tui.wizard import WizardScreen

        screen = WizardScreen(cwd="/tmp/test")
        assert screen._current_step_idx == 0
        assert screen._current_step == "select_goal"
        assert screen._max_iterations == 50
        assert screen._hitl_enabled is False

    def test_wizard_initial_step_is_select_goal(self) -> None:
        from retrai.tui.wizard import WizardScreen

        screen = WizardScreen()
        assert screen._current_step == "select_goal"

    def test_wizard_default_model(self) -> None:
        from retrai.tui.wizard import WizardScreen

        screen = WizardScreen()
        assert screen._model_name == "claude-sonnet-4-6"


# ── Textual App Integration ──────────────────────────────────


@pytest.mark.asyncio
async def test_wizard_screen_opens_and_closes() -> None:
    """WizardScreen can be opened and closed via Textual test runner."""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from retrai.tui.wizard import WizardScreen

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Label("test")

    app = TestApp()

    async with app.run_test(size=(120, 40)) as pilot:
        wizard = WizardScreen(cwd="/tmp/test")
        app.push_screen(wizard)
        await pilot.pause()

        # Wizard should be on screen
        assert isinstance(app.screen, WizardScreen)

        # Press escape to cancel
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.asyncio
async def test_wizard_shows_goals() -> None:
    """WizardScreen shows the goal selection on step 1."""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from retrai.tui.wizard import WizardScreen

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Label("test")

    app = TestApp()

    async with app.run_test(size=(120, 40)) as pilot:
        wizard = WizardScreen(cwd="/tmp/test")
        app.push_screen(wizard)
        await pilot.pause()

        # Wizard should be showing on the goal selection step
        assert isinstance(app.screen, WizardScreen)
        assert app.screen._current_step == "select_goal"


@pytest.mark.asyncio
async def test_wizard_app_auto_opens_on_empty_goal() -> None:
    """RetrAITUI auto-opens the wizard when goal is empty."""
    from retrai.tui.app import RetrAITUI
    from retrai.tui.wizard import WizardScreen

    cfg = _make_cfg(goal="")
    app = RetrAITUI(cfg=cfg)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # The wizard should be pushed on mount
        assert isinstance(app.screen, WizardScreen)

        # Cancel the wizard
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.asyncio
async def test_wizard_keybinding_w() -> None:
    """Pressing 'w' opens the wizard from the main TUI."""
    from retrai.tui.app import RetrAITUI
    from retrai.tui.wizard import WizardScreen

    cfg = _make_cfg(goal="pytest")
    app = RetrAITUI(cfg=cfg)

    async with app.run_test(size=(120, 40)) as pilot:
        # Press 'w' to open wizard
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.screen, WizardScreen)

        # Close it
        await pilot.press("escape")
        await pilot.pause()
