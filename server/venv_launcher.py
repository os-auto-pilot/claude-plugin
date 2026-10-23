"""Start the Oniesoft MCP server from a persistent, plugin-owned virtualenv.

Claude Code, Claude Desktop and the SessionStart hook all run this file with
``uv run --no-project --python ">=3.10" server/venv_launcher.py``. It is
stdlib-only, so that ``uv run`` call starts an interpreter without installing
anything. This file then:

1. Makes sure a venv with ``server/requirements.txt`` installed exists under
   ``${CLAUDE_PLUGIN_DATA}/venvs/<hash>/``. It is built once per requirements
   file + Python minor version, under a cross-process file lock, so concurrent
   starts (Cowork, Code sessions, the hook) wait for one build instead of racing.
2. Runs ``server/launch.py`` with that venv's Python.

Why not ``uv run --with-requirements`` on every start: it builds a throwaway
environment each time, and on Windows that repeatedly installs pywin32 (a
Windows-only ``mcp`` dependency). Parallel starts or antivirus scans then lock
uv's temp directory and the server never comes up.

Pass ``--bootstrap-only`` (the SessionStart hook does) to build the venv and exit.

Nothing here may write to stdout: it is the MCP JSON-RPC channel.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS = os.path.join(PLUGIN_ROOT, "server", "requirements.txt")
LAUNCH = os.path.join(PLUGIN_ROOT, "server", "launch.py")

# Same data dir as launch.py: ${CLAUDE_PLUGIN_DATA}, or a local dir for --plugin-dir dev use.
DATA_DIR = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(PLUGIN_ROOT, ".data")
VENVS_DIR = os.path.join(DATA_DIR, "venvs")

#: Bump to force every install to rebuild its venv (e.g. after a layout change).
LAYOUT_VERSION = "1"
MARKER_NAME = "auto-pilot-venv.json"
LOCK_TIMEOUT_S = 600
INSTALL_ATTEMPTS = 3
#: Venvs for older requirements are removed once unused for this long.
STALE_AFTER_S = 14 * 24 * 3600


class SetupError(RuntimeError):
    pass


def _log(msg: str) -> None:
    print(f"auto-pilot: {msg}", file=sys.stderr, flush=True)


def venv_key(requirements: bytes, python_version: tuple[int, int]) -> str:
    """Identify a venv by what is installed in it, not by which interpreter launched us."""
    digest = hashlib.sha256()
    digest.update(f"layout={LAYOUT_VERSION}\n".encode())
    digest.update(f"python={python_version[0]}.{python_version[1]}\n".encode())
    digest.update(requirements)
    return digest.hexdigest()[:16]


def venv_python(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _base_python_home(venv_dir: str) -> str | None:
    """The ``home`` entry of pyvenv.cfg: the base interpreter's directory."""
    try:
        with open(os.path.join(venv_dir, "pyvenv.cfg"), encoding="utf-8") as fh:
            for line in fh:
                key, sep, val = line.partition("=")
                if sep and key.strip() == "home":
                    return val.strip()
    except OSError:
        pass
    return None


def is_ready(venv_dir: str, key: str) -> bool:
    """True when a previous build of this venv finished and its base Python still exists."""
    try:
        with open(os.path.join(venv_dir, MARKER_NAME), encoding="utf-8") as fh:
            marker = json.load(fh)
    except (OSError, ValueError):
        return False
    if marker.get("key") != key or not os.path.isfile(venv_python(venv_dir)):
        return False
    home = _base_python_home(venv_dir)
    return home is None or os.path.isdir(home)


