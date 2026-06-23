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

`create_test_cases`, `analyze_test_steps`, `create_test_case_from_defect`,
`run_tests`, `get_run_status`, `stop_tests`, `analyze_test_run`,
`compare_test_runs`, `analyze_stack_trace`.

## Develop & test

```bash
python -m venv .devvenv && ./.devvenv/Scripts/python -m pip install -r server/requirements.txt
python -c "import asyncio; from server.tools import mcp; print(asyncio.run(mcp.list_tools()))"
claude plugin validate . --strict
```
