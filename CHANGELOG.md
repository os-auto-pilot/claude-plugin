# Changelog

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