@contextlib.contextmanager
def file_lock(path: str, timeout: float = LOCK_TIMEOUT_S) -> Iterator[None]:
    """Exclusive cross-process lock on ``path`` (fcntl on POSIX, msvcrt on Windows)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a+b")
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise SetupError(
                        f"timed out after {int(timeout)}s waiting for {path}; "
                        "another auto-pilot setup may be stuck"
                    ) from None
                time.sleep(0.5)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


def _find_uv() -> str:
    # `uv run` exports UV with its own path to the processes it starts.
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise SetupError("uv was not found on PATH; install it from https://docs.astral.sh/uv/")
    return uv


def _run(cmd: list[str]) -> None:
    # stdin is the MCP stream and stdout is the JSON-RPC channel: keep both away from uv.
    result = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    if result.stdout:
        sys.stderr.write(result.stdout)
        sys.stderr.flush()
    if result.returncode != 0:
        raise SetupError(f"command failed ({result.returncode}): {' '.join(cmd)}")


def _build(venv_dir: str, key: str) -> None:
    uv = _find_uv()
    _log(f"setting up Python environment in {venv_dir} (first run only, may take a minute)")

    # A leftover dir here is an interrupted build: nothing runs from a venv without a marker.
    shutil.rmtree(venv_dir, ignore_errors=True)
    venv_cmd = [uv, "venv", "--python", sys.executable]
    if os.path.exists(venv_dir):
        venv_cmd.append("--allow-existing")
    _run([*venv_cmd, venv_dir])

    python = venv_python(venv_dir)
    for attempt in range(1, INSTALL_ATTEMPTS + 1):
        try:
            _run([uv, "pip", "install", "--python", python, "-r", REQUIREMENTS])
            break
        except SetupError:
            # Usually a file briefly locked by antivirus on Windows; a retry tends to succeed.
            if attempt == INSTALL_ATTEMPTS:
                raise
            _log(f"dependency install failed (attempt {attempt}/{INSTALL_ATTEMPTS}); retrying")
            time.sleep(2 * attempt)

    # Written last: its presence is what marks the venv as complete.
    with open(os.path.join(venv_dir, MARKER_NAME), "w", encoding="utf-8") as fh:
        json.dump({"key": key, "basePython": sys.executable}, fh)


def _touch(path: str) -> None:
    with contextlib.suppress(OSError):
        os.utime(path)


def _remove_stale_venvs(keep: str) -> None:
    """Delete venvs for old requirements that no launch has used recently."""
    try:
        entries = os.listdir(VENVS_DIR)
    except OSError:
        return
    now = time.time()
    for name in entries:
        path = os.path.join(VENVS_DIR, name)
        if name == keep or not os.path.isdir(path):
            continue
        try:
            last_used = os.path.getmtime(os.path.join(path, MARKER_NAME))
        except OSError:
            last_used = os.path.getmtime(path)
        if now - last_used > STALE_AFTER_S:
            shutil.rmtree(path, ignore_errors=True)


def ensure_venv() -> str:
    """Return the Python of a ready venv, building it first if needed."""
    try:
        with open(REQUIREMENTS, "rb") as fh:
            requirements = fh.read()
    except OSError as exc:
        raise SetupError(f"cannot read {REQUIREMENTS}: {exc}") from None

    key = venv_key(requirements, sys.version_info[:2])
    venv_dir = os.path.join(VENVS_DIR, key)

    if not is_ready(venv_dir, key):
        with file_lock(os.path.join(VENVS_DIR, f"{key}.lock")):
            # Another process may have finished the build while we waited.
            if not is_ready(venv_dir, key):
                _build(venv_dir, key)
        _remove_stale_venvs(keep=key)

    _touch(os.path.join(venv_dir, MARKER_NAME))
    return venv_python(venv_dir)


def main(argv: list[str]) -> int:
    try:
        python = ensure_venv()
    except SetupError as exc:
        _log(f"could not prepare the MCP server environment: {exc}")
        return 1

    if "--bootstrap-only" in argv:
        return 0

    cmd = [python, LAUNCH, *argv]
    if os.name == "nt":
        # os.exec* on Windows spawns a new process and exits this one, which the
        # MCP host sees as the server dying. Stay alive as the parent instead.
        try:
            return subprocess.call(cmd)
        except KeyboardInterrupt:
            return 130
    os.execv(python, cmd)
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
