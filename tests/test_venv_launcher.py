"""Tests for server/venv_launcher.py (persistent venv) and the Desktop registration entry."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import register_desktop_mcp  # noqa: E402
from server import venv_launcher as vl  # noqa: E402


def _fake_build(venv_dir: str, key: str) -> None:
    """Stand-in for _build: lay out just enough of a venv for is_ready()."""
    python = vl.venv_python(venv_dir)
    os.makedirs(os.path.dirname(python), exist_ok=True)
    Path(python).write_text("", encoding="utf-8")
    Path(venv_dir, vl.MARKER_NAME).write_text(json.dumps({"key": key}), encoding="utf-8")


class VenvKeyTests(unittest.TestCase):
    def test_key_is_stable(self) -> None:
        self.assertEqual(vl.venv_key(b"mcp\n", (3, 12)), vl.venv_key(b"mcp\n", (3, 12)))

    def test_key_changes_with_requirements(self) -> None:
        self.assertNotEqual(vl.venv_key(b"mcp\n", (3, 12)), vl.venv_key(b"mcp\nhttpx\n", (3, 12)))

    def test_key_changes_with_python_minor_version(self) -> None:
        self.assertNotEqual(vl.venv_key(b"mcp\n", (3, 12)), vl.venv_key(b"mcp\n", (3, 13)))


class IsReadyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.venv = os.path.join(self.tmp.name, "venv")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_not_ready_without_marker(self) -> None:
        os.makedirs(self.venv)
        self.assertFalse(vl.is_ready(self.venv, "k"))

    def test_ready_after_build(self) -> None:
        _fake_build(self.venv, "k")
        self.assertTrue(vl.is_ready(self.venv, "k"))

    def test_not_ready_for_other_key(self) -> None:
        _fake_build(self.venv, "k")
        self.assertFalse(vl.is_ready(self.venv, "other"))

    def test_not_ready_when_base_python_is_gone(self) -> None:
        _fake_build(self.venv, "k")
        Path(self.venv, "pyvenv.cfg").write_text(
            f"home = {os.path.join(self.tmp.name, 'deleted-python')}\n", encoding="utf-8"
        )
        self.assertFalse(vl.is_ready(self.venv, "k"))


class EnsureVenvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        req = Path(self.tmp.name, "requirements.txt")
        req.write_text("mcp\n", encoding="utf-8")
        venvs = os.path.join(self.tmp.name, "venvs")
        for patch in (
            mock.patch.object(vl, "REQUIREMENTS", str(req)),
            mock.patch.object(vl, "VENVS_DIR", venvs),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_builds_once_then_reuses(self) -> None:
        with mock.patch.object(vl, "_build", side_effect=_fake_build) as build:
            first = vl.ensure_venv()
            second = vl.ensure_venv()
        self.assertEqual(first, second)
        self.assertEqual(build.call_count, 1)

    def test_concurrent_starts_build_once(self) -> None:
        def slow_build(venv_dir: str, key: str) -> None:
            threading.Event().wait(0.3)
            _fake_build(venv_dir, key)

        results: list[str] = []
        with mock.patch.object(vl, "_build", side_effect=slow_build) as build:
            threads = [threading.Thread(target=lambda: results.append(vl.ensure_venv())) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(build.call_count, 1)
        self.assertEqual(len(set(results)), 1)

    def test_new_requirements_get_a_new_venv(self) -> None:
        with mock.patch.object(vl, "_build", side_effect=_fake_build):
            first = vl.ensure_venv()
            Path(vl.REQUIREMENTS).write_text("mcp\nhttpx\n", encoding="utf-8")
            second = vl.ensure_venv()
        self.assertNotEqual(first, second)
        self.assertTrue(os.path.exists(first))


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.venv = os.path.join(self.tmp.name, "venv")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_retries_a_failed_install_and_writes_marker_last(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd: list[str]) -> None:
            calls.append(cmd)
            if cmd[1] == "venv":
                _fake_build(self.venv, "unused")
                os.remove(os.path.join(self.venv, vl.MARKER_NAME))
            elif cmd[1:3] == ["pip", "install"] and len(calls) == 2:
                self.assertFalse(os.path.exists(os.path.join(self.venv, vl.MARKER_NAME)))
                raise vl.SetupError("locked")

        with mock.patch.object(vl, "_find_uv", return_value="uv"), mock.patch.object(
            vl, "_run", side_effect=fake_run
        ), mock.patch.object(vl.time, "sleep"):
            vl._build(self.venv, "k")

        self.assertEqual([c[1] for c in calls], ["venv", "pip", "pip"])
        self.assertTrue(vl.is_ready(self.venv, "k"))

    def test_gives_up_after_max_attempts(self) -> None:
        def fake_run(cmd: list[str]) -> None:
            if cmd[1] == "pip":
                raise vl.SetupError("locked")

        with mock.patch.object(vl, "_find_uv", return_value="uv"), mock.patch.object(
            vl, "_run", side_effect=fake_run
        ), mock.patch.object(vl.time, "sleep"):
            with self.assertRaises(vl.SetupError):
                vl._build(self.venv, "k")
        self.assertFalse(vl.is_ready(self.venv, "k"))

    def test_run_never_writes_to_stdout(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            vl._run([sys.executable, "-c", "print('from child')"])
        self.assertEqual(out.getvalue(), "")
        self.assertIn("from child", err.getvalue())


class FileLockTests(unittest.TestCase):
    def test_second_holder_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.lock")
            with vl.file_lock(path):
                with self.assertRaises(vl.SetupError):
                    with vl.file_lock(path, timeout=0.6):
                        pass
            with vl.file_lock(path, timeout=0.6):
                pass


class MainTests(unittest.TestCase):
    def test_bootstrap_only_builds_and_exits(self) -> None:
        with mock.patch.object(vl, "ensure_venv", return_value="/venv/python") as ensure, mock.patch.object(
            vl.os, "execv"
        ) as execv:
            self.assertEqual(vl.main(["--bootstrap-only"]), 0)
        ensure.assert_called_once()
        execv.assert_not_called()

    def test_setup_failure_returns_nonzero(self) -> None:
        with mock.patch.object(vl, "ensure_venv", side_effect=vl.SetupError("boom")), contextlib.redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(vl.main([]), 1)

    @unittest.skipIf(os.name == "nt", "POSIX hands over with execv")
    def test_runs_launch_py_with_venv_python(self) -> None:
        with mock.patch.object(vl, "ensure_venv", return_value="/venv/python"), mock.patch.object(
            vl.os, "execv"
        ) as execv:
            vl.main([])
        execv.assert_called_once_with("/venv/python", ["/venv/python", vl.LAUNCH])


class DesktopEntryTests(unittest.TestCase):
    def test_entry_uses_launcher_and_shares_data_dir(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/data/auto-pilot"}):
            entry = register_desktop_mcp._server_entry(Path("/plugin"))
        self.assertEqual(entry["command"], "uv")
        self.assertIn("--no-project", entry["args"])
        self.assertTrue(entry["args"][-1].endswith(os.path.join("server", "venv_launcher.py")))
        self.assertNotIn("--with-requirements", entry["args"])
        self.assertEqual(entry["env"], {"CLAUDE_PLUGIN_DATA": "/data/auto-pilot"})

    def test_entry_without_data_dir_has_no_env(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
        with mock.patch.dict(os.environ, env, clear=True):
            entry = register_desktop_mcp._server_entry(Path("/plugin"))
        self.assertNotIn("env", entry)


if __name__ == "__main__":
    unittest.main()
