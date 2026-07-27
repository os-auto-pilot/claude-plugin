---
name: push-to-autopilot
description: Phase 3 — read enriched manual test case markdown files and push them to the autopilot backend in batches using create_test_cases. Use when the user wants to save, upload, or push their test cases to the platform after Phase 1 and Phase 2 are complete.
---

# Push Test Cases to Autopilot Backend — Phase 3

Read the enriched markdown from Phase 1+2 and persist utils and test cases to
the autopilot backend.

> **IMPORTANT — File location:** All markdown files (`test-cases-*.md`, `test-coverage.md`) live in the **current working directory** — the folder the user launched Claude from. Always read from and write to the cwd, never the plugin directory.

## Step -1 — Resolve the author's display name (do this once, first)

Both `save_claude_utils` (`userName` field) and `save_claude_test_cases`
(`created_by` field) require a **plain human display name** — e.g. `"Surya"` —
never an email address and never a UUID.

1. Call `get_user_details_by_id_or_email_or_unique_key` with whatever identifier
   you have (the session's user email is usually available in context) and the
   project's `companyId` (read from `config.json` per `CLAUDE.md` — do **not**
   invent or zero-fill a placeholder `companyId`; if `config.json` is missing
   or has no `companyId`, ask the user for it before calling this tool, exactly
   as `CLAUDE.md` already instructs for missing project/company/user IDs).
2. Take **`empName`** from the response — that is the field to use, not
   `email`, not `userId`, not `empId`.
3. Use that name verbatim as `userName` in every `save_claude_utils` call and
   `created_by` in every `save_claude_test_cases` call for the rest of this
   push. Resolve it once per session, not once per call.
4. If the lookup genuinely fails (user not found, no `companyId` available even
   after asking), ask the user directly: *"What name should I record as the
   author of these test cases/utils?"* — do not fall back to their email or a
   UUID, and do not fabricate a name.

**Why this matters:** an email address (contains `@`) or a UUID passed as
`created_by`/`userName` does not raise a validation error — the backend
silently drops every test case in the batch and returns
`{"detail": "No test cases were saved"}` with no indication of which field
caused it. This is easy to lose an hour to; resolving the name up front avoids
it entirely.

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
- `created_by` (test cases) / `userName` (utils) — the `empName` resolved in
  Step -1. Never an email, never a UUID.

## Step 3 — Push using save_claude_test_cases

Call `save_claude_test_cases` once per module+feature group. This endpoint does
**no LLM re-analysis** — it uses exactly what Claude wrote, in exactly the order
the `steps` array is sent. The backend does not reorder, sort, or otherwise
rearrange steps — whatever order you send is the order the run executes in.

**Steps must be copied into the `steps` array in the exact line order they
appear in the markdown's `### Autopilot Steps` fenced block — never reordered,
regrouped, or moved for any reason.** This applies especially to `execute
util` calls: a cleanup util at the *end* of the block (e.g. deleting a record
created earlier in the same test case) must stay last in the `steps` array,
even though it might be tempting to move it next to other `execute util`
calls or "setup"-looking lines. Moving a cleanup-util call earlier than the
action it's meant to clean up after silently breaks the test — e.g. deleting
an element before it's even created. Copy the fenced block top-to-bottom,
line for line, with no reasoning about what "should" come first.

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

**Elements with a `locator_spec`** (recording-sourced, per `analyze-requirements` Branch R —
JSON like `{"steps": [{"method": "get_by_role", ...}]}`): put that JSON string, verbatim and
unmodified, into **both** `css_selector` and `xpath` on the element. Confirmed against
`agentic_ai_be`'s actual persistence code (`claude_test_case_service.py`/
`claude_util_service.py`: `selector = el.css_selector or el.xpath or "selector"`) —
`css_selector` is the field that's actually authoritative (it wins whenever present; `xpath` is
only a fallback if `css_selector` is empty). Still write to both: it costs nothing, and it means
this doesn't silently break if that precedence ever changes.
```json
{"name": "otp_textbox", "css_selector": "{\"steps\": [{\"method\": \"get_by_role\", \"args\": [\"textbox\"], \"kwargs\": {\"name\": \"Enter 6-digit OTP\"}}]}", "xpath": "{\"steps\": [{\"method\": \"get_by_role\", \"args\": [\"textbox\"], \"kwargs\": {\"name\": \"Enter 6-digit OTP\"}}]}"}
```
Do not split the JSON across the two fields or otherwise alter it — the executing runtime parses
it as one unit.

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

