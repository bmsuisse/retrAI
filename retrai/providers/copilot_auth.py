"""GitHub Copilot OAuth device-flow authentication.

Implements the same flow that opencode/Claude Code use to leverage an
existing Copilot subscription (Pro, Pro+, Business, Enterprise):

1. Device-code OAuth with GitHub
2. Exchange the OAuth token for a short-lived Copilot API token
3. Cache credentials locally for reuse across sessions
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# GitHub OAuth app client ID used by VS Code Copilot extension
COPILOT_CLIENT_ID = "Iv1.b507a08c87ecfe98"

# Endpoints
DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_API_BASE = "https://api.githubcopilot.com"

# Auth file location (same convention as opencode)
AUTH_DIR = Path.home() / ".local" / "share" / "retrai"
AUTH_FILE = AUTH_DIR / "auth.json"


@dataclass
class DeviceCodeResponse:
    """Parsed response from the device code request."""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class CopilotToken:
    """A short-lived Copilot API token."""

    token: str
    expires_at: int  # unix timestamp

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at - 60)  # 60s safety margin


def _load_auth() -> dict[str, Any]:
    """Load cached auth data from disk."""
    if AUTH_FILE.exists():
        with AUTH_FILE.open() as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    return {}


def _save_auth(data: dict[str, Any]) -> None:
    """Save auth data to disk."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    with AUTH_FILE.open("w") as f:
        json.dump(data, f, indent=2)


def initiate_device_flow() -> DeviceCodeResponse:
    """Start the GitHub device authorization flow.

    Returns the device code and user code for the user to authorize.
    """
    resp = httpx.post(
        DEVICE_CODE_URL,
        data={
            "client_id": COPILOT_CLIENT_ID,
            "scope": "read:user",
        },
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    data = resp.json()
    return DeviceCodeResponse(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data["verification_uri"],
        expires_in=data["expires_in"],
        interval=data.get("interval", 5),
    )


def poll_for_access_token(
    device_code: str,
    interval: int = 5,
    timeout: int = 300,
) -> str:
    """Poll GitHub until the user authorizes the device.

    Returns the OAuth access token (gho_...).
    Raises TimeoutError if the user doesn't authorize in time.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        resp = httpx.post(
            ACCESS_TOKEN_URL,
            data={
                "client_id": COPILOT_CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        if "access_token" in data:
            token = data["access_token"]
            # Cache the GitHub OAuth token
            auth = _load_auth()
            auth["github_oauth_token"] = token
            _save_auth(auth)
            return str(token)

        error = data.get("error", "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval = data.get("interval", interval + 5)
            continue
        if error == "expired_token":
            msg = "Device code expired. Please try again."
            raise TimeoutError(msg)
        if error == "access_denied":
            msg = "Authorization denied by user."
            raise PermissionError(msg)

    msg = "Timed out waiting for authorization."
    raise TimeoutError(msg)


def get_copilot_token(github_token: str) -> CopilotToken:
    """Exchange a GitHub OAuth token for a short-lived Copilot API token."""
    resp = httpx.get(
        COPILOT_TOKEN_URL,
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return CopilotToken(
        token=data["token"],
        expires_at=data["expires_at"],
    )


def get_or_refresh_copilot_token() -> CopilotToken:
    """Get a valid Copilot token, refreshing if needed.

    Uses cached GitHub OAuth token to obtain/refresh the Copilot token.
    Raises ValueError if no cached GitHub token exists.
    """
    auth = _load_auth()
    github_token = auth.get("github_oauth_token")
    if not github_token:
        msg = (
            "No GitHub Copilot credentials found. "
            "Run retrai init and select GitHub Copilot to authenticate."
        )
        raise ValueError(msg)

    # Check if we have a cached copilot token that's still valid
    cached_token = auth.get("copilot_token")
    cached_expires = auth.get("copilot_token_expires_at", 0)
    if cached_token and time.time() < (cached_expires - 60):
        return CopilotToken(token=cached_token, expires_at=cached_expires)

    # Refresh
    ct = get_copilot_token(str(github_token))
    auth["copilot_token"] = ct.token
    auth["copilot_token_expires_at"] = ct.expires_at
    _save_auth(auth)
    return ct


def list_copilot_models(github_token: str) -> list[str]:
    """Fetch available models from the Copilot API."""
    try:
        ct = get_copilot_token(github_token)
        resp = httpx.get(
            f"{COPILOT_API_BASE}/models",
            headers={
                "Authorization": f"Bearer {ct.token}",
                "Copilot-Integration-Id": "vscode-chat",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            m["id"] for m in data.get("data", [])
            if m.get("id")
        ]
    except Exception:
        # Fallback to known models if API call fails
        return [
            "claude-sonnet-4",
            "claude-sonnet-4-thinking",
            "gpt-4o",
            "gpt-4.1",
            "o4-mini",
            "o3",
            "gemini-2.5-pro",
        ]
