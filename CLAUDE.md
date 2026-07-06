# Oniesoft Auto-Pilot Claude Plugin

## Project Overview

This is a Claude Code plugin (MCP server) that integrates Claude with the Oniesoft test automation platform. It lets Claude author, push, run, and analyze test cases via MCP tools. The plugin has three layers:

- **`server/`** — FastMCP server exposing ~40 typed REST wrapper tools
- **`skills/`** — Skill playbooks (SKILL.md files) that guide Claude through multi-step workflows
- **`agents/`** — Specialist subagents delegated to for heavy lifting (failure analysis, element discovery, etc.)

## Project Connection Details

Company ID, user ID, project ID, and the three API URLs are per-project settings, stored in a `.config.json` file in the project folder (the directory you're working in — read it directly, the same way you read any other file in the repo).

**At the start of each session, read `.configs.json` from the project root and keep `companyId`/`projectId`/`userId` in mind for the rest of the conversation.** Pass them explicitly as `projectId` / `companyId` / `userId` (or `registerId` where a tool asks for the user's ID) on every tool call that accepts them — do not assume they are auto-injected. (`server/launch.py` also tries to inject them as environment variables at server startup as a bonus fallback, but this depends on the MCP host launching the server with the project directory as its working directory, which is not reliable — don't depend on it.)

The **API key** is the only credential that stays in the global plugin config (set once in Claude Code settings), sourced from `~/.claude/.credentials.json` and injected as `PLATFORM_API_KEY`. This one *is* reliably injected — no need to read or pass it.

If `.config.json` is missing a value you need, or a tool call fails with "No project_id given and no default configured" (or similar for company/user ID), ask the user for the missing value directly — never search `.credentials.json`, `settings.json`, or other config files to hunt for identifiers like emails or registerIds. Those files hold secrets and are out of scope for resolving a missing project/company/user ID.

**Project `.config.json` format**:
```json
{
  "companyId": "43e4f7c3-1a17-4627-8d95-49fd59076851",
  "projectId": "248af507-c75c-4590-95b8-4145891df8d0",
  "userId": "15eb541f-2dbe-403f-8191-9e1ad15fc0ef",
  "platformApiUrl": "http://localhost:8000",
  "executionApiUrl": "http://localhost:3232",
  "backendUrl": "http://localhost:8088"
}
```

## Tool Scope Rules

`get_autopilot_steps` — **only call this tool from within the `/analyze-requirements` skill**, during Step 2c before writing any autopilot steps. Never call it in any other skill, agent, or inline conversation.

## Agent Delegation Rules

When the user asks to analyze an Oniesoft test run (why it failed, compare runs, interpret a stack trace), always delegate to the `auto-pilot:failure-analyst` subagent via the Agent tool instead of calling MCP tools inline in the main conversation.

## Three-Phase Test Case Workflow

The core workflow for generating test cases is:

| Phase | Skill | What happens |
|---|---|---|
| 1 | `/analyze-requirements` | Analyze requirement docs / Swagger / codebase → generate markdown test cases + utils |
| 2 | `element-discoverer` agent | Enrich markdown with real element locators (Playwright or codebase grep) |
| 3 | `/push-to-autopilot` | Read enriched markdown → call `save_claude_utils` then `save_claude_test_cases` |

## Utils (Reusable Test Components)

Utils are reusable test flows (login, logout, create user, etc.) that can be called from multiple test cases. Key rules:

- A util is identified when a setup/teardown flow appears in 2+ test cases
- Utils are always referenced in test case steps by **UUID**, never by name: `execute util "3fa85f64-..."`
- Utils are created via the `save_claude_utils` MCP tool **before** `save_claude_test_cases`
- Utils have their own test data. A test case can optionally override util test data using: `<field>_i<N>_<util-uuid>` where N = invocation number (1 = first call, 2 = second call). Override is not mandatory.
- Before creating new utils, always call `fetch_util_details` to check if an existing util can be reused

### Test Data Override Example

Login util (id: `3fa85f64-5717-4562-b3fc-2c963f66afa6`) has fields `email` and `password`.
A test case calling it twice with different credentials:

```
Step 1: execute util "3fa85f64-5717-4562-b3fc-2c963f66afa6"   ← first call
Step 2: [do something]
Step 3: execute util "3fa85f64-5717-4562-b3fc-2c963f66afa6"   ← second call
```

Test data in the test case:
```
email_i1_3fa85f64-5717-4562-b3fc-2c963f66afa6    = admin@example.com
email_i2_3fa85f64-5717-4562-b3fc-2c963f66afa6    = user@example.com
password_i1_3fa85f64-5717-4562-b3fc-2c963f66afa6 = AdminPass@1
```

## Key Files

| File | Purpose |
|---|---|
| `server/tools.py` | All MCP tool definitions (~40 tools) |
| `server/request_response_model.py` | All Pydantic request/response models |
| `server/client.py` | Thin HTTP client (no business logic) |
| `skills/analyze-requirements/SKILL.md` | Phase 1 skill — requirement analysis + util/test case generation |
| `skills/push-to-autopilot/SKILL.md` | Phase 3 skill — push markdown to backend |
| `skills/run-tests/SKILL.md` | Run test cases or test runs |
| `skills/analyze-run/SKILL.md` | Failure analysis workflow |
| `agents/element-discoverer.md` | Phase 2 — enrich markdown with real locators |
| `agents/failure-analyst.md` | Deep failure triage (delegated, not inline) |
| `docs/backend-utils-create-from-claude.md` | Backend implementation spec for the util creation endpoint |

## MCP Tool Reference (most-used)

| Tool | What it does |
|---|---|
| `save_claude_utils` | Batch-create utils identified by Claude; returns UUIDs — call before `save_claude_test_cases` |
| `save_claude_test_cases` | Batch-create test cases authored by Claude; no LLM re-analysis |
| `fetch_util_details` | Search/filter existing utils by name, module, feature, testMode |
| `create_util` | Create a single util directly via backend (use `save_claude_utils` for Claude-authored batches) |
| `fetch_test_run_results` | Get all results for a completed run |
| `fetch_test_run_failure_details` | Get stack traces for failed cases |
| `get_feature_id_by_name_or_unique_key` | Resolve feature UUID — needed before pushing test cases or utils |

## Pending Backend Work

`POST /api/utils/create-from-claude` needs to be implemented on the Platform API (`agentic_ai_be`). The full spec is in `docs/backend-utils-create-from-claude.md`. Until this endpoint exists, `save_claude_utils` will return a 404/500 — the rest of the plugin is complete.
