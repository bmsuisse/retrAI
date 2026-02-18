"""Tests for the optimize tool — linear programming, knapsack, TSP, assignment, minimize."""

from __future__ import annotations

import json

import pytest

from retrai.tools.optimize import (
    _assignment,
    _integer_program,
    _knapsack,
    _linear_program,
    _minimize,
    _tsp,
    optimize,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_ORTOOLS_MISSING = False
try:
    import ortools  # noqa: F401
except ImportError:
    _ORTOOLS_MISSING = True

_SCIPY_MISSING = False
try:
    import scipy  # noqa: F401
except ImportError:
    _SCIPY_MISSING = True

skip_ortools = pytest.mark.skipif(_ORTOOLS_MISSING, reason="ortools not installed")
skip_scipy = pytest.mark.skipif(_SCIPY_MISSING, reason="scipy not installed")


# ── linear_program ────────────────────────────────────────────────────────────


@skip_scipy
def test_linear_program_basic() -> None:
    """Minimize -x1 - 2*x2 s.t. x1 + x2 <= 4, x1,x2 >= 0 → optimal at (0,4), obj=-8."""
    result = _linear_program(
        c=[-1.0, -2.0],
        a_ub=[[1.0, 1.0]],
        b_ub=[4.0],
        a_eq=None,
        b_eq=None,
        bounds=[(0, None), (0, None)],
        method="highs",
    )
    assert result["success"] is True
    assert result["objective_value"] is not None
    assert abs(result["objective_value"] - (-8.0)) < 0.01


@skip_scipy
def test_linear_program_infeasible() -> None:
    """Infeasible LP: x >= 5 and x <= 3."""
    result = _linear_program(
        c=[1.0],
        a_ub=[[-1.0]],
        b_ub=[-5.0],
        a_eq=None,
        b_eq=None,
        bounds=[(None, 3.0)],
        method="highs",
    )
    assert result["success"] is False


# ── minimize ──────────────────────────────────────────────────────────────────


@skip_scipy
def test_minimize_quadratic() -> None:
    """Minimize x[0]**2 — solution should be near 0."""
    result = _minimize(
        expression="x[0]**2",
        x0=[5.0],
        method="BFGS",
        bounds=None,
    )
    assert result["success"] is True
    assert abs(result["objective_value"]) < 1e-6
    assert abs(result["solution"][0]) < 1e-4


@skip_scipy
def test_minimize_rosenbrock() -> None:
    """Minimize Rosenbrock function — solution near (1, 1)."""
    result = _minimize(
        expression="(1 - x[0])**2 + 100*(x[1] - x[0]**2)**2",
        x0=[0.0, 0.0],
        method="L-BFGS-B",
        bounds=None,
    )
    assert result["success"] is True
    assert abs(result["solution"][0] - 1.0) < 0.01
    assert abs(result["solution"][1] - 1.0) < 0.01


@skip_scipy
def test_minimize_invalid_expression() -> None:
    """Invalid expression returns an error."""
    result = _minimize(
        expression="x[0] +++ invalid",
        x0=[0.0],
        method="BFGS",
        bounds=None,
    )
    assert "error" in result


# ── knapsack ──────────────────────────────────────────────────────────────────


@skip_ortools
def test_knapsack_basic() -> None:
    """Classic knapsack: items with values [60,100,120], weights [10,20,30], cap=50."""
    result = _knapsack(
        values=[60, 100, 120],
        weights=[10, 20, 30],
        capacity=50,
    )
    assert result["success"] is True
    # Optimal: items 1 and 2 (0-indexed) → value=220, weight=50
    assert result["objective_value"] == 220
    assert set(result["solution"]["selected_items"]) == {1, 2}


@skip_ortools
def test_knapsack_all_fit() -> None:
    """All items fit — all should be selected."""
    result = _knapsack(
        values=[10, 20, 30],
        weights=[1, 2, 3],
        capacity=100,
    )
    assert result["success"] is True
    assert result["objective_value"] == 60
    assert len(result["solution"]["selected_items"]) == 3


# ── TSP ───────────────────────────────────────────────────────────────────────


@skip_ortools
def test_tsp_basic() -> None:
    """4-city TSP — route should be a valid permutation visiting all cities."""
    dist = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0],
    ]
    result = _tsp(distance_matrix=dist, depot=0)
    assert result["success"] is True
    route = result["solution"]["route"]
    # Route starts and ends at depot
    assert route[0] == 0
    assert route[-1] == 0
    # All cities visited
    assert set(route) == {0, 1, 2, 3}


# ── Assignment ────────────────────────────────────────────────────────────────


@skip_ortools
def test_assignment_basic() -> None:
    """3×3 cost matrix — verify optimal total cost."""
    cost = [
        [4, 1, 3],
        [2, 0, 5],
        [3, 2, 2],
    ]
    result = _assignment(cost_matrix=cost)
    assert result["success"] is True
    # Optimal: worker0→task1(1), worker1→task0(2), worker2→task2(2) = 5
    # OR worker0→task1(1), worker1→task1... let solver decide
    assert result["objective_value"] <= 5  # at most 5 (optimal is 5)
    assignments = result["solution"]["assignments"]
    assert len(assignments) == 3
    # Each worker assigned exactly one task
    tasks = [a["task"] for a in assignments]
    assert len(set(tasks)) == 3


# ── Integer Program ───────────────────────────────────────────────────────────


@skip_ortools
def test_integer_program_basic() -> None:
    """Maximize 3x + 2y s.t. x+y<=6, 2x+y<=8, x,y>=0 integer."""
    result = _integer_program(
        variables=[
            {"name": "x", "lb": 0, "ub": 10},
            {"name": "y", "lb": 0, "ub": 10},
        ],
        constraints=["x + y <= 6", "2*x + y <= 8"],
        objective="3*x + 2*y",
        maximize=True,
    )
    assert result["success"] is True
    # Optimal: x=2, y=4 → obj=14
    assert result["objective_value"] == 14
    assert result["solution"]["x"] == 2
    assert result["solution"]["y"] == 4


# ── async optimize() wrapper ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_optimize_unknown_action() -> None:
    """Unknown action returns a JSON error."""
    raw = await optimize(action="foobar", cwd="/tmp")
    result = json.loads(raw)
    assert "error" in result
    assert "foobar" in result["error"]


@pytest.mark.asyncio
async def test_optimize_missing_param() -> None:
    """Missing required parameter returns a JSON error."""
    raw = await optimize(action="knapsack", cwd="/tmp", values=[1, 2])
    result = json.loads(raw)
    assert "error" in result


@pytest.mark.asyncio
@skip_scipy
async def test_optimize_linear_program_via_wrapper() -> None:
    """End-to-end: optimize() dispatches linear_program correctly."""
    raw = await optimize(
        action="linear_program",
        cwd="/tmp",
        c=[-1.0, -2.0],
        a_ub=[[1.0, 1.0]],
        b_ub=[4.0],
        bounds=[(0, None), (0, None)],
    )
    result = json.loads(raw)
    assert result["success"] is True


def test_missing_ortools_returns_hint() -> None:
    """When ortools is missing, knapsack returns the install hint."""
    import unittest.mock as mock

    with mock.patch.dict("sys.modules", {"ortools": None, "ortools.algorithms": None,
                                          "ortools.algorithms.python": None,
                                          "ortools.algorithms.python.knapsack_solver": None}):
        # Re-import to trigger the ImportError path
        import importlib
        import retrai.tools.optimize as opt_mod
        importlib.reload(opt_mod)
        result = opt_mod._knapsack([10, 20], [5, 10], 15)
        # Should return error dict
        assert "error" in result
