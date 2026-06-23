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


def main() -> None:
    bootstrap_only = "--bootstrap-only" in sys.argv[1:]
    py = ensure_venv()
    if bootstrap_only:
        return
    # Run the venv python as a child process.  We keep this launcher alive as a/exit
    # thin wrapper so that the MCP stdio pipe (which Claude Code opened to THIS
    # process) stays connected.  os.execve doesn't replace the process on
    # Windows — it spawns a child and exits, breaking the pipe.
    os.chdir(PLUGIN_ROOT)
    env = dict(os.environ)
    env["PYTHONPATH"] = PLUGIN_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([py, "-m", "server"], env=env, cwd=PLUGIN_ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
