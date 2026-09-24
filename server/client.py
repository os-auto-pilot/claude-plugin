"""Thin async HTTP client over the two Oniesoft backends.

The MCP server holds NO business logic — every tool is a typed wrapper around a
REST call to either:
  * the platform API (agentic_ai_be, generation + analysis), or
  * the execution API (python_tool, runs).

Auth is a single per-user API key sent as the ``x-api-key`` header (the backend's
existing convention), read from the OS environment or the workspace ``.env`` file
(see ``server/launch.py``).
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

# --- Configuration (injected by the plugin's .mcp.json from userConfig) --------
PLATFORM_API_URL = os.environ.get("PLATFORM_API_URL", "http://localhost:8000").rstrip("/")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8088").rstrip("/")
API_KEY = os.environ.get("PLATFORM_API_KEY", "")
DEFAULT_PROJECT_ID = os.environ.get("PLATFORM_PROJECT_ID", "") or None
DEFAULT_USER_ID = os.environ.get("PLATFORM_USER_ID", "") or None
DEFAULT_COMPANY_ID = os.environ.get("PLATFORM_COMPANY_ID", "") or None

# Fixed-location fallback for the per-project IDs. Some server instances are
# spawned WITHOUT project context (e.g. Claude Desktop's app-startup MCP server,
# launched from C:\Windows\system32 before any project is open), so their
# PLATFORM_PROJECT_ID / PLATFORM_USER_ID env vars are empty for the life of the
# process. launch.py writes a snapshot of the active project's IDs here whenever
# it DOES have project context; the getters below read it lazily so a
# context-less process can still resolve the IDs at request time. This is the
# same trick that already makes the API key work: read from a fixed path that
# does not depend on knowing the project directory.
_DATA_DIR = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".data"
)
_SHARED_CONFIG_PATH = os.path.join(_DATA_DIR, "active_project.json")


def _read_shared_config() -> dict:
    try:
        with open(_SHARED_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def default_project_id() -> str | None:
    """Project ID from env, falling back to the shared active-project snapshot."""
    return DEFAULT_PROJECT_ID or _read_shared_config().get("projectId")


def default_user_id() -> str | None:
    """User ID from env, falling back to the shared active-project snapshot."""
    return DEFAULT_USER_ID or _read_shared_config().get("userId")

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)

_client: httpx.AsyncClient | None = None


def _headers() -> dict[str, str]:
    # Deliberately no default Content-Type here. Every JSON call below passes
    # json=payload, which makes httpx set "application/json" itself regardless
    # of client defaults; a hardcoded default would instead force every
    # multipart call (post_backend_multipart) to go out mislabeled as
    # application/json, since a client-level header can't be unset per-request.
    headers: dict[str, str] = {}
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

async def post_backend(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = await get_client().post(f"{BACKEND_URL}{path}", json=payload)
    return _result(resp)


async def post_backend_data(
    path: str, data: dict[str, Any], headers: dict[str, str] | None = None
) -> dict[str, Any]:
    """POST application/x-www-form-urlencoded to the backend (e.g. /api/issues/save)."""
    resp = await get_client().post(f"{BACKEND_URL}{path}", data=data, headers=headers)
    return _result(resp)


async def post_backend_multipart(
    path: str, data: dict[str, Any], files: dict[str, tuple[str, bytes, str]]
) -> dict[str, Any]:
    """POST multipart/form-data to the backend (e.g. datafiles/v1/upload).

    `files` values are (filename, content_bytes, content_type) tuples. Uses
    data=/files= (never json=) so httpx computes its own multipart boundary —
    see _headers() for why the shared client carries no default Content-Type.
    """
    resp = await get_client().post(f"{BACKEND_URL}{path}", data=data, files=files)
    return _result(resp)

async def get_backend(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = await get_client().get(f"{BACKEND_URL}{path}", params=params)
    return _result(resp)

async def patch_backend(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = await get_client().patch(f"{BACKEND_URL}{path}", json=payload)
    return _result(resp)

async def put_backend(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = await get_client().put(f"{BACKEND_URL}{path}", json=payload)
    return _result(resp)
