"""Checkpoint: save and load AgentState to/from disk for run resumption."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = ".retrai/checkpoints"


def _serialise_message(msg: Any) -> dict[str, Any]:
    """Convert a LangChain BaseMessage to a JSON-serialisable dict."""
    content = msg.content if hasattr(msg, "content") else str(msg)
    msg_type = type(msg).__name__  # e.g. "HumanMessage", "AIMessage"
    return {"type": msg_type, "content": content}


def _deserialise_message(d: dict[str, Any]) -> Any:
    """Reconstruct a LangChain message from its serialised form."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    _TYPE_MAP = {
        "SystemMessage": SystemMessage,
        "HumanMessage": HumanMessage,
        "AIMessage": AIMessage,
        "ToolMessage": ToolMessage,
    }
    cls = _TYPE_MAP.get(d.get("type", ""), HumanMessage)
    # ToolMessage requires tool_call_id
    if cls is ToolMessage:
        return cls(content=d.get("content", ""), tool_call_id=d.get("tool_call_id", ""))
    return cls(content=d.get("content", ""))


def save_checkpoint(
    state: dict[str, Any],
    run_id: str,
    base_dir: str = _CHECKPOINT_DIR,
) -> Path:
    """Serialise *state* to ``<base_dir>/<run_id>.json`` and return the path.

    Messages (``BaseMessage`` objects) are converted to plain dicts so the
    state can be round-tripped through JSON without custom encoders.

    Args:
        state: The current ``AgentState`` dict.
        run_id: Unique identifier for this run (used as the filename stem).
        base_dir: Directory in which to store checkpoints.

    Returns:
        The path of the written checkpoint file.
    """
    checkpoint_dir = Path(base_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"{run_id}.json"

    serialisable: dict[str, Any] = {}
    for key, value in state.items():
        if key == "messages":
            serialisable[key] = [_serialise_message(m) for m in value]
        else:
            # Most values are scalars, lists of scalars, or plain dicts —
            # fall back to str for anything else that might not serialise.
            try:
                json.dumps(value)
                serialisable[key] = value
            except (TypeError, ValueError):
                serialisable[key] = str(value)

    path.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
    logger.info("Checkpoint saved: %s", path)
    return path


def load_checkpoint(
    run_id: str,
    base_dir: str = _CHECKPOINT_DIR,
) -> dict[str, Any]:
    """Load a previously saved checkpoint and reconstruct ``AgentState``.

    Args:
        run_id: Unique identifier used when the checkpoint was saved.
        base_dir: Directory where checkpoints are stored.

    Returns:
        The reconstructed ``AgentState`` dict.

    Raises:
        FileNotFoundError: If no checkpoint exists for *run_id*.
    """
    path = Path(base_dir) / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No checkpoint found for run_id={run_id!r} at {path}")

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    # Reconstruct messages
    if "messages" in raw and isinstance(raw["messages"], list):
        raw["messages"] = [_deserialise_message(m) for m in raw["messages"]]

    logger.info("Checkpoint loaded: %s", path)
    return raw


def checkpoint_path(run_id: str, base_dir: str = _CHECKPOINT_DIR) -> Path:
    """Return the expected checkpoint path for *run_id* (may not exist yet)."""
    return Path(base_dir) / f"{run_id}.json"


def list_checkpoints(base_dir: str = _CHECKPOINT_DIR) -> list[str]:
    """Return a list of all saved run_ids in *base_dir*."""
    d = Path(base_dir)
    if not d.exists():
        return []
    return [p.stem for p in sorted(d.glob("*.json"))]
