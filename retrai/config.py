"""Run configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
        m for m in matched
        if not any(c.isdigit() and len(c) >= 8 for c in m.split("-"))
        or m.endswith("-latest")
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
    except Exception:
        all_models = []

    result: dict[str, dict[str, Any]] = {}
    for pdef in PROVIDER_DEFS:
        name = pdef["name"]
        entry: dict[str, Any] = {
            "env_var": pdef.get("env_var"),
        }
        # Copy extra fields
        for key in ("extra_env", "api_base"):
            if key in pdef:
                entry[key] = pdef[key]

        # Fetch models dynamically
        prefixes = pdef.get("prefixes", [pdef.get("prefix")])
        models: list[str] = []
        for pfx in prefixes:
            if pfx and all_models:
                models.extend(_pick_best_models(all_models, pfx))

        entry["models"] = models
        result[name] = entry

    return result


@dataclass
class RunConfig:
    """Configuration for a single agent run."""

    goal: str
    cwd: str = field(default_factory=lambda: str(Path.cwd()))
    model_name: str = "claude-sonnet-4-6"
    max_iterations: int = 20
    hitl_enabled: bool = False
    run_id: str = ""

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

