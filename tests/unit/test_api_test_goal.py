"""Tests for ApiTestGoal."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from retrai.goals.api_test_goal import ApiTestGoal


def _make_state() -> dict[str, Any]:
    return {
        "messages": [],
        "run_id": "test-api",
        "iteration": 1,
        "model_name": "test-model",
        "pending_tool_calls": [],
        "tool_results": [],
        "goal_achieved": False,
        "goal_reason": "",
        "max_iterations": 10,
        "stop_mode": "soft",
        "hitl_enabled": False,
        "cwd": "/tmp",
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "max_cost_usd": 0.0,
        "failed_strategies": [],
        "consecutive_failures": 0,
        "tool_cache": {},
        "mop_enabled": False,
        "mop_k": 3,
    }


@pytest.fixture()
def yml_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestApiTestGoalConfig:
    @pytest.mark.asyncio
    async def test_no_config_file(self) -> None:
        goal = ApiTestGoal()
        result = await goal.check(_make_state(), "/nonexistent_path_xyz")
        assert not result.achieved
        assert "No .retrai.yml" in result.reason

    @pytest.mark.asyncio
    async def test_no_endpoints_configured(self, yml_dir: Path) -> None:
        (yml_dir / ".retrai.yml").write_text("goal: api-test\nbase_url: http://localhost\n")
        goal = ApiTestGoal()
        result = await goal.check(_make_state(), str(yml_dir))
        assert not result.achieved
        assert "No endpoints" in result.reason

    def test_system_prompt(self) -> None:
        goal = ApiTestGoal()
        prompt = goal.system_prompt()
        assert "HTTP" in prompt
        assert "endpoint" in prompt.lower()


class TestApiTestGoalExecution:
    @pytest.mark.asyncio
    async def test_all_pass(self, yml_dir: Path) -> None:
        (yml_dir / ".retrai.yml").write_text(
            "goal: api-test\n"
            "base_url: http://localhost:9999\n"
            "endpoints:\n"
            "  - path: /health\n"
            "    expect_status: 200\n"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("retrai.goals.api_test_goal.httpx", create=True), \
             patch("httpx.AsyncClient", return_value=mock_client):
            goal = ApiTestGoal()
            # Patch _run_tests to avoid real network
            with patch(
                "retrai.goals.api_test_goal._run_tests",
                AsyncMock(return_value=[
                    {"path": "/health", "method": "GET", "passed": True, "reason": "ok",
                     "status_code": 200, "elapsed_ms": 5}
                ]),
            ):
                result = await goal.check(_make_state(), str(yml_dir))

        assert result.achieved
        assert "1 endpoints passed" in result.reason

    @pytest.mark.asyncio
    async def test_partial_fail(self, yml_dir: Path) -> None:
        (yml_dir / ".retrai.yml").write_text(
            "goal: api-test\n"
            "base_url: http://localhost:9999\n"
            "endpoints:\n"
            "  - path: /health\n"
            "    expect_status: 200\n"
            "  - path: /missing\n"
            "    expect_status: 200\n"
        )

        with patch(
            "retrai.goals.api_test_goal._run_tests",
            AsyncMock(return_value=[
                {"path": "/health", "method": "GET", "passed": True, "reason": "ok",
                 "status_code": 200, "elapsed_ms": 5},
                {"path": "/missing", "method": "GET", "passed": False,
                 "reason": "Expected status 200, got 404",
                 "status_code": 404, "elapsed_ms": 3},
            ]),
        ):
            goal = ApiTestGoal()
            result = await goal.check(_make_state(), str(yml_dir))

        assert not result.achieved
        assert "1/2" in result.reason
