---
name: run-tests
description: Run a single test case by its name or unique key, wait for completion, and present a structured pass/fail report. Use when the user asks to run, execute, or test a specific test case. Only one test case can run at a time — the backend enforces this.
---

# Run Test Case

Execute a test case on the autopilot backend, wait for it to complete, and report results in a consistent format.

> **IMPORTANT — One at a time:** The backend allows only **one test case execution per user at a time**. Never attempt to run multiple test cases in parallel. If the user asks to run several, run them sequentially one after the other, or confirm with the user which to run first.

---

## Step 1 — Resolve the test case UUID

The user will provide a test case name or unique key (e.g. `TC-0042` or `"Login with valid credentials"`).

**Try unique key first:**

Call `get_test_cases_uuid_by_unique_keys` with the provided key(s).

- If it returns a UUID → use it. Skip to Step 2.
- If it returns no result or errors → fall through to name search.

**Name search fallback:**

Call `get_test_cases_with_filters_in_a_project` with `searchTerm` set to the test case name.

- If exactly one result → use its UUID. Proceed.
- If multiple results → show the list (name + uniqueKey) and ask the user to confirm which one.
- If no results → tell the user no matching test case was found. Stop.

---

## Step 2 — Collect run parameters

You need:

| Parameter | How to get it |
|-----------|--------------|
| `envId` | Call `get_environments_assigned_to_user`. List all returned environments by name and ask the user to choose one — always ask, even if only one exists. |
| `browserType` | Default `Chrome`. Ask only if the user has specified a different browser. |
| `userId` | Use the plugin default (`PLATFORM_USER_ID`). |
| `platform` | Default `server,server` (runs on cloud). Ask only if the user requests local execution. |

---

## Step 3 — Start execution

Call `run_test_case` with the resolved UUID and parameters.

- On success → confirm to the user: *"Test case execution started. Waiting for results…"*
- On failure → surface the error verbatim. **Do NOT call `wait_for_test_execution_completion`.** Stop.

---

## Step 4 — Wait for completion

Call `wait_for_test_execution_completion` with the test case UUID.

This tool polls until status is `Pass`, `Fail`, or `Abort` (timeout: ~5 minutes).

---

## Step 5 — Present results

Always present results in this exact format, regardless of pass or fail:

---

### Test Execution Report

**Test Case:** `<name>`
**Status:** ✅ Pass / ❌ Fail / ⚠️ Abort
**Executed At:** `<executeTime>`

#### Step Results

Parse the `traceStack` field from the execution result. The trace contains one line per step.

**Before rendering the table**, scan the trace for any UUID-style element references (e.g. `el:3fa85f64-5717-4562-b3fc-2c963f66afa6` or bare UUIDs in step descriptions). Collect all unique UUIDs, then call `fetch_element_details_by_id` once with the full list to resolve names in parallel. In the table, replace every UUID with the resolved element `name` (e.g. `el:login_button`). If a UUID cannot be resolved, leave it as-is.

Present as a table:

| Step # | Step Name / Action | Output / Message | Status |
|--------|--------------------|-----------------|--------|
| 1      | navigate to "/login" | Navigation successful | ✅ Pass |
| 2      | enter "user@example.com" in "el:email_textbox" | Value entered | ✅ Pass |
| 3      | click on "el:login_button" | Element not found | ❌ Fail |

If the trace format does not split cleanly into a table, present it as a formatted code block instead — never omit it.

---

## Step 6 — Failure analysis (only if status is Fail or Abort)

When one or more steps failed, provide a structured failure analysis immediately after the table.

### Failure Analysis

**Failed Step(s):** List each failed step number and action.

**Root Cause:**
Analyze the error message from the trace and provide a specific explanation. Do not use generic language like "the element was not found" — explain *why* it wasn't found based on the trace (wrong selector, page not loaded, auth redirect, etc.).

**Frontend vs Backend Classification:**

| Signal in trace | Classification |
|----------------|----------------|
| Element not found, selector mismatch, unexpected redirect, page layout issue | **Frontend defect** |
| HTTP 4xx/5xx from API call, unexpected API response, assertion on API return value | **Backend defect** |
| Network timeout, environment unreachable | **Infrastructure / environment issue** |
| Step order issue, wrong test data, assertion on wrong value | **Test case defect** |

State clearly: **This appears to be a [Frontend / Backend / Infrastructure / Test case] defect.**

**Recommended Fix:**
Provide 1–3 concrete, actionable recommendations. For example:
- "The CSS selector `button.submit-btn` may have changed — check the latest DOM and update the element locator."
- "The API returned 401 on step 3 — verify the login util is running before this step and that test credentials are valid."
- "The element `el:error_banner` was not found — the validation message may have a different `data-testid` in the current build."

---

## Error handling

| Error | Action |
|-------|--------|
| `run_test_case` returns error | Surface verbatim. Do NOT call wait. Stop. |
| `wait_for_test_execution_completion` times out (>5 min) | Tell the user execution timed out. Suggest checking the platform dashboard directly. |
| UUID resolution finds no match | Tell the user, list any partial matches, stop. |
| Multiple test cases match the name | Show the list and ask the user to confirm. |
