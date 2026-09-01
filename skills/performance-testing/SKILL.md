---
name: performance-testing
description: Generate performance/load test cases from a Swagger doc — single endpoint or a multi-endpoint controller flow, with or without correlation, with or without CSV-driven data. Claude authors the load-test steps directly (zero-LLM backend push) — never calls the platform's AI-driven performance-test-generation endpoint. Use when the user wants load/performance testing, concurrent-user testing, or mentions vus/throughput/latency/correlation for an API.
---

# Performance Test Case Generation

Author performance test cases yourself and push them with `save_claude_test_cases`
(`test_mode="Performance"`) — the same zero-LLM, Claude-authored path used for web/API/mobile
test cases. **Never** call the platform's separate AI-driven performance endpoint
(`/test-cases/create` with `testMode=performance`) — that generates content server-side via an
LLM; this skill exists specifically so Claude does that authoring instead.

## Step 1 — Intake

Get the Swagger spec (URL or file) the same way `analyze-requirements` does — fetch via
`python skills/analyze-requirements/scripts/fetch_swagger.py "<url>" --output swagger-spec.json`
if a URL was given and `swagger-spec.endpoints.json` doesn't already exist, otherwise read a
local file directly. Identify the endpoint(s) involved: one endpoint (a single load-tested call)
or a controller/flow (several endpoints called in sequence, e.g. login → create order → check
status).

## Step 2 — Decide the branch

| Scope | Data | Correlation | Branch |
|---|---|---|---|
| Single endpoint | Multiple data sets (one row drives each virtual user) | — | **A** — CSV, no correlation |
| Controller / multi-endpoint flow | Multiple data sets | Needed (a later step needs a value an earlier step produced) | **B** — CSV + correlation |
| Either | Single data set | With or without | **C** — no CSV, direct |

**Determining which data column applies — check the user's prompt first, ask only if it's silent:**

- **The prompt already specifies concrete data for any field** (one value, several values, a
  range, "test with these 5 users", etc.) — use exactly what was given, and let that determine
  single vs. multiple data sets. Don't ask the clarifying question below; their intent is already
  clear from the data itself.
- **The prompt says nothing about data at all** — ask before proceeding:
  > Should this test case use a CSV file to drive multiple data sets (one row per virtual user), or run with a single, fixed set of data?
  - If the user picks **single data set** → branch C: write the literal values directly into the
    step JSON, no CSV, no `create-datafile` involved.
  - If the user picks **CSV / multiple data sets** → branch A or B per the table above: follow
    `create-datafile`'s steps inline to generate and upload it first.

- **Branches A/B need a CSV first.** Follow `create-datafile`'s steps inline (don't just
  reference it — actually generate, validate, and upload the CSV as that skill describes) before
  writing the test case. Keep the returned file `id` for `file_ids` and the file's registered
  name (minus `.csv`) for `{{data.<file>.<column>}}` placeholders. **Ask the user how many rows /
  sets of data to generate** before running `generate_csv.py` — don't assume or silently default
  a row count.

**Fields the user didn't specify — split by origin, not treated the same:**

Every field in the target endpoint's request schema (`swagger-spec.endpoints.json`'s
`request_fields`) falls into one of two buckets — handle each differently:

- **User-specified** — the prompt gave an explicit value for this field (an ID, a name, a
  literal). Use that value exactly, as a fixed literal in the step body, on every request
  regardless of what else is CSV-driven. Never put a user-specified field into the CSV.
- **Schema field the user didn't mention** — present in the endpoint's schema but not given a
  value in the prompt. This is what needs synthesized data:
  - **Single data set** → generate one plausible dummy value per such field (based on its schema
    type/format/constraints), written as a literal directly in the body — same approach
    `analyze-requirements` already uses for unspecified-but-required fields.
  - **Multiple data sets / CSV** → these unspecified fields — *only* these, not the
    user-specified ones — become the CSV's columns. When invoking `create-datafile`, scope the
    columns explicitly (`--columns "name,selector,testMode"` or `--remove "projectId,feature,module"`
    against the auto-detected set) so the CSV doesn't duplicate fields that are already fixed
    literals in the body.

**Worked example** — `POST /elements/v1` (schema fields: `name`, `selector`, `testMode`,
`feature`, `module`, `projectId`), prompt gives `projectId`, `featureId` (→ `feature`), and
`module` only, multiple data sets requested:
```
✅ CORRECT — user-specified fields stay fixed literals; only the untouched schema fields
(name, selector, testMode) are CSV-driven:
define load step "Create Element" {"method": "POST", "url": "https://api.example.com/elements/v1", "headers": {"x-api-key": "Oniesoft@123dfgewerrt", "Content-Type": "application/json"}, "body": {"projectId": "5639fd39-2b70-4b81-8439-70e58075d602", "feature": "1bddd576-9e2e-4421-b9ab-011f6fccd5fc", "module": "Suite Controller", "name": "{{data.elem_load1.name}}", "selector": "{{data.elem_load1.selector}}", "testMode": "{{data.elem_load1.testMode}}"}, "expected_status": 200}

❌ WRONG — putting a user-specified field into the CSV instead of keeping it a fixed literal:
"projectId": "{{data.elem_load1.projectId}}"
```
For the single-data-set version of the same example, `name`/`selector`/`testMode` would each be
one dummy literal written directly in the body instead — no CSV, no `create-datafile` call.
- **Branch C** — write literal values directly into the step JSON; no CSV, no `file_ids`.
- Correlation (branch B, or optionally added to A/C when a single flow still needs to pass a
  value between steps) is independent of whether a CSV is used — decide it by whether any step's
  input value is *produced by* an earlier step's response, not by data-set count.