## Known backend quirks — `save_claude_test_cases` fails silently, no per-item error

`save_claude_test_cases` returns `{"detail": "No test cases were saved"}` (400)
for the **entire batch**, or silently drops **individual** test cases from a
batch (check `total_test_cases` in the response against how many you sent —
if it's lower, some were dropped with no indication of which one or why),
for reasons that are not validated anywhere in the MCP tool schema. Known
triggers, discovered by bisection:

1. **`created_by` contains `@` (an email) or is a raw UUID.** See Step -1 above
   — always resolve and use `empName` instead.
2. **A bare single-tag CSS selector** for any element, e.g. `"h1"`, `"button"`,
   `"div"` with no attribute/class/ancestor scoping. Fails the whole test case
   silently. Fix: scope it, e.g. `"main h1"`, `"form button[type=submit]"`,
   `".card h1"`. This applies even when the selector is accurate — Playwright's
   `page.locator('h1')` in a recording is a valid *locator* but is not an
   acceptable *CSS selector* for this endpoint on its own.
3. **`description` longer than roughly 300 characters** gets silently rejected
   — no field-level error, just the generic "No test cases were saved" for
   that test case. Keep descriptions under ~200 characters. If the source
   material needs more nuance (e.g. flagging an inferred/unverified
   constraint), put the caveat in a `<!-- COMMENT -->` in the markdown file
   instead of stuffing it into the pushed `description`.
4. **`css_selector`/`xpath` holding a JSON `locator_spec`** (see Step 3 above) has not yet been
   exercised with a real push the way quirks 1-3 were, but the persistence path was read
   directly: `claude_test_case_service.py`/`claude_util_service.py` do
   `selector = el.css_selector or el.xpath or "selector"` with no format/regex validation on
   either field, and `ClaudeElement.css_selector`/`.xpath` are plain unvalidated `Optional[str]`
   — there's no code path that would reject a JSON string specifically. Quirk 2 is about *bare
   single-tag* selectors only, which a JSON object string is not. Still, if a test case with a
   `locator_spec` element fails silently, bisect it first per the method below before assuming
   the cause is elsewhere.

**How to debug a batch that silently drops items:** don't guess — bisect.
Retry the suspected test case **alone** with a throwaway name first (to
separate "is it this test case" from "is it a duplicate name conflict"), then
strip it down step-by-step (short description → long description; one element
at a time) until the failing ingredient is isolated. This is faster than
re-reading the schema for constraints that aren't there.

**Do not debug by trial-and-error pushes into the real target module/feature.**
There is no delete or update tool exposed via MCP for test cases — every debug
probe you push is permanent clutter the user has to clean up by hand in the UI.
If you must bisect live, say so before doing it (*"I'll need to push a few
throwaway probes into `<module>/<feature>` to isolate this — they'll need
manual cleanup after"*) rather than doing dozen of silent retries, and use the
shortest, most obviously-throwaway names possible (e.g. prefix
`ZZ_DEBUG_DELETE_ME_`) so they're easy for the user to find and bulk-remove
afterward.

## Note on step format

The `save_claude_test_cases` endpoint runs zero LLM — it only applies a regex
normaliser to fix minor spacing issues (e.g. `navigateto` → `navigate to`).
Steps must already be in autopilot format as described in the
`analyze-requirements` skill's step format guide. If steps are in plain English
rather than autopilot format, use `create_test_cases` instead (which does run LLM
analysis) and accept that element locators will not be preserved.
