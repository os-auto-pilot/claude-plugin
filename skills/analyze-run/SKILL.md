---
name: analyze-run
description: Analyze a finished Oniesoft test run for top failure reasons, compare runs, or explain a stack trace in plain language. Use when the user asks why tests failed, what changed between runs, or to interpret a trace.
---

# Analyze Oniesoft test runs

Turn raw run results into actionable insight using `analyze_test_run`,
`compare_test_runs`, and `analyze_stack_trace`.

## Single run — why did it fail?

- Call `analyze_test_run(test_run_id)` with `user_input` empty to get the default
  top-3 failure reasons (derived from the failing cases' stack traces, in plain
  language).
- To answer a specific question ("did the login tests pass?", "which API
  returned 500?"), pass it as `user_input`.

## Comparing runs

- Call `compare_test_runs(run_ids=[...])` to get differences in failures,
  execution time, and overall results between two or more runs — e.g. before vs.
  after a fix, or across environments.

## Explaining a trace

- For a raw stack trace the user pastes, call `analyze_stack_trace(stack_trace)`
  to get a root-cause + likely-fix explanation.

## Reporting

- Summarize the top reasons and concrete next steps (re-run, fix a selector,
  adjust expected status code, etc.).
- If failures look like flaky locators on web/mobile, note that Oniesoft's
  self-healing semantic locators usually absorb UI churn — persistent locator
  failures may indicate a real UI change worth confirming.
