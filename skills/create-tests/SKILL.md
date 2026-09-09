---
name: create-tests
description: Directly call the autopilot backend to create test cases from a short feature description (quick path, no markdown file). Use ONLY when the user explicitly wants to skip Phase 1/2 and push a quick description straight to the backend. For full requirement analysis use the analyze-requirements skill instead.
---

# Create Oniesoft test cases

Turn a plain-language requirement into stored test cases on the Oniesoft platform
using the `create_test_cases` MCP tool. The platform persists them against a
project so they can be run and managed later.

## Before generating

1. **Pick the test mode** from what the user is testing:
   - `web` — browser UI flows (default if unclear and it's a UI).
   - `api` — HTTP/REST endpoints (OpenAPI specs, request/response checks).
   - `mobile` — native Android/iOS app flows (see the `mobile-testing` skill).
     Do not default a native-app request to `web`. Do not attach Playwright locators.
     Without an Appium/Selenium recording or mobile codebase, element selectors must
     be the literal `selector`.
2. **Confirm the target**: `module` and `feature` are required and group the
   tests in the project. Ask for them if not provided. `project_id` falls back to
   the plugin's configured default — only ask if there's no default.
3. **Preview first for anything non-trivial**: call `analyze_test_steps` to show
   the user the steps/elements/test-data that would be produced, and confirm
   before committing with `create_test_cases`. For a single obvious case you can
   skip straight to creation.

## Generating

- Call `create_test_cases` with `user_input` = the scenario description, plus
  `module`, `feature`, and `test_mode`.
- For API tests, put any specific constraints (status codes, auth, field values)
  in `user_prompt` — the backend follows it strictly.
- For a batch (e.g. "cover positive, negative, and boundary cases"), make one
  call per distinct scenario rather than one giant prompt, so each becomes a
  clean, separately-runnable test case. Confirm the list with the user first.

## After generating

- Report the returned `test_cases` (ids) and counts from the `data` field.
- Offer to run them with the `run-tests` skill.
- If `ok` is false or a 4xx/5xx status comes back, surface the `data` error
  verbatim — a 401 means the API key is missing/expired, 403 means the key lacks
  the `generate` scope.
