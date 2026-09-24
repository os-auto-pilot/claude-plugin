# Backend Implementation Record: `file_ids` on the zero-LLM test-case save path

**Service:** Platform API (`agentic_ai_be`), the existing `POST /api/test-cases/create-from-claude`
endpoint (already implemented and working — this was a small field addition, not a new endpoint).

**Auth:** unaffected — no change to auth handling.

**Status: DONE — applied and confirmed live (2026-08-04).** Both changes below are applied to
`app/models/request_response.py` and `app/services/claude_test_case_service.py`, and the
`agentic_ai_backend` Docker container was restarted to pick them up (it runs `uvicorn` without
`--reload`; the source is bind-mounted so no rebuild was needed, just a restart).

Verified end-to-end: uploaded a real CSV via `upload_datafile`, created a real performance test
case via `save_claude_test_cases` with a non-empty `file_ids`, then fetched the created test case
via `GET /testcases/v1/get/{id}` — the response correctly shows
`"fileIds": ["<the-uploaded-file-id>"]`. (Note: `GET /testcases/v1/getForProject`, the list/search
endpoint, does *not* include `fileIds` in its response projection at all, regardless of whether
the field is actually stored — an unrelated limitation of that endpoint that looked like a failed
fix on first check; `/testcases/v1/get/{id}` is the correct endpoint to verify this on.)

---

## 1. Problem

`save_claude_test_cases` (this plugin) now sends a `file_ids: List[str]` field on each test case
in the batch, so a CSV data file uploaded via `upload_datafile` (`datafiles/v1/upload`) can be
attached to a performance test case that references it via `{{data.<file>.<column>}}`
placeholders in its steps.

AgenticAI's zero-LLM `ClaudeTestCaseInput` (`app/models/request_response.py:78-88`) has no field
to receive it:

```python
class ClaudeTestCaseInput(BaseModel):
    """A single test case authored by Claude in Phase 1/2."""

    name: str
    description: str
    type: str = "Functional +Ve"
    priority: str = "Major"
    test_phase: str = "QA"
    steps: List[str]
    elements: List[ClaudeElement] = Field(default_factory=list)
    test_data: List[TestDataEntry] = Field(default_factory=list)
```

Pydantic silently ignores unknown incoming JSON keys by default (no `model_config`/
`populate_by_name`/`extra="forbid"` is set on this model) — so today, `file_ids` sent from the
plugin is dropped with **no error anywhere**. `upload_datafile` succeeds, `save_claude_test_cases`
succeeds, but the created test case never actually links to its CSV.

Note the downstream `SingleTestCase` model (same file, ~line 155) already accepts
`fileIds: Optional[List[str]] = []` — this data-model gap is only on the *inbound* zero-LLM
model. The *separate* AI-driven performance model (`CreateTestCaseRequest.dataFileIds`, same
file, line 67) already has an analogous field, and `performance_test_service.py` already forwards
it (`fileIds=request.dataFileIds or []`) — this spec just wires the same downstream capability
into the second (zero-LLM) upstream path.

## 2. Change 1 — `app/models/request_response.py`

Add one field to `ClaudeTestCaseInput` (lines 78-88):

```python
class ClaudeTestCaseInput(BaseModel):
    """A single test case authored by Claude in Phase 1/2."""

    name: str
    description: str
    type: str = "Functional +Ve"
    priority: str = "Major"
    test_phase: str = "QA"
    steps: List[str]
    elements: List[ClaudeElement] = Field(default_factory=list)
    test_data: List[TestDataEntry] = Field(default_factory=list)
    file_ids: List[str] = Field(default_factory=list)
```

**Use the field name `file_ids` (snake_case), matching this plugin's `ClaudeTestCaseInput.file_ids`
exactly.** This is deliberate, not arbitrary: every other field on this specific model is already
snake_case matching the plugin 1:1 (`test_data`, `test_phase`) — unlike the *other*, camelCase
models in the same file (`SingleTestCase`, `ClaudeUtilInput.utilTestCaseSteps`, etc.). Do **not**
reuse the name `dataFileIds` — that's already a different field on the different, AI-driven
`CreateTestCaseRequest` model in this same file (line 67); reusing it here would just move the
silent-drop bug rather than fix it.

## 3. Change 2 — `app/services/claude_test_case_service.py`

In `_process_one_test_case` (the function building the `SingleTestCase(...)` payload, ~lines
307-327 per the traced flow: `steps = tc.steps`, `_substitute_element_ids`, `"\n".join(steps)`),
add one kwarg to the existing construction, mirroring the one-line pattern already present in
`performance_test_service.py`:

```python
        single_tc = SingleTestCase(
            # ...existing kwargs unchanged...
            envId=request.env_id or "",
            testPhase=tc.test_phase,
            fileIds=tc.file_ids or [],   # NEW
        )
```

No other logic changes — `steps`/`test_data`/element handling are unaffected.

## 4. What NOT to do

- Do not add validation/format-checking on `file_ids` beyond what `List[str]` already gives —
  the plugin is responsible for only sending real file IDs returned by `datafiles/v1/upload`.
- Do not rename to `dataFileIds` or any other name — see the naming rationale in Change 1.
- Do not touch the AI-driven `performance_test_service.py` path — it already works correctly and
  is unrelated to this change.

## 5. Verification

- Push a test case via `save_claude_test_cases` with `test_mode="Performance"` and a non-empty
  `file_ids` list; confirm the resulting `/testcases/v1/save/{project_id}` call carries a
  matching `fileIds` array (not `[]`).
- Push a test case with `file_ids` omitted (defaults to `[]`); confirm no regression — behaves
  exactly as it did before this change.

## 6. Implementation Checklist

- [x] Add `file_ids: List[str] = Field(default_factory=list)` to `ClaudeTestCaseInput`
      (`app/models/request_response.py:78-88`)
- [x] Add `fileIds=tc.file_ids or []` to the `SingleTestCase(...)` construction in
      `claude_test_case_service.py`'s `_process_one_test_case`
- [x] Confirm no other reader of `ClaudeTestCaseInput` needs updating (this field is purely
      additive/optional, default `[]`) — no other readers found
- [x] Restart `agentic_ai_backend` (no `--reload`, needed a restart to pick up the bind-mounted
      source change)
- [x] Verified live: uploaded a CSV, created a performance test case referencing it, fetched it
      back via `GET /testcases/v1/get/{id}`, confirmed `fileIds` populated correctly
