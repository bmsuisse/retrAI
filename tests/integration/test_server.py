"""Integration tests for the FastAPI server."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from retrai.server.app import create_app


@pytest.fixture(autouse=True)
def reset_run_manager():
    """Isolate tests by giving each one a fresh RunManager.

    The routes import `run_manager` directly, so we must patch all references.
    """
    import retrai.server.routes.runs as runs_module
    import retrai.server.routes.ws as ws_module
    import retrai.server.run_manager as rm_module
    from retrai.server.run_manager import RunManager

    fresh = RunManager()
    originals = (rm_module.run_manager, runs_module.run_manager, ws_module.run_manager)
    rm_module.run_manager = fresh
    runs_module.run_manager = fresh
    ws_module.run_manager = fresh
    yield
    rm_module.run_manager, runs_module.run_manager, ws_module.run_manager = originals


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Health / basic routes ──────────────────────────────────────────────────────


def test_openapi_schema_accessible(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "retrAI" in data["info"]["title"]


def test_list_runs_initially_empty(client: TestClient):
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


# ── POST /api/runs ────────────────────────────────────────────────────────────


def test_create_run_returns_run_id(client: TestClient, tmp_path: Path):
    with patch("retrai.server.run_manager.RunManager.start_run", new_callable=AsyncMock):
        r = client.post(
            "/api/runs",
            json={"goal": "pytest", "cwd": str(tmp_path)},
        )
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data
    # start_run is mocked so status stays "pending" until the real task runs
    assert data["status"] in ("pending", "running")


def test_create_run_default_model(client: TestClient, tmp_path: Path):
    with patch("retrai.server.run_manager.RunManager.start_run", new_callable=AsyncMock):
        r = client.post("/api/runs", json={"goal": "pytest", "cwd": str(tmp_path)})
    assert r.status_code == 200


def test_create_run_custom_params(client: TestClient, tmp_path: Path):
    with patch("retrai.server.run_manager.RunManager.start_run", new_callable=AsyncMock):
        r = client.post(
            "/api/runs",
            json={
                "goal": "shell-goal",
                "cwd": str(tmp_path),
                "model_name": "gpt-4o",
                "max_iterations": 5,
                "hitl_enabled": True,
            },
        )
    assert r.status_code == 200


# ── GET /api/runs/{run_id} ────────────────────────────────────────────────────


def test_get_run_not_found(client: TestClient):
    r = client.get("/api/runs/nonexistent-id")
    assert r.status_code == 404


def test_get_run_after_create(client: TestClient, tmp_path: Path):
    with patch("retrai.server.run_manager.RunManager.start_run", new_callable=AsyncMock):
        create_r = client.post("/api/runs", json={"goal": "pytest", "cwd": str(tmp_path)})
    run_id = create_r.json()["run_id"]

    r = client.get(f"/api/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == run_id
    assert data["goal"] == "pytest"


# ── GET /api/runs (list) ──────────────────────────────────────────────────────


def test_list_runs_shows_created_runs(client: TestClient, tmp_path: Path):
    with patch("retrai.server.run_manager.RunManager.start_run", new_callable=AsyncMock):
        client.post("/api/runs", json={"goal": "pytest", "cwd": str(tmp_path)})
        client.post("/api/runs", json={"goal": "shell-goal", "cwd": str(tmp_path)})
    r = client.get("/api/runs")
    assert r.status_code == 200
    runs = r.json()
    assert len(runs) == 2
    goals = {run["goal"] for run in runs}
    assert "pytest" in goals
    assert "shell-goal" in goals


# ── POST /api/runs/{run_id}/resume ─────────────────────────────────────────────


def test_resume_nonexistent_run(client: TestClient):
    r = client.post("/api/runs/nonexistent/resume", json={"decision": "approve"})
    assert r.status_code == 404


def test_resume_run_without_graph(client: TestClient, tmp_path: Path):
    with patch("retrai.server.run_manager.RunManager.start_run", new_callable=AsyncMock):
        create_r = client.post("/api/runs", json={"goal": "pytest", "cwd": str(tmp_path)})
    run_id = create_r.json()["run_id"]
    # Entry has no graph yet, so resume should 400
    r = client.post(f"/api/runs/{run_id}/resume", json={"decision": "approve"})
    assert r.status_code == 400
