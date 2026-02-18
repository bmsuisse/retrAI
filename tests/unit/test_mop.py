import unittest
from unittest.mock import AsyncMock, MagicMock
from retrai.agent.nodes.plan import _plan_with_mop
from retrai.agent.state import AgentState

class TestMoP(unittest.IsolatedAsyncioTestCase):
    async def test_plan_with_mop(self):
        # Mock state and config
        state: AgentState = {
            "messages": [],
            "run_id": "test-run",
            "iteration": 1,
            "model_name": "test-model",
            "mop_enabled": True,
            "mop_k": 2,
            # other fields
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
            "failed_strategies": [],
            "consecutive_failures": 0,
        }
        config = MagicMock()
        
        # Mock LLMs
        base_llm = AsyncMock()
        base_llm.ainvoke.return_value = MagicMock(content="Persona plan")
        
        llm_with_tools = AsyncMock()
        llm_with_tools.ainvoke.return_value = MagicMock(
            content="Final plan",
            tool_calls=[{"name": "test_tool", "args": {}, "id": "call_1"}]
        )
        
        event_bus = AsyncMock()
        
        # Execute
        result = await _plan_with_mop(
            state=state,
            config=config,
            base_llm=base_llm,
            llm_with_tools=llm_with_tools,
            messages=[],
            system_content_base="System prompt",
            k=2,
            event_bus=event_bus
        )
        
        # Verify
        # Should have called base_llm twice (for 2 personas)
        self.assertEqual(base_llm.ainvoke.call_count, 2)
        
        # Should have called llm_with_tools once (aggregation)
        self.assertEqual(llm_with_tools.ainvoke.call_count, 1)
        
        # Result should contain the final response and tool calls
        self.assertEqual(result["messages"][0].content, "Final plan")
        self.assertEqual(len(result["pending_tool_calls"]), 1)
        self.assertEqual(result["pending_tool_calls"][0]["name"], "test_tool")
