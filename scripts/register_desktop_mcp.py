"""Register this plugin's MCP server in Claude Desktop's own config.

Claude Desktop (the standalone app) does not read Claude Code's plugin-declared
.mcp.json at all — it has its own separate mcpServers list in
claude_desktop_config.json. A plugin installed via the Claude Code marketplace
therefore never reaches Claude Desktop; this script bridges that gap by adding
(or updating) this plugin's entry in Desktop's own config file.

Only the "mcpServers.auto-pilot" key is touched. Every other key in the file —
including unrelated app preferences — is preserved exactly. A backup is
written before any change that actually modifies the file.

Run on every SessionStart (see hooks/hooks.json) so it self-heals if the
plugin moves to a new install path across an update — it's a no-op write if
the entry already matches.

Usage: uv run scripts/register_desktop_mcp.py [--remove]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

SERVER_NAME = "auto-pilot"


def _config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("%APPDATA% is not set; cannot locate claude_desktop_config.json")
        return Path(appdata) / "Claude/claude_desktop_config.json"
    return Path.home() / ".config/claude-desktop/claude_desktop_config.json"


def _server_entry(plugin_root: Path) -> dict:
    requirements = str(plugin_root / "server" / "requirements.txt")
    launch = str(plugin_root / "server" / "launch.py")
    return {
        "command": "uv",
        "args": [
            "run",
            "--with-requirements", requirements,
            "--python", ">=3.10",
            launch,
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remove", action="store_true", help="Remove this plugin's entry instead of adding it."
    )
    args = parser.parse_args()

    plugin_root = Path(__file__).resolve().parent.parent
    config_path = _config_path()

    if config_path.exists():
        with open(config_path, encoding="utf-8") as fh:
            config = json.load(fh)
    else:
        if args.remove:
            print(f"{config_path} does not exist; nothing to remove.")
            return 0
        config = {}
        config_path.parent.mkdir(parents=True, exist_ok=True)

    servers = config.setdefault("mcpServers", {})

    if args.remove:
        if SERVER_NAME in servers:
            del servers[SERVER_NAME]
            action = "removed"
        else:
            print(f"'{SERVER_NAME}' is not registered in {config_path}; nothing to do.")
            return 0
    else:
        desired = _server_entry(plugin_root)
        if servers.get(SERVER_NAME) == desired:
            return 0  # already up to date — silent no-op, run every session
        servers[SERVER_NAME] = desired
        action = "registered"

    if config_path.exists():
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        shutil.copy2(config_path, backup_path)
        print(f"Backed up existing config to {backup_path}")

    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")

    print(f"{action.capitalize()} '{SERVER_NAME}' in {config_path}")
    print("Restart Claude Desktop for this change to take effect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
