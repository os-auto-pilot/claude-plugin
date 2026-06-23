---
name: analyze-requirements
description: Analyze a requirement document, codebase, or Swagger/OpenAPI spec and generate structured manual test cases in markdown covering all Functional +Ve, Functional -Ve, and edge cases. Use when the user wants to create test cases from requirements, a spec, a swagger doc, or application source code.
---

# Analyze Requirements → Generate Manual Test Cases

You are the test case author. Analyze the provided input and produce structured
manual test cases in the standard Oniesoft template. Claude is the brain here —
do NOT call any backend tools in this phase.

## Step 1 — Understand the input type

Ask the user what they are providing if not clear:
- **Requirement / Feature doc** → analyze directly
- **Codebase** → read the relevant source files to understand controllers,
  routes, business logic, and UI components
- **Swagger / OpenAPI doc** → ask: *"Which controller or endpoint do you want
  test cases for?"* before proceeding. Do not generate for the entire spec at once.

## Step 2 — Scope check

Before generating, scan the input and list all modules and features detected.
If there are more than 3 modules or 10+ features, **ask the user**:
> "I found these modules: [list]. Which ones should I cover first?"

Generate only for the selected scope. Track what has been covered in
`test-coverage.md` (create or update it in the working directory):

```markdown
# Test Coverage Tracker
| Module | Feature | Status | File | Date |
|--------|---------|--------|------|------|
| Auth | Login | Done | test-cases-auth-login.md | 2026-06-22 |
| Auth | Register | Pending | — | — |
```

## Step 3 — Generate test cases

For each module + feature combination, produce a markdown file named
`test-cases-<module>-<feature>.md` (lowercase, hyphenated).

Cover all of:
- **Functional +Ve** — valid inputs, happy path, boundary-valid values
- **Functional -Ve** — invalid inputs, missing fields, wrong types, auth failures
- **Edge cases** — empty strings, max-length values, special characters,
  concurrent actions, state-dependent flows

**Numbering:** TC-001, TC-002, … per file. Reset per file.

## Test Case Template (use exactly, every time)

```markdown
## TC-001: [Concise test case name]
**Module:** [Module name]
**Feature:** [Feature name]
**Type:** Functional +Ve
**Priority:** Major
**Test Phase:** QA

### Pre-conditions
- [List what must be true before this test runs]

### Test Steps
| Step | Action | Test Data | Expected Result |
|------|--------|-----------|-----------------|
| 1    | [Action] | [Data if any] | [Expected outcome] |

### Expected Result
[Overall expected outcome in one or two sentences]

### Element Info *(populated in Phase 2)*
| Element | Playwright Locator | CSS Selector | XPath |
|---------|--------------------|--------------|-------|
| [name]  | —                  | —            | —     |

### API Details *(only for api test_mode)*
**Endpoint:** METHOD /path
**Request Body:**
```json
{}
```
**Expected Response:** 200 `{}`
```

### Priority guidelines
| Priority | When to use |
|----------|-------------|
| Blocker  | App cannot be used at all without this working |
| Critical | Core business flow broken |
| Major    | Important feature broken, workaround exists |
| Minor    | Cosmetic, edge case, low-impact |

## Autopilot step format (use this in the `steps` list)

Steps in the `steps` field of the template must be written in autopilot format so
the backend can execute them without re-analysis. Reference element names with the
`el:` prefix exactly as you named them in the Element Info table.

**Web / Mobile steps:**
```
navigate to "https://app.example.com/login"
enter "test@example.com" in "el:email_textbox"
enter "<password>" in "el:password_textbox"
click on "el:login_button"
check element "el:dashboard_header" is visible in the page
check text of "el:welcome_label" is "Welcome, Admin"
select option "Admin" in "el:role_dropdown"
scroll down until "el:submit_button" is visible
```

**API steps:**
```
with bearer auth to login endpoint "/auth/login" using payload {"email": "<email>", "password": "<password>"}
with body {"name": "John", "email": "<email>"}
call post "/api/users"
check status code is 201
check "$.id" value is "<user_id>"
store the "$.id" in "created_user_id"
call get "/api/users/$$created_user_id"
check status code is 200
```

Element name rules:
- Use `el:` prefix in steps: `el:email_textbox`, `el:login_button`
- Include element type in name: `textbox`, `button`, `link`, `dropdown`, `checkbox`, `label`
- Use `<placeholder>` for test data that varies: `"<email>"`, `"<password>"`
- Use literal strings for fixed values: `"Admin"`, `"https://..."`, `200`

## Step 4 — After generating

1. Update `test-coverage.md` with the newly covered modules/features.
2. Tell the user:
   - How many test cases were created (total, +Ve count, -Ve count)
   - The filename(s) written
   - Which modules/features are still pending (from the tracker)
3. Ask: *"Shall I proceed to Phase 2 to discover element locators using Playwright?"*
   - If yes → hand off to the `element-discoverer` subagent with the filename(s)
   - If no → stop here; the user can run Phase 2 later with `/push-to-autopilot` after manual enrichment
