"""Launcher for the Oniesoft MCP server.

``server/venv_launcher.py`` runs this with the Python of the plugin's persistent
venv, which already has ``server/requirements.txt`` installed — see that file
for how the venv is built and shared across concurrent starts.

Workspace-level credentials (``PLATFORM_API_KEY`` in ``.env`` or the OS
environment) and per-project settings (company/user/project ID, API URLs in
``config.json``) are read from the user's project directory, not from Claude's
``userConfig`` UI — which the desktop app does not collect today.

``--bootstrap-only`` makes this exit immediately. The SessionStart hook passes it
to the venv launcher, which builds the venv and stops before reaching this file.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import MutableMapping

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ${CLAUDE_PLUGIN_DATA} is exported to plugin subprocesses; fall back to a local
# dir for `--plugin-dir` dev use where it may be unset.
DATA_DIR = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(PLUGIN_ROOT, ".data")

SNAPSHOT_PATH = os.path.join(DATA_DIR, "active_project.json")

#: Settings loaded from the workspace ``.env`` (gap-fill only).
_ENV_OVERRIDABLE = ("PLATFORM_API_KEY", "PLATFORM_API_URL", "BACKEND_URL")


def _read_snapshot() -> dict:
    try:
        with open(SNAPSHOT_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _write_snapshot(updates: dict) -> None:
    if not updates:
        return
    snapshot = _read_snapshot()
    snapshot.update(updates)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
    except Exception:
        pass


def _is_placeholder(val: str) -> bool:
    """True if `val` is an unsubstituted ``${VAR}`` template rather than a value."""
    return val.startswith("${") and val.endswith("}")


def _strip_unresolved(env: MutableMapping[str, str]) -> None:
    """Drop env vars still holding an unsubstituted ``${VAR}`` placeholder.

    Claude may inject the literal string ``${user_config.platform_api_key}``
    when the desktop UI never collected a userConfig value.
    """
    for key, val in list(env.items()):
        if isinstance(val, str) and _is_placeholder(val):
            del env[key]


def _load_env_file(env: MutableMapping[str, str], project_dir: str) -> None:
    """Fill any still-unset setting from the workspace's ``.env``.

    Only fills gaps — never overrides a value already present in the process
    environment (highest precedence).
    """
    path = os.path.join(project_dir, ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'\"")
        if not val or _is_placeholder(val):
            continue
        if key not in _ENV_OVERRIDABLE:
            continue
        if not env.get(key):
            env[key] = val


def _inject_project_config(env: MutableMapping[str, str], project_dir: str) -> None:
    """Read the project's config.json and inject company/user/project ID and API URLs."""
    field_env_map = {
        "companyId": "PLATFORM_COMPANY_ID",
        "userId": "PLATFORM_USER_ID",
        "projectId": "PLATFORM_PROJECT_ID",
        "platformApiUrl": "PLATFORM_API_URL",
        "backendUrl": "BACKEND_URL",
    }

    project_config = os.path.join(project_dir, "config.json")
    try:
        with open(project_config, encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception:
        return

    for field, env_var in field_env_map.items():
        val = config.get(field)
        if val and not env.get(env_var):
            env[env_var] = str(val)

    snapshot = {
        key: config[key]
        for key in ("projectId", "userId", "companyId")
        if config.get(key)
    }
    if snapshot.get("projectId"):
        _write_snapshot(snapshot)


def _inject_api_key_from_credentials(env: MutableMapping[str, str]) -> None:
    """Fallback: read API key from ~/.claude/.credentials.json (CLI install path).

    Only used when PLATFORM_API_KEY is still unset after OS env and workspace
    ``.env`` — keeps backward compatibility for users who installed via
    ``claude plugin install --config platform_api_key=...``.
    """
    if env.get("PLATFORM_API_KEY"):
        return

    plugin_name = "auto-pilot"
    server_name = "auto-pilot"
    try:
        with open(os.path.join(PLUGIN_ROOT, "config.json"), encoding="utf-8") as fh:
            config_data = json.load(fh)
        server_name = next(iter(config_data.get("mcpServers", {})), server_name)
    except Exception:
        pass

    candidate_keys = [f"{plugin_name}@{server_name}"]
    if server_name != "oniesoft":
        candidate_keys.append(f"{plugin_name}@oniesoft")

    creds_path = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
    try:
        with open(creds_path, encoding="utf-8") as fh:
            creds = json.load(fh)
        plugin_secrets = creds.get("pluginSecrets", {})
        for key in candidate_keys:
            api_key = plugin_secrets.get(key, {}).get("platform_api_key")
            if api_key:
                env["PLATFORM_API_KEY"] = str(api_key)
                break
    except Exception:
        pass


def _has_project_files(path: str) -> bool:
    return os.path.isfile(os.path.join(path, ".env")) or os.path.isfile(
        os.path.join(path, "config.json")
    )


def _resolve_project_dir() -> str:
    """Locate the workspace holding this project's ``.env`` / ``config.json``."""
    project_dir = os.path.expanduser(
        os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    )

    if _has_project_files(project_dir):
        _write_snapshot({"workspaceDir": project_dir})
        return project_dir

    recorded = _read_snapshot().get("workspaceDir")
    if recorded and _has_project_files(recorded):
        return recorded

    return project_dir


def main() -> None:
    if "--bootstrap-only" in sys.argv[1:]:
        return

    # Precedence: OS/process env > workspace .env > config.json (IDs/URLs only)
    # > ~/.claude/.credentials.json (CLI install fallback).
    _strip_unresolved(os.environ)

    project_dir = _resolve_project_dir()
    _load_env_file(os.environ, project_dir)
    _inject_project_config(os.environ, project_dir)
    _inject_api_key_from_credentials(os.environ)

    if not os.environ.get("PLATFORM_API_KEY"):
        print(
            "auto-pilot: no PLATFORM_API_KEY configured. Set PLATFORM_API_KEY in "
            f"your OS environment or add it to {os.path.join(project_dir, '.env')}",
            file=sys.stderr,
        )

    sys.path.insert(0, PLUGIN_ROOT)
    os.chdir(PLUGIN_ROOT)
    from server.tools import mcp  # noqa: E402

    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
