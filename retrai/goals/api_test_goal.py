"""API Test Goal — run HTTP integration tests against a live base URL.

.retrai.yml example
-------------------
goal: api-test
base_url: http://localhost:8000
endpoints:
  - path: /health
    method: GET
    expect_status: 200
    expect_json:
      status: ok
  - path: /users
    method: GET
    expect_status: 200
  - path: /users
    method: POST
    json: {name: Alice}
    expect_status: 201
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from retrai.goals.base import GoalBase, GoalResult

logger = logging.getLogger(__name__)


@dataclass
class EndpointSpec:
    path: str
    method: str = "GET"
    json_body: dict[str, Any] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    expect_status: int = 200
    expect_json: dict[str, Any] | None = None
    timeout: float = 10.0


class ApiTestGoal(GoalBase):
    """Run HTTP integration tests against a configured base URL.

    Reads ``base_url`` and ``endpoints`` from ``.retrai.yml``.  All
    endpoints must return the expected HTTP status code; optionally the
    response body is checked for key/value matches.
    """

    def system_prompt(self) -> str:
        return (
            "You are an API integration testing agent.\n\n"
            "Your goal is to ensure that ALL configured HTTP endpoints return\n"
            "the expected status codes and response bodies.\n\n"
            "Strategy:\n"
            "1. Use `bash_exec` to inspect the running service (logs, process list).\n"
            "2. If the service is not running, attempt to start it.\n"
            "3. Use `bash_exec` with `curl` or `python -c 'import httpx; ...'` to test\n"
            "   individual endpoints.\n"
            "4. Fix any issues you find in the service code.\n"
            "5. Repeat until all endpoints pass.\n\n"
            "Never give up — if a service won't start, diagnose why and fix it."
        )

    async def check(self, state: Any, cwd: str) -> GoalResult:
        """Run the configured HTTP endpoint tests."""
        from pathlib import Path

        import yaml  # type: ignore[import-untyped]

        config_path = Path(cwd) / ".retrai.yml"
        if not config_path.exists():
            return GoalResult(
                achieved=False,
                reason="No .retrai.yml found",
                details={},
            )

        try:
            with config_path.open() as f:
                config: dict[str, Any] = yaml.safe_load(f) or {}
        except Exception as exc:
            return GoalResult(
                achieved=False,
                reason=f"Failed to read .retrai.yml: {exc}",
                details={},
            )

        base_url: str = config.get("base_url", "http://localhost:8000").rstrip("/")
        raw_endpoints: list[dict[str, Any]] = config.get("endpoints", [])

        if not raw_endpoints:
            return GoalResult(
                achieved=False,
                reason="No endpoints configured in .retrai.yml",
                details={},
            )

        endpoints = [
            EndpointSpec(
                path=ep.get("path", "/"),
                method=str(ep.get("method", "GET")).upper(),
                json_body=ep.get("json"),
                headers=ep.get("headers", {}),
                expect_status=int(ep.get("expect_status", 200)),
                expect_json=ep.get("expect_json"),
                timeout=float(ep.get("timeout", 10.0)),
            )
            for ep in raw_endpoints
        ]

        results = await _run_tests(base_url, endpoints)
        passed = sum(1 for r in results if r["passed"])
        total = len(results)
        pct = int(passed / total * 100) if total else 0

        failed = [r for r in results if not r["passed"]]
        if failed:
            reasons = "; ".join(
                f"{r['method']} {r['path']}: {r['reason']}" for r in failed[:5]
            )
            return GoalResult(
                achieved=False,
                reason=f"{passed}/{total} endpoints passed. Failures: {reasons}",
                details={"percentage": pct, "results": results},
            )

        return GoalResult(
            achieved=True,
            reason=f"All {total} endpoints passed ✅",
            details={"percentage": 100, "results": results},
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _run_tests(
    base_url: str,
    endpoints: list[EndpointSpec],
) -> list[dict[str, Any]]:
    """Execute each endpoint test and return result dicts."""
    results: list[dict[str, Any]] = []
    for ep in endpoints:
        result = await _test_endpoint(base_url, ep)
        results.append(result)
    return results


async def _test_endpoint(
    base_url: str,
    ep: EndpointSpec,
) -> dict[str, Any]:
    """Test a single endpoint and return a result dict."""
    try:
        import httpx
    except ImportError:
        return {
            "path": ep.path,
            "method": ep.method,
            "passed": False,
            "reason": "httpx not installed — run `uv add httpx`",
            "status_code": None,
            "elapsed_ms": None,
        }

    url = base_url + ep.path
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=ep.timeout) as client:
            request_kwargs: dict[str, Any] = {}
            if ep.json_body is not None:
                request_kwargs["json"] = ep.json_body
            if ep.headers:
                request_kwargs["headers"] = ep.headers

            method = ep.method.lower()
            http_method = getattr(client, method, None)
            if http_method is None:
                return {
                    "path": ep.path,
                    "method": ep.method,
                    "passed": False,
                    "reason": f"Unsupported HTTP method: {ep.method}",
                    "status_code": None,
                    "elapsed_ms": None,
                }

            response: httpx.Response = await http_method(url, **request_kwargs)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "path": ep.path,
            "method": ep.method,
            "passed": False,
            "reason": f"Request failed: {type(exc).__name__}: {exc}",
            "status_code": None,
            "elapsed_ms": elapsed_ms,
        }

    # Status check
    if response.status_code != ep.expect_status:
        return {
            "path": ep.path,
            "method": ep.method,
            "passed": False,
            "reason": (
                f"Expected status {ep.expect_status}, got {response.status_code}"
            ),
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        }

    # Optional JSON body assertion
    if ep.expect_json:
        try:
            body: Any = response.json()
        except Exception:
            return {
                "path": ep.path,
                "method": ep.method,
                "passed": False,
                "reason": "Response is not valid JSON",
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            }
        for key, expected_val in ep.expect_json.items():
            actual_val = body.get(key) if isinstance(body, dict) else None
            if actual_val != expected_val:
                return {
                    "path": ep.path,
                    "method": ep.method,
                    "passed": False,
                    "reason": (
                        f"JSON field {key!r}: expected {expected_val!r}, got {actual_val!r}"
                    ),
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                }

    logger.debug("PASS %s %s (%dms)", ep.method, ep.path, elapsed_ms)
    return {
        "path": ep.path,
        "method": ep.method,
        "passed": True,
        "reason": "ok",
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
    }
