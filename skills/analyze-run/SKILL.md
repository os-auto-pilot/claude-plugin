---
name: analyze-run
description: Analyze a finished Oniesoft test run for top failure reasons, compare runs, or explain a stack trace in plain language. Offers to create grouped defects for unique failures after analysis. Use when the user asks why tests failed, what changed between runs, or to interpret a trace.
---

# Analyze Oniesoft test runs

> **Delegation rule:** Always delegate this task to the `oniesoft-test-platform:failure-analyst`
> subagent using the Agent tool. Pass the run ID and any comparison/trace context as the prompt.
> Do not fetch MCP data inline in the main conversation.

Fetch raw results directly from the backend and analyze them yourself — no agentic AI
endpoint is involved.

## Single run — why did it fail?

1. Call `fetch_test_run_results(test_run_id)` to get overall stats (total/pass/fail/skip
   broken down by feature, module, severity, test mode, author) and a `failed_cases` list.
2. Call `fetch_test_run_failure_details(failed_case_ids=[...])` with all IDs from
   `failed_cases` to retrieve trace stacks, test data, and test steps.
3. If a trace references an element ID → call `fetch_element_details(element_id)` for
   the element name and selector context.
4. If a trace references a util ID → call `fetch_util_details(util_id)` for the step
   definition.
5. Analyze and group failures by root cause:
   - **Real defect** — assertion mismatch, unexpected API response, business logic error
   - **Env / setup** — auth failure, missing test data, timeout
   - **Locator** — element not found (Oniesoft's semantic locators self-heal UI churn;
     persistent locator failures likely indicate a genuine UI change)

## Comparing runs

- Repeat steps 1–2 for each run ID.
- Produce a side-by-side stats table (total/pass/fail by feature, module, severity).
- Highlight what improved or regressed and any shared vs. run-specific failure patterns.

## Explaining a stack trace

If the user pastes a raw trace, analyze it directly — no tool call needed. Identify the
root cause and a concrete likely fix.

## Reporting

- Summarize top failure reasons with concrete next steps (re-run, fix selector, adjust
  expected value, confirm a real UI change, etc.).
- Use names not raw UUIDs in the final output where available.
- Surface any non-2xx HTTP errors verbatim.

## After analysis — offer defect creation

When the run has failures, ask after the report:

> Do you want to create defects for the failed cases?

- **No** → stop.
- **Yes** → delegate to the `auto-pilot:defect-creator` subagent (do not call `create_defect` inline).
  Pass the run ID, failure analysis, and `failed_cases`. The subagent follows
  `create-defect` — one defect per unique failure reason with comma-separated unique keys
  in `dependency`.
