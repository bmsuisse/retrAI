"""LangGraph AgentState TypedDict."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ToolCall(TypedDict):
    id: str
    name: str
    args: dict[str, Any]


class ToolResult(TypedDict):
    tool_call_id: str
    name: str
    content: str
    error: bool


class AgentState(TypedDict):
    # Full conversation history (reducer appends messages)
    messages: Annotated[list[BaseMessage], add_messages]
    # Tool calls requested by the LLM in the last plan step
    pending_tool_calls: list[ToolCall]
    # Results of executed tool calls
    tool_results: list[ToolResult]
    # Goal evaluation
    goal_achieved: bool
    goal_reason: str
    # Loop control
    iteration: int
    max_iterations: int
    stop_mode: str  # "soft" or "hard"
    hitl_enabled: bool
    # Run metadata
    model_name: str
    cwd: str
    run_id: str
    # Token usage tracking
    total_tokens: int
    # Cost tracking
    estimated_cost_usd: float
    # Smart retry / reflection
    failed_strategies: list[str]
    consecutive_failures: int
    # Read-only tool result cache (key = "tool_name:json_args", value = result)
    tool_cache: dict[str, str]
