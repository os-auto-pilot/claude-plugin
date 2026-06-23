---
name: push-to-autopilot
description: Phase 3 — read enriched manual test case markdown files and push them to the autopilot backend in batches using create_test_cases. Use when the user wants to save, upload, or push their test cases to the platform after Phase 1 and Phase 2 are complete.
---

# Push Test Cases to Autopilot Backend — Phase 3

Read the enriched markdown from Phase 1+2 and persist each test case to the
autopilot backend using the `create_test_cases` MCP tool.

## Step 1 — Identify files to push

If the user did not specify which files:
- Read `test-coverage.md` to find all files with status `Done`
- List them and ask: *"Which of these files shall I push?"*

## Step 2 — Collect required metadata

You need for every push call:
- `module` — from the test case **Module** field
- `feature` — from the test case **Feature** field
- `test_mode` — ask the user once per file: `web`, `api`, or `mobile`
- `project_id` — use the plugin default; ask only if not configured
- `user_id` — use the plugin default; ask only if not configured

## Step 3 — Push using save_claude_test_cases

Call `save_claude_test_cases` once per module+feature group. This endpoint does
**no LLM re-analysis** — it uses exactly what Claude wrote.

Build the `test_cases` array from the markdown file. Each item:
```json
{
  "name": "TC-001: Login with valid credentials",
  "description": "Verify user can log in with valid email and password",
  "type": "Functional +Ve",
  "priority": "Major",
  "test_phase": "QA",
  "steps": [
    "navigate to \"/login\"",
    "enter \"test@example.com\" in \"el:email_textbox\"",
    "enter \"<password>\" in \"el:password_textbox\"",
    "click on \"el:login_button\"",
    "check element \"el:dashboard_header\" is visible in the page"
  ],
  "elements": [
    {"name": "email_textbox", "css_selector": "input[name='email']"},
    {"name": "password_textbox", "css_selector": "input[type='password']"},
    {"name": "login_button", "css_selector": "button.btn-login"},
    {"name": "dashboard_header", "css_selector": "h1.dashboard-title"}
  ],
  "test_data": [
    {"field": "password", "value": "Test@123", "type": "text"}
  ]
}
```

Required fields besides `test_cases`:
- `module`, `feature` — from the test case file header
- `feature_id` — the UUID of the feature in the autopilot backend (ask the user if unknown)
- `test_mode` — `web`, `api`, or `mobile`
- `project_id` — from plugin default or ask the user

Record the returned test case IDs.

## Step 4 — Update the tracker and report

After all batches for a file are pushed:
- Update `test-coverage.md`: change status from `Done` to `Pushed`, add the
  returned IDs in a new `Backend IDs` column.
- Report total pushed, any failures (surface the verbatim error), and the IDs.

## Error handling

- **401** — API key missing or expired. Ask the user to check `platform_api_key`
  in plugin settings.
- **403** — API key lacks `generate` scope. User needs to regenerate with the
  correct scopes.
- **4xx/5xx** — surface the error verbatim and skip that batch; continue with
  the rest.

## Note on step format

The `save_claude_test_cases` endpoint runs zero LLM — it only applies a regex
normaliser to fix minor spacing issues (e.g. `navigateto` → `navigate to`).
Steps must already be in autopilot format as described in the
`analyze-requirements` skill's step format guide. If steps are in plain English
rather than autopilot format, use `create_test_cases` instead (which does run LLM
analysis) and accept that element locators will not be preserved.
