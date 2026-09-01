---
name: run-tests
description: Run a single test case by its name or unique key, wait for completion, and present a structured pass/fail report. Handles Web, API, Mobile and Performance test cases — Performance runs additionally collect a load profile (virtual users, ramp pattern, duration, capped at 3 minutes). Use when the user asks to run, execute, load-test or test a specific test case. Only one test case can run at a time — the backend enforces this.
---

# Run Test Case

Execute a test case on the autopilot backend, wait for it to complete, and report results in a consistent format.

> **IMPORTANT — One at a time:** The backend allows only **one test case execution per user at a time**. Never attempt to run multiple test cases in parallel. If the user asks to run several, run them sequentially one after the other, or confirm with the user which to run first.

---

## Step 1 — Resolve the test case UUID **and its test mode**

The user will provide a test case name or unique key (e.g. `TC-0042` or `"Login with valid credentials"`).

Call `get_test_cases_with_filters` with `nameOrUniqueKey` set to what the user gave — it matches
on either, and returns the `testMode` you need in Step 2 alongside the UUID.

- If exactly one result → use its `id` and `testMode`. Proceed.
- If multiple results → show the list (name + uniqueKey + testMode) and ask the user to confirm which one.
- If no results → tell the user no matching test case was found. Stop.

> **Read `testMode` off the result — never guess it from the name.** A test case called
> "Load test checkout" may well be a `Web` case, and "API smoke" may be a `Performance` one.
> Step 2 branches on this value, so getting it from the backend matters.
>
> When a search returns **more than 10** results the tool switches to a compact output shape
> that omits `testMode`. If that happens, narrow the search (add the unique key, or pass
> `testMode`) rather than proceeding without it.

---

## Step 2 — Collect run parameters

You need:

| Parameter | How to get it |
|-----------|--------------|
| `envId` | Call `get_environments_assigned_to_user`. List all returned environments by name and ask the user to choose one — always ask, even if only one exists. |
| `browserType` | Default `Chrome`. Ask only if the user has specified a different browser. |
| `userId` | Use the plugin default (`PLATFORM_USER_ID`). |
| `platform` | Default `server,server` (runs on cloud). Ask only if the user requests local execution. |

**If `testMode` is `Performance`, also do Step 2a.** For `Web`, `API`, and `Mobile`, skip
straight to Step 3 — the load-profile fields do not apply and must not be sent.

---

## Step 2a — Load profile (Performance test cases only)

Virtual users, ramp pattern, and duration are **execution config, not part of the authored
steps** (see `performance-testing/SKILL.md`) — they are chosen here, at run time.

**Show the defaults first and let the user accept them in one step.** Don't interrogate the
user field by field; present the profile and ask a single question:

> This is a **Performance** test case. It will run with the default load profile:
>
> | Setting | Default |
> |---|---|
> | Virtual users | **100** |
> | Ramp pattern | **linear** |
> | Duration | **1m** |
>
> Continue with these, or change them? (max duration **3 minutes**)

- **User accepts** → call `run_test_case` **omitting** `virtualUsers`, `rampPattern`, and
  `duration` entirely. The backend applies exactly these defaults. Do not pass them explicitly
  just to restate the defaults.
- **User overrides some or all** → pass only the fields they changed; omit the rest.
- **User already gave values in their original request** (e.g. "run TC-08983 with 500 users for
  2 minutes") → use those, show the resulting profile back for confirmation, and don't re-ask
  what they already answered.

**Accepted values:**

| Field | Accepted | Notes |
|---|---|---|
| `virtualUsers` | integer `1`–`50000` | |
| `rampPattern` | `linear`, `incremental`, `waved` | Case-insensitive — `Linear` is normalized for you |
| `duration` | `<int>s` / `<int>m` / `<int>h`, or a bare integer of seconds | e.g. `30s`, `2m`, `180` |

### Duration limit — hard stop at 3 minutes

**If the user asks for a duration longer than 3 minutes, do not start the run.** Do not silently
clamp it to 3 minutes, and do not call `run_test_case` "to see what happens" — tell the user:

> A duration of `<what they asked for>` exceeds the 3-minute limit for load tests started from
> this plugin. For longer runs, use the Autopilot portal: https://www.osautopilot.com

Then stop, or offer to re-run within the limit if they want. This applies to every equivalent
form of the same value — `4m`, `240`, and `1h` are all over the limit.

`RunTestCaseInput` enforces this too, so an over-limit value raises a validation error naming
the portal rather than reaching the backend. Treat that as a backstop, not the primary path —
catching it here means the user gets a clear answer instead of a tool error.

---

## Step 3 — Start execution

Call `run_test_case` with the resolved UUID and parameters — plus the load profile from Step 2a
if, and only if, this is a `Performance` test case and the user changed something.

- On success → confirm to the user: *"Test case execution started. Waiting for results…"*
  For a Performance run, restate the profile actually in effect (e.g. *"…with 250 virtual users,
  waved ramp, 2m"*) so the user can see what the run is doing.
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

For a **Performance** run, add one line under the header recording the profile the run actually
used, so the numbers below are interpretable:

**Load Profile:** 250 virtual users · waved ramp · 2m

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
| Duration over 3 minutes | Don't run. Point the user to https://www.osautopilot.com (see Step 2a). |
| Validation error naming the portal | You passed an over-limit duration — Step 2a should have caught it. Relay the limit and the portal link; don't retry with a clamped value unless the user asks. |
| `virtualUsers` out of range (1–50000) | Report the accepted range and ask for a value within it. |
| Load-profile fields rejected on a non-Performance case | You sent a load profile for a `Web`/`API`/`Mobile` case. Re-run without those fields. |
