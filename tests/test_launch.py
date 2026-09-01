"""Tests for server/launch.py credential and project-dir resolution."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import launch  # noqa: E402


class LaunchCredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_environ = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._original_environ)

    def test_strip_unresolved_removes_user_config_placeholder(self) -> None:
        env: dict[str, str] = {"PLATFORM_API_KEY": "${user_config.platform_api_key}"}
        launch._strip_unresolved(env)
        self.assertNotIn("PLATFORM_API_KEY", env)

    def test_load_env_file_fills_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("PLATFORM_API_KEY=from-dotenv\n", encoding="utf-8")
            env: dict[str, str] = {}
            launch._load_env_file(env, tmp)
            self.assertEqual(env["PLATFORM_API_KEY"], "from-dotenv")

    def test_load_env_file_does_not_override_os_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("PLATFORM_API_KEY=from-dotenv\n", encoding="utf-8")
            env: dict[str, str] = {"PLATFORM_API_KEY": "from-os"}
            launch._load_env_file(env, tmp)
            self.assertEqual(env["PLATFORM_API_KEY"], "from-os")

    def test_inject_project_config_reads_config_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "companyId": "c1",
                "projectId": "p1",
                "userId": "u1",
                "platformApiUrl": "http://api.test",
                "backendUrl": "http://backend.test",
            }
            (Path(tmp) / "config.json").write_text(json.dumps(config), encoding="utf-8")
            env: dict[str, str] = {}
            with mock.patch.object(launch, "DATA_DIR", Path(tmp) / ".data"):
                launch._inject_project_config(env, tmp)
            self.assertEqual(env["PLATFORM_PROJECT_ID"], "p1")
            self.assertEqual(env["PLATFORM_API_URL"], "http://api.test")

    def test_credentials_fallback_when_env_and_dotenv_missing(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            creds_dir = Path(home) / ".claude"
            creds_dir.mkdir()
            creds = {
                "pluginSecrets": {
                    "auto-pilot@auto-pilot": {"platform_api_key": "from-creds"}
                }
            }
            (creds_dir / ".credentials.json").write_text(json.dumps(creds), encoding="utf-8")
            env: dict[str, str] = {}
            with mock.patch.object(launch, "PLUGIN_ROOT", Path(home) / "plugin"):
                with mock.patch.object(launch.os.path, "expanduser", return_value=home):
                    launch._inject_api_key_from_credentials(env)
            self.assertEqual(env["PLATFORM_API_KEY"], "from-creds")


if __name__ == "__main__":
    unittest.main()