## Step 3 — Author the steps

Each flow step becomes:
```
define load step "<name>" {"method": "<GET|POST|PUT|PATCH|DELETE>", "url": "<full URL>", "headers": {...}, "body": {...}, "expected_status": <int>}
```
- One `define load step` line per call in the flow, in order.
- `headers`/`body` are the exact request shape for that endpoint — same field-by-field rigor as
  API test cases in `analyze-requirements` (use example/schema values, never invent fields not in
  the spec).
- After all `define load step`/`capture` lines: a fixed literal line, always present —
  ```
  run the load test
  ```
- After `run the load test`: one or more `check ...` assertion lines (see the fixed grammar
  below).

**CSV-driven fields** (branches A/B): use the literal placeholder string
`{{data.<file>.<column>}}` instead of a hardcoded value, where `<file>` is the uploaded file's
`file_name` exactly as registered (it's a bare identifier already — no extension, see
`create-datafile`) and `<column>` is the exact CSV header name. Example: a file uploaded as
`ord_load1` with a `customerId` column → `{{data.ord_load1.customerId}}`.

**Correlation** (branch B, or wherever needed): identical mechanism to the `$$var` convention
already documented in `analyze-requirements/SKILL.md`'s "Variable store/access rule" section —
same rule, same `$$` access prefix, just a different capture syntax for this DSL:
- On the step that *produces* the value, add a line immediately after its `define load step` line:
  ```
  capture "<json_path>" from step "<name>" into variable "<var>"
  ```
- Any later step that *consumes* it references the plain name with the `$$` prefix, inline inside
  that step's own JSON: `"$$<var>"`.

```
✅ CORRECT — login produces a token, order creation consumes it:
define load step "Login" {"method": "POST", "url": "https://api.example.com/v1/auth/login", "headers": {"Content-Type": "application/json"}, "body": {"email": "{{data.perf_users.email}}", "password": "{{data.perf_users.password}}"}, "expected_status": 200}
capture "$.access_token" from step "Login" into variable "auth_token"

define load step "Create Order" {"method": "POST", "url": "https://api.example.com/v1/orders", "headers": {"Content-Type": "application/json", "Authorization": "Bearer $$auth_token"}, "body": {"sku": "{{data.perf_users.sku}}"}, "expected_status": 201}

run the load test

check error rate is below 1 percent
check average response time is below 800 ms

❌ WRONG — accessing the captured variable without $$:
"Authorization": "Bearer auth_token"
```

**`check` assertion grammar — use only these four exact strings, do not invent variants:**
```
check average response time is below N ms
check p95 latency is below N ms
check requests per second is above N
check error rate is below N percent
```
These are the only confirmed performance-check phrasings. There is no `test_mode="performance"`
entry in `get_autopilot_steps` to fall back on for this test mode (and that tool is scoped to
`/analyze-requirements` only per this plugin's Tool Scope Rules anyway) — do not phrase a new
assertion (e.g. "check throughput is above X") without first confirming it against a real pushed
test case; stick to the four above.

**No load concurrency field in the DSL** — virtual-user count, duration, and ramp-up are
execution config applied at test-run time, not part of the authored steps. Don't try to encode
`vus`/duration into a step; if the user specifies concurrency, tell them it's configured when the
test *runs*, not when it's authored, and proceed without it.

**No utils** — `execute util "<uuid>"` is not applicable to performance test cases; don't
reference or create utils here.

## Step 4 — Push

1. Resolve the author's display name once (same as every other push in this plugin): call
   `get_user_details_by_id_or_email_or_unique_key` → use `empName`, never an email or UUID.
2. Call `save_claude_test_cases` with `test_mode="Performance"`. Build each test case's `steps`
   array from Step 3's lines, one string per line, in order — copy them exactly as authored, no
   reordering (the backend executes `steps` in exactly the order sent).
3. For branches A/B, set `file_ids: ["<id returned by upload_datafile>"]` on the test case; leave
   it empty for branch C.
4. `elements` stays empty — performance steps have no `el:` UI elements, so there's nothing for
   Phase 2 element discovery to do here; skip straight to pushing.

## Error handling

- Same silent-drop quirks as documented in `push-to-autopilot/SKILL.md`'s "Known backend quirks"
  apply here too (`created_by` as email/UUID, `description` over ~300 chars) — this path uses the
  identical `save_claude_test_cases` tool.
- `file_ids` attachment is confirmed working (see `docs/backend-performance-test-fileids.md`) —
  verify it by fetching the test case via a single-entity read (`GET /testcases/v1/get/{id}`),
  not a list/search endpoint like `getForProject`, which doesn't project `fileIds` at all.
