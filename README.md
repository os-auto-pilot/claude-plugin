# Oniesoft Test Platform — Claude Code plugin

Drive the Oniesoft test platform from Claude Code (or any MCP-capable AI). Claude
becomes the orchestration brain; the plugin's bundled MCP server exposes the
platform's capabilities as tools:

- **Generate** web, API, and **native mobile** test cases from plain language.
- **Run** test cases / test runs — including native Android/iOS via Appium — with
  **self-healing semantic locators** (things browser-only tools can't do).
- **Analyze** failures: top reasons, run comparison, stack-trace explanations.

## What's inside

| Component | Purpose |
|---|---|
| `server/` | Bundled MCP server — a thin HTTP client over the platform (`:8000`) and execution engine (`:3232`). No business logic; the backends do the work. |
| `skills/` | Workflow playbooks: `create-tests`, `run-tests`, `mobile-testing`, `analyze-run`. Claude invokes them automatically or via `/`. |
| `agents/` | Subagents: `test-author`, `test-runner`, `failure-analyst`. |
| `.mcp.json` | Registers the MCP server; injects config + API key as env. |
| `hooks/hooks.json` | SessionStart venv bootstrap (installs `mcp`+`httpx` into `${CLAUDE_PLUGIN_DATA}`). |

## Requirements

- A `python` (3.10+) on PATH — the launcher creates its own venv, so no global
  installs are needed.
- Running Oniesoft backends reachable from your machine:
  - platform API (`agentic_ai_be`), default `http://localhost:8000`
  - execution API (`python_tool`), default `http://localhost:3232`
- A personal **API key** (generate one in the platform: Users → API Keys).

## Install

**For development (no marketplace):**
```bash
claude --plugin-dir /path/to/oniesoft-test-platform
```

**Via marketplace:**
```
/plugin marketplace add <this-repo-url>
/plugin install oniesoft-test-platform@oniesoft
```

On enable you'll be prompted for the platform URL, execution URL, your **API
key** (stored in the OS keychain), and optional default project/user ids.

## Auth

The plugin sends your API key as the `x-api-key` header on every call. It is the
single credential — no JWT is held in the plugin. Keys are scoped
(`generate` / `run` / `read`); a `401` means the key is missing/expired, a `403`
means it lacks the scope for that action.

## Tools

**Test Case Authoring**
`create_test_cases`, `analyze_test_steps`, `save_claude_test_cases`, `create_test_case_from_defect`

**Test Execution**
`run_tests`, `run_test_case`, `get_run_status`, `stop_tests`, `wait_for_test_execution_completion`

**Test Run Management**
`create_test_run`, `clone_test_run`, `schedule_test_run`, `get_test_runs_with_filters`,
`add_or_remove_test_cases_from_test_run`, `get_test_cases_with_filters_in_a_project`,
`get_test_cases_uuid_by_unique_keys`

**Failure Analysis**
`fetch_test_run_results`, `fetch_test_run_failure_details`, `fetch_element_details`, `fetch_util_details`

**Projects & Modules**
`get_project_id_by_name`, `get_projects_assigned_to_user`, `create_module`,
`get_module_id_by_name_or_unique_key`, `create_feature`, `get_feature_id_by_name_or_unique_key`

**Elements**
`create_element`, `update_element`, `get_element_id_by_name_or_unique_key`

**Users & Environments**
`get_user_details_by_id_or_email_or_unique_key`, `get_environments_assigned_to_user`,
`get_web_environment_details_by_name_or_unique_key`

## Develop & test

```bash
python -m venv .devvenv && ./.devvenv/Scripts/python -m pip install -r server/requirements.txt
python -c "import asyncio; from server.tools import mcp; print(asyncio.run(mcp.list_tools()))"
claude plugin validate . --strict
```
