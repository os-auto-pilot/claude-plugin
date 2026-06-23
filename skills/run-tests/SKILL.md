---
name: run-tests
description: Execute Oniesoft test cases or a saved test run and report pass/fail. Use when the user wants to run, execute, or kick off tests on the Oniesoft platform.
---

# Run Oniesoft tests

Execute tests on the Oniesoft execution engine and follow them to completion
using the `run_tests`, `get_run_status`, and `stop_tests` MCP tools.

## Starting a run

1. Decide the target:
   - A single test case → pass `test_case_id`.
   - A saved test run (a suite) → pass `test_run_id`.
2. Set the environment:
   - Web: `browser_type` (e.g. `chrome`, `firefox`) and `env_id`.
   - Native mobile: `platform="local,<tunnel-id>"` and `apk_id` — see the
     `mobile-testing` skill for details.
   - `parallel=true` to fan a multi-case run out concurrently.
3. Call `run_tests`. It returns an **execution id** (in `data`). Capture it.

## Following the run

- Poll `get_run_status(execution_id)` until status is no longer `running`.
- Space the polls out sensibly (the engine runs real browsers/devices — runs
  take time); don't hammer it.
- If the user asks to abort, call `stop_tests(execution_id)`.

## Reporting

- When the run finishes, summarize pass/fail. If anything failed, offer the
  `analyze-run` skill to get root-cause analysis.
- Surface any non-2xx `data` errors verbatim. A 401/403 means the API key is
  missing/expired or lacks the `run` scope.
