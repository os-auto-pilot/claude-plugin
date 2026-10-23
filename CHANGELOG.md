# Changelog

## 0.1.2

- **MCP server starts from a persistent venv** — fixes the server never starting
  on Windows with `Failed to install: pywin32-312-…whl … failed to remove
  directory …\uv\cache\builds-v0\.tmp…`. Previously every start ran
  `uv run --with-requirements`, which rebuilt a throwaway environment (including
  `pywin32`, a Windows-only `mcp` dependency) each time; parallel starts or
  antivirus scans locked uv's temp directory. The new stdlib-only
  `server/venv_launcher.py` builds one venv per requirements + Python version
  under `${CLAUDE_PLUGIN_DATA}/venvs/`, behind a cross-process file lock, retries
  a failed install, then runs `server/launch.py` with it. `.mcp.json`, the
  SessionStart hook and the Claude Desktop registration all use it, and the
  Desktop entry now passes `CLAUDE_PLUGIN_DATA` so both share one venv.
- `uv run` calls now pass `--no-project`, so a `pyproject.toml` in the user's
  workspace is never synced by the plugin.

## 0.1.1

- **API key from workspace `.env` or OS environment** — no longer depends on
  Claude's `userConfig` / plugin Configure UI (which Claude Desktop does not
  support today). `server/launch.py` reads `PLATFORM_API_KEY` from the process
  environment first, then the workspace `.env`, then `~/.claude/.credentials.json`
  as a CLI-install fallback. Removed `userConfig` from `.claude-plugin/plugin.json`
  and `${user_config.platform_api_key}` from `.mcp.json`.
- Added `.env.example`.

## 0.1.0

Initial release.

- Bundled MCP server (`server/`) with 9 tools over the platform API (`:8000`) and
  execution engine (`:3232`): `create_test_cases`, `analyze_test_steps`,
  `create_test_case_from_defect`, `run_tests`, `get_run_status`, `stop_tests`,
  `analyze_test_run`, `compare_test_runs`, `analyze_stack_trace`.
- Skills: `create-tests`, `run-tests`, `mobile-testing`, `analyze-run`.
- Subagents: `test-author`, `test-runner`, `failure-analyst`.
- Self-bootstrapping launcher (`server/launch.py`) + SessionStart hook: creates a
  venv under `${CLAUDE_PLUGIN_DATA}` and installs deps on first run / when
  requirements change.
- API-key auth via the `x-api-key` header, sourced from the sensitive
  `platform_api_key` user config.
