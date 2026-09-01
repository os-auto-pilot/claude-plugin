# Oniesoft Auto-Pilot Claude Plugin

## Project Overview

This is a Claude Code plugin (MCP server) that integrates Claude with the Oniesoft test automation platform. It lets Claude author, push, run, and analyze test cases via MCP tools. The plugin has three layers:

- **`server/`** — FastMCP server exposing ~40 typed REST wrapper tools
- **`skills/`** — Skill playbooks (SKILL.md files) that guide Claude through multi-step workflows
- **`agents/`** — Specialist subagents delegated to for heavy lifting (failure analysis, element discovery, etc.)

## Project Connection Details

Company ID, user ID, project ID, and the three API URLs are per-project settings, stored in a `config.json` file in the project folder (the directory you're working in — read it directly, the same way you read any other file in the repo).

**At the start of each session, read `config.json` from the project root and keep `companyId`/`projectId`/`userId` in mind for the rest of the conversation.** Pass them explicitly as `projectId` / `companyId` / `userId` (or `registerId` where a tool asks for the user's ID) on every tool call that accepts them — do not assume they are auto-injected. (`server/launch.py` also tries to inject them as environment variables at server startup as a bonus fallback, but this depends on the MCP host launching the server with the project directory as its working directory, which is not reliable — don't depend on it.)

The **API key** is set in the workspace **`.env`** file (`PLATFORM_API_KEY=...`) or
the OS environment. Generate one in the platform under Users → API Keys. It is
injected automatically — never read or pass it in chat. Claude Desktop does not
collect plugin `userConfig` values today, so `.env` is the supported path for
desktop installs. CLI installs may still fall back to `~/.claude/.credentials.json`
if the key was provided via `claude plugin install --config platform_api_key=...`.

If `config.json` is missing a value you need, or a tool call fails with "No project_id given and no default configured" (or similar for company/user ID), ask the user for the missing value directly — never search `.credentials.json`, `settings.json`, or other config files to hunt for identifiers like emails or registerIds. Those files hold secrets and are out of scope for resolving a missing project/company/user ID.

**Project `config.json` format**:
```json
{
  "companyId": "43e4f7c3-1a17-4627-8d95-49fd59076851",
  "projectId": "248af507-c75c-4590-95b8-4145891df8d0",
  "userId": "15eb541f-2dbe-403f-8191-9e1ad15fc0ef",
  "platformApiUrl": "http://localhost:8000",
  "backendUrl": "http://localhost:8088"
}
```

## Author / created_by Fields

`save_claude_utils` (`userName`) and `save_claude_test_cases` (`created_by`)
require a **plain human display name**, e.g. `"Surya"` — never an email
address, never a UUID. Resolve it via `get_user_details_by_id_or_email_or_unique_key`
and use **`empName`** from the response. Passing an email (contains `@`) or a
UUID does not raise a validation error — the backend silently drops the entire
batch and returns a generic `{"detail": "No test cases were saved"}` with no
indication of which field caused it. Full detail and other related backend
quirks (bare-tag CSS selectors, a ~300-char `description` limit) are documented
in `skills/push-to-autopilot/SKILL.md` under "Known backend quirks".

`get_user_details_by_id_or_email_or_unique_key` requires a real `companyId` —
read it from `config.json` per the Project Connection Details section above.
Never pass a placeholder/zero-filled UUID for `companyId` (or any other
required ID) just to make a call succeed structurally — a wrong ID produces a
misleading "not found" error instead of the real problem (a missing config
value). Ask the user for it if it's genuinely unavailable.

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

## Performance Test Case Workflow

A separate, standalone workflow — not part of the three-phase pipeline above (no `el:` elements,
no Phase 2 discovery):

| Step | Skill/Tool | What happens |
|---|---|---|
| 1 (only if CSV-driven) | `/create-datafile` | Generate + validate a CSV, upload via `upload_datafile` → returns a file `id` |
| 2 | `/performance-testing` | Author load-test steps from a Swagger doc (single endpoint, or multi-endpoint flow with correlation) |
| 3 | `save_claude_test_cases` | Push with `test_mode="Performance"`, `file_ids` set when a CSV was created |

Claude authors all performance-test content itself — this workflow never calls the platform's
separate AI-driven performance-test-generation endpoint. `/create-datafile` is also usable
standalone, independent of performance test cases.

## Utils (Reusable Test Components)

Utils are reusable test flows (login, logout, create user, etc.) that can be called from multiple test cases. Key rules:

- A util is identified when a setup/teardown flow appears in 2+ test cases
- Utils are always referenced in test case steps by **UUID**, never by name: `execute util "3fa85f64-..."`
- Utils are created via the `save_claude_utils` MCP tool **before** `save_claude_test_cases`
- **A util can never call another util.** `execute util "<uuid>"` is only valid inside a test case's own steps — never inside a UTIL-NNN section's own Autopilot Steps. Nested/chained util calls are not supported by the autopilot backend. If a util's flow would otherwise need another util's steps, inline those steps directly in the util instead of referencing it.
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
| `skills/run-tests/SKILL.md` | Run test cases or test runs (incl. Performance load profile) |
| `skills/schedule-test-run/SKILL.md` | Schedule an existing test run for a future date/time + environment |
| `skills/analyze-run/SKILL.md` | Failure analysis workflow |
| `agents/element-discoverer.md` | Phase 2 — enrich markdown with real locators |
| `agents/failure-analyst.md` | Deep failure triage (delegated, not inline) |
| `docs/backend-utils-create-from-claude.md` | Backend implementation spec for the util creation endpoint |
| `skills/create-datafile/SKILL.md` | Generate + upload a CSV data file (standalone) |
| `skills/performance-testing/SKILL.md` | Author performance/load test cases, zero-LLM push |
| `docs/backend-performance-test-fileids.md` | Backend implementation spec for attaching CSV files to zero-LLM test cases |

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
| `upload_datafile` | Upload a CSV data file to `datafiles/v1/upload`; returns the file `id` used in a test case's `file_ids` |
| `run_test_case` | Start one test case; carries the load profile for Performance cases |
| `get_environments_assigned_to_user` | List a user's environments — the source for any environment prompt |
| `schedule_test_run` | Set an existing test run to execute later; `environment` is a **name**, not a UUID |

## Performance Run Profile

Virtual users, ramp pattern, and duration are **run-time config**, never authored into
steps (see `skills/performance-testing/SKILL.md`). Defaults live in the backend's
`LoadProfileValidator` and are applied there when a field is omitted — **100** VUs,
**linear**, **1m**. Send only what the user explicitly chose so those defaults stay the
single source of truth.

Field names on the wire must match the backend's `TestCaseRunDto` exactly —
`virtualUsers` (plural), `duration`, `rampPattern`. A misspelled field is dropped
silently by Jackson and the run falls back to defaults with no error, so a "why did it
run with 100 users?" bug looks like a backend problem when it's a typo.

Duration from this plugin is capped at **3 minutes**; longer runs belong on
https://www.osautopilot.com. `RunTestCaseInput` enforces the cap, but `run-tests` should
catch it first so the user gets an explanation instead of a validation error.

## Pending Backend Work

`POST /api/utils/create-from-claude` needs to be implemented on the Platform API (`agentic_ai_be`). The full spec is in `docs/backend-utils-create-from-claude.md`. Until this endpoint exists, `save_claude_utils` will return a 404/500 — the rest of the plugin is complete.

~~`ClaudeTestCaseInput.file_ids` backend gap~~ — **RESOLVED (2026-08-04).** The matching `file_ids` field was added to the Platform API's zero-LLM test-case model, and forwarded into the downstream `SingleTestCase.fileIds` — see `docs/backend-performance-test-fileids.md` for the applied change and live verification. The performance-testing workflow (upload, `test_mode="Performance"`, the full DSL, `file_ids` attachment) is now confirmed working end-to-end against a real dev instance.
