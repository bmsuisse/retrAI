"""Tests for parallel tool execution in act_node."""

from __future__ import annotations

from retrai.agent.nodes.act import _PARALLEL_SAFE, _partition_tool_calls
from retrai.agent.state import ToolCall


def _tc(name: str, tc_id: str = "call-1") -> ToolCall:
    """Create a simple ToolCall for testing."""
    return {"id": tc_id, "name": name, "args": {}}


# ── Parallel safety checks ──────────────────────────────────


def test_parallel_safe_set():
    """Ensure read-only tools are in the parallel safe set."""
    for tool in [
        "file_read",
        "file_list",
        "grep_search",
        "find_files",
        "git_status",
        "git_log",
        "git_diff",
        "web_search",
    ]:
        assert tool in _PARALLEL_SAFE, f"{tool} should be parallel-safe"


def test_write_tools_not_parallel():
    """Write tools should NOT be in the parallel safe set."""
    for tool in ["file_write", "file_patch", "bash_exec", "run_pytest"]:
        assert tool not in _PARALLEL_SAFE, f"{tool} should NOT be parallel-safe"


# ── Partitioning ─────────────────────────────────────────────


def test_partition_empty():
    assert _partition_tool_calls([]) == []


def test_partition_single_tool():
    tcs = [_tc("file_read")]
    batches = _partition_tool_calls(tcs)
    assert len(batches) == 1
    assert len(batches[0]) == 1


def test_partition_multiple_safe_tools_batched():
    """Multiple read-only tools should be batched together."""
    tcs = [
        _tc("file_read", "c1"),
        _tc("grep_search", "c2"),
        _tc("find_files", "c3"),
    ]
    batches = _partition_tool_calls(tcs)
    assert len(batches) == 1  # All in one parallel batch
    assert len(batches[0]) == 3


def test_partition_write_tool_isolates():
    """A write tool should break parallel batching."""
    tcs = [
        _tc("file_read", "c1"),
        _tc("file_write", "c2"),
        _tc("grep_search", "c3"),
    ]
    batches = _partition_tool_calls(tcs)
    assert len(batches) == 3  # [read], [write], [grep]
    assert batches[0][0]["name"] == "file_read"
    assert batches[1][0]["name"] == "file_write"
    assert batches[2][0]["name"] == "grep_search"


def test_partition_sequential_bash():
    """bash_exec should always be sequential."""
    tcs = [
        _tc("bash_exec", "c1"),
        _tc("bash_exec", "c2"),
    ]
    batches = _partition_tool_calls(tcs)
    assert len(batches) == 2
    assert len(batches[0]) == 1
    assert len(batches[1]) == 1


def test_partition_mixed_workflow():
    """Realistic tool call sequence with mixed read/write."""
    tcs = [
        _tc("file_read", "c1"),
        _tc("git_status", "c2"),
        _tc("file_patch", "c3"),  # sequential
        _tc("file_read", "c4"),
        _tc("find_files", "c5"),
        _tc("run_pytest", "c6"),  # sequential
    ]
    batches = _partition_tool_calls(tcs)
    # Expected: [read, git_status], [patch], [read, find_files], [pytest]
    assert len(batches) == 4
    assert len(batches[0]) == 2  # read + git_status (parallel)
    assert len(batches[1]) == 1  # patch
    assert len(batches[2]) == 2  # read + find_files (parallel)
    assert len(batches[3]) == 1  # pytest
