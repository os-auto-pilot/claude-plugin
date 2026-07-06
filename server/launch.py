"""Self-bootstrapping launcher for the Oniesoft MCP server.

Claude Code runs this with whatever ``python`` is on PATH. It:
  1. Ensures a dedicated venv exists under ${CLAUDE_PLUGIN_DATA} (persists across
     plugin updates) and installs server/requirements.txt into it the first time
     or whenever requirements change.
  2. Re-execs the venv's python on ``-m server`` (stdio MCP).

Run with ``--bootstrap-only`` (used by the SessionStart hook) to do step 1 and
exit, so the first tool call isn't delayed by the install.

Cross-platform: this script picks the right venv layout (Scripts/ vs bin/), so
the static .mcp.json doesn't have to.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(PLUGIN_ROOT, "server")
REQUIREMENTS = os.path.join(SERVER_DIR, "requirements.txt")

# ${CLAUDE_PLUGIN_DATA} is exported to plugin subprocesses; fall back to a local
# dir for `--plugin-dir` dev use where it may be unset.
DATA_DIR = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(PLUGIN_ROOT, ".data")
VENV_DIR = os.path.join(DATA_DIR, "venv")
STAMP = os.path.join(VENV_DIR, ".requirements.sha256")


def _venv_python() -> str:
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _requirements_hash() -> str:
    with open(REQUIREMENTS, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _stamp_matches(want: str) -> bool:
    try:
        with open(STAMP, "r", encoding="utf-8") as fh:
            return fh.read().strip() == want
    except OSError:
        return False


def ensure_venv() -> str:
    """Create/refresh the venv if missing or requirements changed. Returns the
    venv python path."""
    py = _venv_python()
    want = _requirements_hash()
    if os.path.exists(py) and _stamp_matches(want):
        return py

    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(py):
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
    try:
        subprocess.run(
            [py, "-m", "pip", "install", "-q", "-r", REQUIREMENTS], check=True
        )
    except subprocess.CalledProcessError:
        # Leave no stamp so the next launch retries the install.
        if os.path.exists(STAMP):
            os.remove(STAMP)
        raise
    with open(STAMP, "w", encoding="utf-8") as fh:
        fh.write(want)
    return py


def _inject_api_key(env: dict) -> None:
    """Read the API key secret from ~/.claude/.credentials.json and inject it.

    Claude Code's ${user_config.*} substitution in .config.json env blocks is not
    reliable: some spawned instances of this server receive a literal
    placeholder string (e.g. "your-api-key-here") instead of the real secret or
    an empty value. A placeholder is truthy, so a "fill only if unset" check
    would leave it in place. ~/.claude/.credentials.json is the authoritative
    source, so it always overrides whatever Claude Code already put in env.

    The API key is the only credential that stays in the global plugin config —
    everything else (company/user/project ID, API URLs) is per-project and comes
    from the project's own .config.json (see _inject_project_config).
    """
    import json

    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")

    # Determine the plugin key ("auto-pilot@<server-name>").
    # Try both the current server name and the legacy "oniesoft" name so existing
    # settings.json entries are not silently dropped after a server rename.
    plugin_name = "auto-pilot"
    server_name = "auto-pilot"
    try:
        config_json_path = os.path.join(PLUGIN_ROOT, ".config.json")
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


def _inject_project_config(env: dict, project_dir: str) -> None:
    """Read the project's .config.json (in the user's working directory — not
    the plugin directory) and inject company/user/project ID and API URLs.

    These values are per-project, not global plugin settings, so they live in a
    .config.json that ships with the project folder itself rather than in
    ~/.claude/settings.json.
    """
    import json

    field_env_map = {
        "companyId": "PLATFORM_COMPANY_ID",
        "userId": "PLATFORM_USER_ID",
        "projectId": "PLATFORM_PROJECT_ID",
        "platformApiUrl": "PLATFORM_API_URL",
        "executionApiUrl": "EXECUTION_API_URL",
        "backendUrl": "BACKEND_URL",
    }

    project_mcp_json = os.path.join(project_dir, ".config.json")
    try:
        with open(project_mcp_json, encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception:
        return

    for field, env_var in field_env_map.items():
        val = config.get(field)
        if val and not env.get(env_var):
            env[env_var] = str(val)


def main() -> None:
    bootstrap_only = "--bootstrap-only" in sys.argv[1:]
    py = ensure_venv()
    if bootstrap_only:
        return
    # Run the venv python as a child process.  We keep this launcher alive as a/exit
    # thin wrapper so that the MCP stdio pipe (which Claude Code opened to THIS
    # process) stays connected.  os.execve doesn't replace the process on
    # Windows — it spawns a child and exits, breaking the pipe.
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    os.chdir(PLUGIN_ROOT)
    env = dict(os.environ)
    env["PYTHONPATH"] = PLUGIN_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    _inject_project_config(env, project_dir)
    _inject_api_key(env)

    result = subprocess.run([py, "-m", "server"], env=env, cwd=PLUGIN_ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
