"""Thin async HTTP client over the two Oniesoft backends.

The MCP server holds NO business logic — every tool is a typed wrapper around a
REST call to either:
  * the platform API (agentic_ai_be, generation + analysis), or
  * the execution API (python_tool, runs).

Auth is a single per-user API key sent as the ``x-api-key`` header (the backend's
existing convention), read once from the environment that the plugin's
``.mcp.json`` injects from ``userConfig``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# --- Configuration (injected by the plugin's .mcp.json from userConfig) --------
PLATFORM_API_URL = os.environ.get("PLATFORM_API_URL", "http://localhost:8000").rstrip("/")
EXECUTION_API_URL = os.environ.get("EXECUTION_API_URL", "http://localhost:3232").rstrip("/")
API_KEY = os.environ.get("PLATFORM_API_KEY", "")
DEFAULT_PROJECT_ID = os.environ.get("PLATFORM_PROJECT_ID", "") or None
DEFAULT_USER_ID = os.environ.get("PLATFORM_USER_ID", "") or None

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)

_client: httpx.AsyncClient | None = None


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY
    return headers


def get_client() -> httpx.AsyncClient:
    """Lazily create one shared AsyncClient for the process."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_TIMEOUT, headers=_headers())
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _result(resp: httpx.Response) -> dict[str, Any]:
    """Normalize any response into a JSON-able dict the model can read."""
    body: Any
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    return {"status_code": resp.status_code, "ok": resp.is_success, "data": body}


async def post_platform(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = await get_client().post(f"{PLATFORM_API_URL}{path}", json=payload)
    return _result(resp)


async def get_platform(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = await get_client().get(f"{PLATFORM_API_URL}{path}", params=params)
    return _result(resp)


async def post_execution(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = await get_client().post(f"{EXECUTION_API_URL}{path}", json=payload)
    return _result(resp)


async def get_execution(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = await get_client().get(f"{EXECUTION_API_URL}{path}", params=params)
    return _result(resp)
