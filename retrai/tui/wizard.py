"""Multi-step experiment setup wizard for the retrAI TUI."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    Select,
    Static,
    Switch,
)

from retrai.config import RunConfig, get_provider_models
from retrai.goals.detector import detect_goal
from retrai.goals.registry import list_goals
from retrai.tui.setup_graph import SETUP_STEPS, STEP_LABELS
from retrai.tui.widgets import build_gradient_logo

# ── Step indicator ────────────────────────────────────────────


def _build_step_indicator(current_step: str) -> str:
    """Build a Rich-markup step progress bar like  ● ○ ○ ○."""
    parts: list[str] = []
    current_idx = SETUP_STEPS.index(current_step) if current_step in SETUP_STEPS else 0
    for i, step in enumerate(SETUP_STEPS):
        label = STEP_LABELS[step]
        if i < current_idx:
            parts.append(f"[bold #4ade80]● {label}[/bold #4ade80]")
        elif i == current_idx:
            parts.append(f"[bold #a78bfa]◉ {label}[/bold #a78bfa]")
        else:
            parts.append(f"[dim]○ {label}[/dim]")
    return "  →  ".join(parts)


# ── Wizard Screen ─────────────────────────────────────────────


class WizardScreen(ModalScreen[RunConfig | None]):
    """Multi-step experiment setup wizard.

    Walks the user through:
      1. Select a goal
      2. Configure LLM provider/model
      3. Set parameters (max iterations, HITL, cwd)
      4. Review & launch

    Dismisses with a ``RunConfig`` on launch, or ``None`` on cancel.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    WizardScreen {
        align: center middle;
        background: rgba(5, 11, 31, 0.96);
    }

    #wizard-outer {
        width: auto;
        height: auto;
        align: center middle;
    }

    #wizard-logo {
        width: auto;
        text-align: center;
        margin-bottom: 1;
    }

    #wizard-container {
        width: 80;
        max-height: 38;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #wizard-title {
        text-align: center;
        text-style: bold;
        color: #c084fc;
        margin-bottom: 1;
    }

    #step-indicator {
        text-align: center;
        margin-bottom: 1;
    }

    .wizard-body {
        height: auto;
        max-height: 22;
        padding: 1;
    }

    .field-label {
        margin-top: 1;
        color: #a78bfa;
        text-style: bold;
    }

    .field-hint {
        color: #64748b;
        text-style: italic;
    }

    .wizard-nav {
        dock: bottom;
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .wizard-nav Button {
        margin: 0 1;
    }

    #review-box {
        padding: 1 2;
        border: round #7c3aed;
        margin: 1 0;
        height: auto;
    }

    .auto-detected {
        color: #4ade80;
        text-style: italic;
    }
    """

    def __init__(self, cwd: str = ".") -> None:
        super().__init__()
        self._cwd = str(Path(cwd).resolve())
        self._detected_goal = detect_goal(self._cwd) or ""
        self._current_step_idx = 0

        # Collected values
        self._goal: str = self._detected_goal or ""
        self._provider: str = ""
        self._model_name: str = "claude-sonnet-4-6"
        self._max_iterations: int = 50
        self._hitl_enabled: bool = False

    @property
    def _current_step(self) -> str:
        return SETUP_STEPS[self._current_step_idx]

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-outer"):
            yield Static(build_gradient_logo(), id="wizard-logo")
            with Vertical(id="wizard-container"):
                yield Label(
                    "🧪 [bold #c084fc]Experiment Setup Wizard[/bold #c084fc]",
                    id="wizard-title",
                )
                yield Static(
                    _build_step_indicator(self._current_step),
                    id="step-indicator",
                )
                # Body area — content changes per step
                with VerticalScroll(classes="wizard-body", id="wizard-body"):
                    yield from self._compose_step()

                # Navigation buttons
                with Center(classes="wizard-nav"):
                    yield Button("Cancel", variant="error", id="btn-cancel")
                    yield Button("← Back", variant="default", id="btn-back", disabled=True)
                    yield Button("Next →", variant="primary", id="btn-next")

    def _compose_step(self) -> ComposeResult:
        """Yield widgets for the current step."""
        step = self._current_step

        if step == "select_goal":
            yield Label("Choose a goal for your experiment:", classes="field-label")
            if self._detected_goal:
                yield Static(
                    f"[#4ade80]Auto-detected:[/#4ade80] [bold]{self._detected_goal}[/bold]",
                    classes="auto-detected",
                )
            goals = list_goals()
            options: list[tuple[str, str]] = [(g, g) for g in goals]
            # Build select kwargs — only set value when valid
            goal_kwargs: dict[str, object] = {
                "allow_blank": True,
                "prompt": "Select a goal…",
                "id": "goal-select",
            }
            if self._goal in goals:
                goal_kwargs["value"] = self._goal
            yield Select[str](options, **goal_kwargs)  # type: ignore[arg-type]
            yield Static(
                "[dim]Goals define what the agent tries to achieve. "
                "Auto-detection scans your project files.[/dim]",
                classes="field-hint",
            )

        elif step == "configure_model":
            yield Label("Select LLM provider and model:", classes="field-label")

            providers = get_provider_models()
            provider_names = list(providers.keys())
            prov_options: list[tuple[str, str]] = [(p, p) for p in provider_names]
            prov_kwargs: dict[str, object] = {
                "allow_blank": True,
                "prompt": "Select provider…",
                "id": "provider-select",
            }
            if self._provider in provider_names:
                prov_kwargs["value"] = self._provider
            yield Select[str](prov_options, **prov_kwargs)  # type: ignore[arg-type]

            # Model select — populated on provider change
            yield Label("Model:", classes="field-label")
            model_options: list[tuple[str, str]] = [
                (self._model_name, self._model_name),
            ]
            yield Select[str](
                model_options,
                value=self._model_name,
                prompt="Select a model…",
                id="model-select",
            )
            yield Static(
                "[dim]Models are fetched from LiteLLM's registry. "
                "Pick a provider first to see available models.[/dim]",
                classes="field-hint",
            )

        elif step == "set_parameters":
            yield Label("Max iterations:", classes="field-label")
            yield Input(
                value=str(self._max_iterations),
                placeholder="50",
                type="integer",
                id="max-iter-input",
            )

            yield Label("Working directory:", classes="field-label")
            yield Input(
                value=self._cwd,
                placeholder="/path/to/project",
                id="cwd-input",
            )

            with Horizontal(id="hitl-row"):
                yield Label("Human-in-the-loop:", classes="field-label")
                yield Switch(value=self._hitl_enabled, id="hitl-switch")

            yield Static(
                "[dim]HITL adds manual approval checkpoints in the agent loop.[/dim]",
                classes="field-hint",
            )

        elif step == "review":
            yield Label("Review your experiment setup:", classes="field-label")
            summary = (
                f"[bold #a78bfa]Goal:[/bold #a78bfa]          {self._goal or '(not set)'}\n"
                f"[bold #a78bfa]Provider:[/bold #a78bfa]      {self._provider or '(auto)'}\n"
                f"[bold #a78bfa]Model:[/bold #a78bfa]         {self._model_name}\n"
                f"[bold #a78bfa]Max Iters:[/bold #a78bfa]     {self._max_iterations}\n"
                f"[bold #a78bfa]HITL:[/bold #a78bfa]          "
                f"{'✓ Enabled' if self._hitl_enabled else '✗ Disabled'}\n"
                f"[bold #a78bfa]Directory:[/bold #a78bfa]     {self._cwd}\n"
            )
            yield Static(summary, id="review-box")

    # ── Event handlers ────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-cancel":
            self.dismiss(None)
        elif btn_id == "btn-next":
            self._save_current_step()
            if self._current_step == "review":
                self._launch()
            else:
                self._go_next()
        elif btn_id == "btn-back":
            self._save_current_step()
            self._go_back()

    def on_select_changed(self, event: Select.Changed) -> None:  # type: ignore[type-arg]
        select_id = event.select.id

        if select_id == "goal-select" and isinstance(event.value, str):
            self._goal = event.value

        elif select_id == "provider-select" and isinstance(event.value, str):
            self._provider = event.value
            self._populate_models(self._provider)

        elif select_id == "model-select" and isinstance(event.value, str):
            self._model_name = event.value

    def _populate_models(self, provider: str) -> None:
        """Update the model select widget based on chosen provider."""
        try:
            model_select = self.query_one("#model-select", Select)
        except Exception:
            return

        providers = get_provider_models()
        prov_data = providers.get(provider, {})
        models: list[str] = prov_data.get("models", [])
        model_options: list[tuple[str, str]] = [(m, m) for m in models]
        model_select.set_options(model_options)

        # Auto-select first model if available
        if models:
            self._model_name = models[0]

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ── Step navigation ───────────────────────────────────────

    def _save_current_step(self) -> None:
        """Persist widget values before navigating away."""
        step = self._current_step

        if step == "select_goal":
            try:
                sel = self.query_one("#goal-select", Select)
                if isinstance(sel.value, str):
                    self._goal = sel.value
            except Exception:
                pass

        elif step == "configure_model":
            try:
                psel = self.query_one("#provider-select", Select)
                if isinstance(psel.value, str):
                    self._provider = psel.value
            except Exception:
                pass
            try:
                msel = self.query_one("#model-select", Select)
                if isinstance(msel.value, str):
                    self._model_name = msel.value
            except Exception:
                pass

        elif step == "set_parameters":
            try:
                max_iter_input = self.query_one("#max-iter-input", Input)
                val = max_iter_input.value.strip()
                if val.isdigit():
                    self._max_iterations = int(val)
            except Exception:
                pass
            try:
                cwd_input = self.query_one("#cwd-input", Input)
                if cwd_input.value.strip():
                    self._cwd = cwd_input.value.strip()
            except Exception:
                pass
            try:
                hitl_switch = self.query_one("#hitl-switch", Switch)
                self._hitl_enabled = hitl_switch.value
            except Exception:
                pass

    def _go_next(self) -> None:
        if self._current_step_idx < len(SETUP_STEPS) - 1:
            self._current_step_idx += 1
            self._rebuild_step()

    def _go_back(self) -> None:
        if self._current_step_idx > 0:
            self._current_step_idx -= 1
            self._rebuild_step()

    def _rebuild_step(self) -> None:
        """Rebuild the wizard body with the current step's widgets."""
        # Update step indicator
        try:
            indicator = self.query_one("#step-indicator", Static)
            indicator.update(_build_step_indicator(self._current_step))
        except Exception:
            pass

        # Clear and repopulate body
        try:
            body = self.query_one("#wizard-body", VerticalScroll)
            body.remove_children()
            body.mount_all(list(self._compose_step()))
        except Exception:
            pass

        # Update button states
        try:
            back_btn = self.query_one("#btn-back", Button)
            back_btn.disabled = self._current_step_idx == 0
        except Exception:
            pass

        try:
            next_btn = self.query_one("#btn-next", Button)
            if self._current_step == "review":
                next_btn.label = "🚀 Launch"
                next_btn.variant = "success"
            else:
                next_btn.label = "Next →"
                next_btn.variant = "primary"
        except Exception:
            pass

    # ── Launch ────────────────────────────────────────────────

    def _launch(self) -> None:
        """Build a RunConfig and dismiss."""
        if not self._goal:
            self.notify(
                "Please select a goal before launching.",
                severity="warning",
            )
            return

        cfg = RunConfig(
            goal=self._goal,
            cwd=self._cwd,
            model_name=self._model_name,
            max_iterations=self._max_iterations,
            hitl_enabled=self._hitl_enabled,
        )
        self.dismiss(cfg)
