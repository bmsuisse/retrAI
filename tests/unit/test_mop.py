"""Tests for Mixture-of-Personas (MoP) plan helper."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from retrai.agent.nodes.plan import _plan_with_mop
from retrai.agent.state import AgentState


class TestMoP(unittest.IsolatedAsyncioTestCase):
    async def test_plan_with_mop(self) -> None:
        # Mock state with all required AgentState fields
        state: AgentState = {
            "messages": [],
            "run_id": "test-run",
            "iteration": 1,
            "model_name": "test-model",
            "mop_enabled": True,
            "mop_k": 2,
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
        }
        config: MagicMock = MagicMock()

        # Mock LLMs
        base_llm = AsyncMock()
        base_llm.ainvoke.return_value = MagicMock(content="Persona plan")

        llm_with_tools = AsyncMock()
        llm_with_tools.ainvoke.return_value = MagicMock(
            content="Final plan",
            tool_calls=[{"name": "test_tool", "args": {}, "id": "call_1"}],
        )

        event_bus: AsyncMock = AsyncMock()

        # Execute
        result = await _plan_with_mop(
            state=state,
            config=config,
            base_llm=base_llm,
            llm_with_tools=llm_with_tools,
            messages=[],
            system_content_base="System prompt",
            k=2,
            event_bus=event_bus,
        )

        # Should have called base_llm twice (for 2 personas)
        self.assertEqual(base_llm.ainvoke.call_count, 2)

        # Should have called llm_with_tools once (aggregation)
        self.assertEqual(llm_with_tools.ainvoke.call_count, 1)

        # Result should contain the final response and tool calls
        self.assertEqual(result["messages"][0].content, "Final plan")
        self.assertEqual(len(result["pending_tool_calls"]), 1)
        self.assertEqual(result["pending_tool_calls"][0]["name"], "test_tool")

    async def test_plan_with_mop_no_event_bus(self) -> None:
        """MoP should work without an event bus (no publish calls)."""
        state: AgentState = {
            "messages": [],
            "run_id": "test-run-2",
            "iteration": 0,
            "model_name": "test-model",
            "mop_enabled": True,
            "mop_k": 1,
            "pending_tool_calls": [],
            "tool_results": [],
            "goal_achieved": False,
            "goal_reason": "",
            "max_iterations": 5,
            "stop_mode": "hard",
            "hitl_enabled": False,
            "cwd": "/tmp",
            "total_tokens": 100,
            "estimated_cost_usd": 0.001,
            "max_cost_usd": 0.0,
            "failed_strategies": [],
            "consecutive_failures": 0,
            "tool_cache": {},
        }

        base_llm = AsyncMock()
        base_llm.ainvoke.return_value = MagicMock(content="Solo persona plan")

        llm_with_tools = AsyncMock()
        llm_with_tools.ainvoke.return_value = MagicMock(
            content="Aggregated", tool_calls=[]
        )

        result = await _plan_with_mop(
            state=state,
            config=MagicMock(),
            base_llm=base_llm,
            llm_with_tools=llm_with_tools,
            messages=[],
            system_content_base="",
            k=1,
            event_bus=None,
        )

        self.assertEqual(base_llm.ainvoke.call_count, 1)
        self.assertEqual(result["pending_tool_calls"], [])
        # Token accumulation: existing 100 + new usage
        self.assertGreaterEqual(result["total_tokens"], 100)
