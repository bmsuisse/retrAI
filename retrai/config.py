"""Run configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

StopMode = Literal["soft", "hard"]
AgentPattern = Literal["default", "mop", "swarm"]

# Provider definitions — models are fetched dynamically from LiteLLM
PROVIDER_DEFS: list[dict[str, Any]] = [
    {
        "name": "Anthropic (Claude)",
        "prefix": "claude-",
        "env_var": "ANTHROPIC_API_KEY",
    },
    {
        "name": "OpenAI",
        "prefixes": ["gpt-", "o1-", "o3-", "o4-", "chatgpt/"],
        "env_var": "OPENAI_API_KEY",
    },
    {
        "name": "GitHub Copilot",
        "prefix": None,
        "env_var": None,
        "auth_type": "copilot_device_flow",
    },
    {
        "name": "Google (Gemini)",
        "prefix": "gemini/",
        "env_var": "GEMINI_API_KEY",
    },
    {
        "name": "Azure OpenAI",
        "prefix": "azure/",
        "env_var": "AZURE_API_KEY",
        "extra_env": ["AZURE_API_BASE", "AZURE_API_VERSION"],
    },
    {
        "name": "Ollama (local)",
        "prefix": "ollama/",
        "env_var": None,
        "api_base": "http://localhost:11434",
    },
    {
        "name": "Other (custom)",
        "prefix": None,
        "env_var": None,
    },
]


def _pick_best_models(all_models: list[str], prefix: str, limit: int = 8) -> list[str]:
    """Filter and rank models for a provider prefix from LiteLLM's registry."""
    matched = [m for m in all_models if m.startswith(prefix)]

    # Prefer `-latest` variants and skip overly specific dated ones
    latest = [m for m in matched if m.endswith("-latest")]
    non_dated = [
        m
        for m in matched
        if not any(c.isdigit() and len(c) >= 8 for c in m.split("-")) or m.endswith("-latest")
    ]
    # Combine: latest first, then non-dated, then all — deduplicated
    ranked: list[str] = []
    seen: set[str] = set()
    for m in latest + non_dated + matched:
        if m not in seen:
            ranked.append(m)
            seen.add(m)

    return ranked[:limit]


def get_provider_models() -> dict[str, dict[str, Any]]:
    """Build provider→models mapping dynamically from LiteLLM's model registry."""
    try:
        import litellm

        all_models = sorted(litellm.model_cost.keys())
    except (ImportError, AttributeError):
        all_models = []

    result: dict[str, dict[str, Any]] = {}
    for pdef in PROVIDER_DEFS:
        name = pdef["name"]
        entry: dict[str, Any] = {
            "env_var": pdef.get("env_var"),
        }
        # Copy extra fields
        for key in ("extra_env", "api_base", "auth_type"):
            if key in pdef:
                entry[key] = pdef[key]

        # Special handling for Copilot
        if pdef.get("auth_type") == "copilot_device_flow":
            try:
                from retrai.providers.copilot_auth import (
                    _load_auth,
                    list_copilot_models,
                )

                auth = _load_auth()
                gh_token = auth.get("github_oauth_token")
                if gh_token:
                    entry["models"] = list_copilot_models(str(gh_token))
                else:
                    entry["models"] = _copilot_fallback_models()
            except (ImportError, OSError):
                entry["models"] = _copilot_fallback_models()
            result[name] = entry
            continue

        # Fetch models dynamically from LiteLLM
        prefixes = pdef.get("prefixes", [pdef.get("prefix")])
        models: list[str] = []
        for pfx in prefixes:
            if pfx and all_models:
                models.extend(_pick_best_models(all_models, pfx))

        entry["models"] = models
        result[name] = entry

    return result


def _copilot_fallback_models() -> list[str]:
    """Fallback model list for Copilot when not yet authenticated."""
    return [
        "claude-sonnet-4",
        "claude-sonnet-4-thinking",
        "gpt-4o",
        "gpt-4.1",
        "o4-mini",
        "o3",
        "gemini-2.5-pro",
    ]


@dataclass
class RunConfig:
    """Configuration for a single agent run."""

    goal: str
    cwd: str = field(default_factory=lambda: str(Path.cwd()))
    model_name: str = "claude-sonnet-4-6"
    max_iterations: int = 50
    stop_mode: StopMode = "soft"
    hitl_enabled: bool = False
    agent_pattern: AgentPattern = "default"
    mop_enabled: bool = False
    mop_k: int = 3
    sandbox_path: str = ".retrai/sandbox"
    run_id: str = ""
    max_cost_usd: float = 0.0  # 0 = no limit

    def __post_init__(self) -> None:
        if not self.run_id:
            import uuid

            self.run_id = str(uuid.uuid4())
        # Resolve to absolute path
        self.cwd = str(Path(self.cwd).resolve())


def load_config(cwd: str) -> dict[str, Any] | None:
    """Load config from .retrai.yml if it exists, else return None."""
    import yaml

    config_path = Path(cwd) / ".retrai.yml"
    if not config_path.exists():
        return None
    with config_path.open() as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else None
