---
name: push-to-autopilot
description: Phase 3 — read enriched manual test case markdown files and push them to the autopilot backend in batches using create_test_cases. Use when the user wants to save, upload, or push their test cases to the platform after Phase 1 and Phase 2 are complete.
---

# Push Test Cases to Autopilot Backend — Phase 3

Read the enriched markdown from Phase 1+2 and persist utils and test cases to
the autopilot backend.

> **IMPORTANT — File location:** All markdown files (`test-cases-*.md`, `test-coverage.md`) live in the **current working directory** — the folder the user launched Claude from. Always read from and write to the cwd, never the plugin directory.

## Step 0 — Save unpersisted utils

Before pushing any test cases, scan each markdown file for `UTIL-NNN` sections
where `Util UUID: *(populated after...)*` — these utils were identified but not
yet saved to the platform.

If any unpersisted utils are found:
1. Call `save_claude_utils` for those utils (grouped by module)
2. Fill in the **Util UUID** field in each UTIL-NNN section
3. Replace all `execute util "util_name"` placeholders in test case steps with
   the real UUIDs returned by the backend

If all util UUIDs are already filled in, skip this step.

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
    {"field": "valid_email", "value": "user@example.com", "type": "text"},
    {"field": "valid_password", "value": "Test@123!", "type": "text"}
  ]
}
```

**Test cases that call utils** use `execute util "<uuid>"` in steps — always UUID, never util name. Test data overrides for util fields use the format `<field>_i<N>_<util-uuid>` where `N` is the invocation number. Override is optional; omit it if the util's default data is sufficient.

```json
{
  "name": "TC-005: Create post as logged-in admin then regular user",
  "description": "Verify post creation works for both admin and regular user roles",
  "type": "Functional +Ve",
  "priority": "Major",
  "test_phase": "QA",
  "steps": [
    "execute util \"3fa85f64-5717-4562-b3fc-2c963f66afa6\"",
    "navigate to \"/posts/create\"",
    "enter \"<post_title>\" in \"el:title_input\"",
    "click on \"el:submit_button\"",
    "check element \"el:success_banner\" is visible in the page",
    "execute util \"3fa85f64-5717-4562-b3fc-2c963f66afa6\""
  ],
  "elements": [
    {"name": "title_input", "css_selector": "input#post-title"},
    {"name": "submit_button", "css_selector": "button[type='submit']"},
    {"name": "success_banner", "css_selector": ".alert-success"}
  ],
  "test_data": [
    {"field": "post_title", "value": "My First Post", "type": "text"},
    {"field": "email_i1_3fa85f64-5717-4562-b3fc-2c963f66afa6", "value": "admin@example.com", "type": "text"},
    {"field": "password_i1_3fa85f64-5717-4562-b3fc-2c963f66afa6", "value": "AdminPass@1", "type": "text"},
    {"field": "email_i2_3fa85f64-5717-4562-b3fc-2c963f66afa6", "value": "user@example.com", "type": "text"}
  ]
}
```

**Important — test_data values must be real example values, never placeholders.**
When you see `<placeholder>` in a step (e.g., `enter "<valid_email>" in "el:email_textbox"`),
extract the field name (strip the `<>`) and generate a realistic example value for `value`.
Never use the placeholder string itself (e.g., `"<valid_email>"`) as the value.

| Placeholder | Example real value |
|------------|-------------------|
| `<email>` / `<valid_email>` | `"user@example.com"` |
| `<password>` / `<valid_password>` | `"Test@123!"` |
| `<username>` | `"testuser"` |
| `<phone>` | `"+1-555-0100"` |
| `<name>` / `<full_name>` | `"John Doe"` |
| `<invalid_email>` | `"not-an-email"` |
| `<invalid_password>` | `"short"` |
| `<otp>` / `<code>` | `"123456"` |

For domain-specific placeholders not in this table, infer a realistic value from the field name and context.

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
