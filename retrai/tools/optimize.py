"""Optimization tool — combinatorial and continuous optimization via OR-Tools and scipy.

Supports:
- Linear programming (scipy linprog)
- Nonlinear minimization (scipy minimize)
- Travelling Salesman Problem (OR-Tools routing)
- 0/1 Knapsack (OR-Tools knapsack solver)
- Linear Assignment (OR-Tools linear assignment)
- Integer/Constraint Programming (OR-Tools CP-SAT)
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_ORTOOLS_INSTALL_HINT = (
    "OR-Tools is not installed. Install with: uv pip install 'retrai[optimize]'"
)
_SCIPY_INSTALL_HINT = (
    "scipy is not installed. Install with: uv pip install 'retrai[optimize]'"
)


# ── Linear Programming (scipy) ────────────────────────────────────────────────


def _linear_program(
    c: list[float],
    a_ub: list[list[float]] | None,
    b_ub: list[float] | None,
    a_eq: list[list[float]] | None,
    b_eq: list[float] | None,
    bounds: list[tuple[float | None, float | None]] | None,
    method: str,
) -> dict[str, Any]:
    """Minimize c·x subject to A_ub·x ≤ b_ub, A_eq·x = b_eq."""
    try:
        from scipy.optimize import linprog  # type: ignore[import-untyped]
    except ImportError:
        return {"error": _SCIPY_INSTALL_HINT}

    import numpy as np  # type: ignore[import-untyped]

    result = linprog(
        c=np.array(c),
        A_ub=np.array(a_ub) if a_ub else None,
        b_ub=np.array(b_ub) if b_ub else None,
        A_eq=np.array(a_eq) if a_eq else None,
        b_eq=np.array(b_eq) if b_eq else None,
        bounds=bounds,
        method=method,
    )
    return {
        "status": result.message,
        "success": bool(result.success),
        "objective_value": float(result.fun) if result.fun is not None else None,
        "solution": [float(x) for x in result.x] if result.x is not None else None,
        "solver_info": {"method": method, "iterations": int(result.nit)},
    }


# ── Nonlinear Minimization (scipy) ────────────────────────────────────────────


def _minimize(
    expression: str,
    x0: list[float],
    method: str,
    bounds: list[tuple[float | None, float | None]] | None,
) -> dict[str, Any]:
    """Minimize a Python expression f(x) starting from x0.

    The expression is evaluated with ``x`` as a numpy array.
    Example: ``"x[0]**2 + (x[1]-1)**2"``
    """
    try:
        import numpy as np  # type: ignore[import-untyped]
        from scipy.optimize import minimize  # type: ignore[import-untyped]
    except ImportError:
        return {"error": _SCIPY_INSTALL_HINT}

    # Build a safe function from the expression
    safe_globals: dict[str, Any] = {"np": np, "__builtins__": {}}
    try:
        code = compile(expression, "<optimize>", "eval")
    except SyntaxError as e:
        return {"error": f"Invalid expression: {e}"}

    def f(x: Any) -> float:  # noqa: ANN001
        return float(eval(code, safe_globals, {"x": x}))  # noqa: S307

    result = minimize(
        f,
        x0=np.array(x0),
        method=method,
        bounds=bounds,
    )
    return {
        "status": result.message,
        "success": bool(result.success),
        "objective_value": float(result.fun),
        "solution": [float(v) for v in result.x],
        "solver_info": {
            "method": method,
            "iterations": int(result.nit),
            "function_evaluations": int(result.nfev),
        },
    }


# ── Travelling Salesman Problem (OR-Tools) ────────────────────────────────────


def _tsp(
    distance_matrix: list[list[int]],
    depot: int,
) -> dict[str, Any]:
    """Solve TSP on a symmetric distance matrix using OR-Tools routing."""
    try:
        from ortools.constraint_solver import (  # type: ignore[import-untyped]
            pywrapcp,
            routing_enums_pb2,
        )
    except ImportError:
        return {"error": _ORTOOLS_INSTALL_HINT}

    n = len(distance_matrix)
    manager = pywrapcp.RoutingIndexManager(n, 1, depot)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_params)
    if not solution:
        return {"error": "No TSP solution found", "status": "infeasible"}

    # Extract route
    route: list[int] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))

    total_distance = solution.ObjectiveValue()
    return {
        "status": "optimal",
        "success": True,
        "objective_value": int(total_distance),
        "solution": {"route": route, "total_distance": int(total_distance)},
        "solver_info": {"solver": "OR-Tools routing", "cities": n},
    }


# ── 0/1 Knapsack (OR-Tools) ───────────────────────────────────────────────────


def _knapsack(
    values: list[int],
    weights: list[int],
    capacity: int,
) -> dict[str, Any]:
    """Solve 0/1 knapsack: maximize sum(values[i]) s.t. sum(weights[i]) ≤ capacity."""
    try:
        from ortools.algorithms.python import knapsack_solver  # type: ignore[import-untyped]
    except ImportError:
        return {"error": _ORTOOLS_INSTALL_HINT}

    solver = knapsack_solver.KnapsackSolver(
        knapsack_solver.SolverType.KNAPSACK_DYNAMIC_PROGRAMMING_SOLVER,
        "knapsack",
    )
    solver.init(values, [weights], [capacity])
    total_value = solver.solve()

    selected = [i for i in range(len(values)) if solver.best_solution_contains(i)]
    total_weight = sum(weights[i] for i in selected)

    return {
        "status": "optimal",
        "success": True,
        "objective_value": int(total_value),
        "solution": {
            "selected_items": selected,
            "total_value": int(total_value),
            "total_weight": total_weight,
            "capacity": capacity,
        },
        "solver_info": {"solver": "OR-Tools knapsack (DP)"},
    }


# ── Linear Assignment (OR-Tools) ──────────────────────────────────────────────


def _assignment(
    cost_matrix: list[list[int]],
) -> dict[str, Any]:
    """Solve linear assignment problem: minimize total cost of worker-task pairs."""
    try:
        from ortools.graph.python import linear_sum_assignment  # type: ignore[import-untyped]
    except ImportError:
        return {"error": _ORTOOLS_INSTALL_HINT}

    n_workers = len(cost_matrix)
    n_tasks = len(cost_matrix[0]) if cost_matrix else 0

    end_nodes: list[int] = []
    start_nodes: list[int] = []
    arc_costs: list[int] = []

    for w in range(n_workers):
        for t in range(n_tasks):
            start_nodes.append(w)
            end_nodes.append(t)
            arc_costs.append(cost_matrix[w][t])

    assignment = linear_sum_assignment.SimpleLinearSumAssignment()
    assignment.add_arcs_with_cost(start_nodes, end_nodes, arc_costs)
    status = assignment.solve()

    status_map = {
        assignment.OPTIMAL: "optimal",
        assignment.INFEASIBLE: "infeasible",
        assignment.POSSIBLE_OVERFLOW: "possible_overflow",
    }
    status_str = status_map.get(status, "unknown")

    if status != assignment.OPTIMAL:
        return {"error": f"Assignment failed: {status_str}", "status": status_str}

    pairs = [
        {"worker": w, "task": assignment.right_mate(w), "cost": assignment.assignment_cost(w)}
        for w in range(assignment.num_nodes())
    ]
    total_cost = assignment.optimal_cost()

    return {
        "status": status_str,
        "success": True,
        "objective_value": int(total_cost),
        "solution": {"assignments": pairs, "total_cost": int(total_cost)},
        "solver_info": {"solver": "OR-Tools linear sum assignment"},
    }


# ── Integer / Constraint Programming (OR-Tools CP-SAT) ───────────────────────


def _integer_program(
    variables: list[dict[str, Any]],
    constraints: list[str],
    objective: str,
    maximize: bool,
) -> dict[str, Any]:
    """Solve an integer/constraint program using OR-Tools CP-SAT.

    Variables are declared as ``{"name": "x", "lb": 0, "ub": 10}``.
    Constraints and objective are Python expressions using variable names.

    Example::

        variables = [{"name": "x", "lb": 0, "ub": 5}, {"name": "y", "lb": 0, "ub": 5}]
        constraints = ["x + y <= 6", "2*x + y <= 8"]
        objective = "3*x + 2*y"
        maximize = True
    """
    try:
        from ortools.sat.python import cp_model  # type: ignore[import-untyped]
    except ImportError:
        return {"error": _ORTOOLS_INSTALL_HINT}

    model = cp_model.CpModel()

    # Create integer variables
    var_map: dict[str, Any] = {}
    for v in variables:
        name = v["name"]
        lb = int(v.get("lb", 0))
        ub = int(v.get("ub", 1000))
        var_map[name] = model.new_int_var(lb, ub, name)

    safe_globals: dict[str, Any] = {"__builtins__": {}}

    # Add constraints (evaluated as linear expressions)
    for constraint_expr in constraints:
        # Parse simple constraints like "x + y <= 6"
        for op in ["<=", ">=", "==", "<", ">"]:
            if op in constraint_expr:
                lhs_str, rhs_str = constraint_expr.split(op, 1)
                lhs = eval(lhs_str.strip(), safe_globals, var_map)  # noqa: S307
                rhs = int(eval(rhs_str.strip(), safe_globals, {}))  # noqa: S307
                if op == "<=":
                    model.add(lhs <= rhs)
                elif op == ">=":
                    model.add(lhs >= rhs)
                elif op == "==":
                    model.add(lhs == rhs)
                break

    # Set objective
    obj_expr = eval(objective, safe_globals, var_map)  # noqa: S307
    if maximize:
        model.maximize(obj_expr)
    else:
        model.minimize(obj_expr)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.solve(model)

    status_map = {
        cp_model.OPTIMAL: "optimal",
        cp_model.FEASIBLE: "feasible",
        cp_model.INFEASIBLE: "infeasible",
        cp_model.UNKNOWN: "unknown",
        cp_model.MODEL_INVALID: "model_invalid",
    }
    status_str = status_map.get(status, "unknown")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"error": f"No solution found: {status_str}", "status": status_str}

    solution = {v["name"]: solver.value(var_map[v["name"]]) for v in variables}
    return {
        "status": status_str,
        "success": True,
        "objective_value": solver.objective_value,
        "solution": solution,
        "solver_info": {
            "solver": "OR-Tools CP-SAT",
            "wall_time_s": round(solver.wall_time, 4),
        },
    }


# ── Public async API ──────────────────────────────────────────────────────────


async def optimize(
    action: str,
    cwd: str,
    **kwargs: Any,
) -> str:
    """Run an optimization problem.

    Args:
        action: One of ``linear_program``, ``minimize``, ``tsp``, ``knapsack``,
                ``assignment``, ``integer_program``.
        cwd: Working directory (unused, kept for API consistency).
        **kwargs: Action-specific parameters (see individual action docs).

    Returns:
        JSON string with ``status``, ``success``, ``objective_value``,
        ``solution``, and ``solver_info``.
    """
    import asyncio

    action = action.lower().strip()
    loop = asyncio.get_event_loop()

    try:
        if action == "linear_program":
            result = await loop.run_in_executor(
                None,
                lambda: _linear_program(
                    c=kwargs["c"],
                    a_ub=kwargs.get("a_ub"),
                    b_ub=kwargs.get("b_ub"),
                    a_eq=kwargs.get("a_eq"),
                    b_eq=kwargs.get("b_eq"),
                    bounds=kwargs.get("bounds"),
                    method=kwargs.get("method", "highs"),
                ),
            )
        elif action == "minimize":
            result = await loop.run_in_executor(
                None,
                lambda: _minimize(
                    expression=kwargs["expression"],
                    x0=kwargs["x0"],
                    method=kwargs.get("method", "BFGS"),
                    bounds=kwargs.get("bounds"),
                ),
            )
        elif action == "tsp":
            result = await loop.run_in_executor(
                None,
                lambda: _tsp(
                    distance_matrix=kwargs["distance_matrix"],
                    depot=kwargs.get("depot", 0),
                ),
            )
        elif action == "knapsack":
            result = await loop.run_in_executor(
                None,
                lambda: _knapsack(
                    values=kwargs["values"],
                    weights=kwargs["weights"],
                    capacity=kwargs["capacity"],
                ),
            )
        elif action == "assignment":
            result = await loop.run_in_executor(
                None,
                lambda: _assignment(cost_matrix=kwargs["cost_matrix"]),
            )
        elif action == "integer_program":
            result = await loop.run_in_executor(
                None,
                lambda: _integer_program(
                    variables=kwargs["variables"],
                    constraints=kwargs.get("constraints", []),
                    objective=kwargs["objective"],
                    maximize=kwargs.get("maximize", True),
                ),
            )
        else:
            result = {
                "error": (
                    f"Unknown action '{action}'. "
                    "Use: linear_program, minimize, tsp, knapsack, assignment, integer_program"
                )
            }
    except KeyError as e:
        result = {"error": f"Missing required parameter: {e}"}
    except Exception as e:
        result = {"error": f"Optimization failed: {type(e).__name__}: {e}"}

    return json.dumps(result, default=str)
