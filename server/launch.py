"""Launcher for the Oniesoft MCP server.

Claude Code runs this via ``uv run --with-requirements server/requirements.txt``,
which resolves/installs a compatible Python and dependencies before handing off
here — cross-platform, with no bespoke venv-bootstrap code needed in this file.

This script only injects environment (API key, per-project config) that Claude
Code's own ${user_config.*} substitution can't reliably provide, then runs the
server in-process.

Run with ``--bootstrap-only`` (used by the SessionStart hook) to let `uv run`
finish syncing dependencies and exit immediately, so the first tool call isn't
delayed by the install.
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


def _inject_api_key(env: MutableMapping[str, str]) -> None:
    """Read the API key secret from ~/.claude/.credentials.json and inject it.

    Claude Code's ${user_config.*} substitution in config.json env blocks is not
    reliable: some spawned instances of this server receive a literal
    placeholder string (e.g. "your-api-key-here") instead of the real secret or
    an empty value. A placeholder is truthy, so a "fill only if unset" check
    would leave it in place. ~/.claude/.credentials.json is the authoritative
    source, so it always overrides whatever Claude Code already put in env.

    The API key is the only credential that stays in the global plugin config —
    everything else (company/user/project ID, API URLs) is per-project and comes
    from the project's own config.json (see _inject_project_config).
    """
    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")

    # Determine the plugin key ("auto-pilot@<server-name>").
    # Try both the current server name and the legacy "oniesoft" name so existing
    # settings.json entries are not silently dropped after a server rename.
    plugin_name = "auto-pilot"
    server_name = "auto-pilot"
    try:
        config_json_path = os.path.join(PLUGIN_ROOT, "config.json")
        with open(config_json_path, encoding="utf-8") as fh:
            config_data = json.load(fh)
        server_name = next(iter(config_data.get("mcpServers", {})), server_name)
    except Exception:
        pass

    candidate_keys = [f"{plugin_name}@{server_name}"]
    if server_name != "oniesoft":
        candidate_keys.append(f"{plugin_name}@oniesoft")  # legacy fallback

    creds_path = os.path.join(claude_dir, ".credentials.json")
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


def _inject_project_config(env: MutableMapping[str, str], project_dir: str) -> None:
    """Read the project's config.json (in the user's working directory — not
    the plugin directory) and inject company/user/project ID and API URLs.

    These values are per-project, not global plugin settings, so they live in a
    config.json that ships with the project folder itself rather than in
    ~/.claude/settings.json.
    """
    field_env_map = {
        "companyId": "PLATFORM_COMPANY_ID",
        "userId": "PLATFORM_USER_ID",
        "projectId": "PLATFORM_PROJECT_ID",
        "platformApiUrl": "PLATFORM_API_URL",
        "backendUrl": "BACKEND_URL",
    }

    project_mcp_json = os.path.join(project_dir, "config.json")
    try:
        with open(project_mcp_json, encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception:
        return

    for field, env_var in field_env_map.items():
        val = config.get(field)
        if val and not env.get(env_var):
            env[env_var] = str(val)

    # Persist a fixed-location snapshot of the per-project IDs so server
    # instances spawned WITHOUT project context (e.g. Claude Desktop's
    # app-startup MCP server, launched from C:\Windows\system32 before any
    # project is open) can still resolve them at request time. DATA_DIR is the
    # same fixed path for every process of this plugin, so this healthy launch's
    # snapshot is readable by a context-less one. See client.default_project_id.
    # Only write when we actually have a project id, so a context-less launch
    # never clobbers a good snapshot.
    snapshot = {
        key: config[key]
        for key in ("projectId", "userId", "companyId")
        if config.get(key)
    }
    if snapshot.get("projectId"):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(
                os.path.join(DATA_DIR, "active_project.json"), "w", encoding="utf-8"
            ) as fh:
                json.dump(snapshot, fh)
        except Exception:
            pass


def main() -> None:
    bootstrap_only = "--bootstrap-only" in sys.argv[1:]
    if bootstrap_only:
        # `uv run` has already synced the environment by the time this code
        # runs; nothing further to do.
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    _inject_project_config(os.environ, project_dir)
    _inject_api_key(os.environ)

    sys.path.insert(0, PLUGIN_ROOT)
    os.chdir(PLUGIN_ROOT)
    from server.tools import mcp  # noqa: E402

    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
