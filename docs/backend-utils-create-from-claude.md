# Backend Implementation Spec: `POST /api/utils/create-from-claude`

**Service:** Platform API (`agentic_ai_be`, same service as `/api/test-cases/create-from-claude`)  
**Auth:** `x-api-key` header — validate using the same middleware as every other `/api/` route

---

## 1. Request Body

```json
{
  "utils": [
    {
      "utilName": "login_as_standard_user",
      "testMode": "Web",
      "testData": [
        { "field": "email",    "value": "user@example.com", "type": "text" },
        { "field": "password", "value": "Test@123!",        "type": "text" }
      ],
      "utilTestCaseSteps": [
        "navigate to \"/login\"",
        "enter \"<email>\" in \"el:email_textbox\"",
        "enter \"<password>\" in \"el:password_textbox\"",
        "click on \"el:login_button\"",
        "check element \"el:dashboard_header\" is visible in the page"
      ],
      "elements": [
        { "name": "email_textbox",    "css_selector": "input[name='email']",    "xpath": null },
        { "name": "password_textbox", "css_selector": "input[type='password']", "xpath": null },
        { "name": "login_button",     "css_selector": "button.btn-login",       "xpath": null },
        { "name": "dashboard_header", "css_selector": "h1.dashboard-title",     "xpath": null }
      ],
      "fileIds": [],
      "feature": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
  ],
  "module": "Authentication",
  "project_id": "248af507-c75c-4590-95b8-4145891df8d0",
  "user_id": "15eb541f-2dbe-403f-8191-9e1ad15fc0ef",
  "created_by": "claude-code"
}
```

### Field Notes

| Field | Notes |
|---|---|
| `utils` | Array, 1 or more util objects |
| `testMode` | One of `"Web"`, `"API"`, `"Mobile"` |
| `testData` | Array of `{ field, value, type }` objects; `type` is always `"text"` unless it's a file upload |
| `utilTestCaseSteps` | Plain autopilot-format strings; treat as opaque — no re-parsing or re-analysis |
| `elements` | Full element objects with name + selectors; `xpath` may be `null` |
| `feature` | UUID of the feature this util belongs to (already validated on the Claude side) |
| `project_id`, `user_id` | UUIDs; treat as required (Claude plugin always fills them from config defaults) |
| `created_by` | String, typically `"claude-code"` or the user's name; store for audit |

---

## 2. Processing Steps (per util in the batch)

Process each util in the array sequentially or in parallel. For each:

### Step 2a — Resolve Elements

For each item in `elements`:

1. Call `GET /elements/v1` (or equivalent internal service) with `name` and `projectId` to check if an element with that name already exists in the project.
2. **If found:** use the existing element's `id`. Do not create a duplicate.
3. **If not found:** call `POST /elements/v1` to create the element with:
   - `name` — from `elements[i].name`
   - `cssSelector` — from `elements[i].css_selector`
   - `xpath` — from `elements[i].xpath` (may be null/omitted)
   - `projectId` — from the request
   - `featureId` — from `util.feature`
   - `createdBy` — from request `created_by`

   Capture the returned element `id`.

Collect all resolved element IDs into a list: `resolvedElementIds: [uuid, uuid, ...]`

This is the same element resolution pattern used by `POST /api/test-cases/create-from-claude`.

### Step 2b — Serialize Test Data

Convert the `testData` array to the format expected by the backend util service. The existing `/utils/v1/create-util/{projectId}` backend endpoint accepts test data as a JSON string in a `testData` field. Serialize the array:

```json
"testData": "[{\"field\":\"email\",\"value\":\"user@example.com\",\"type\":\"text\"},{\"field\":\"password\",\"value\":\"Test@123!\",\"type\":\"text\"}]"
```

If the backend accepts it as a structured array instead, pass it as-is — check what the existing `POST /utils/v1/create-util/{projectId}` endpoint currently expects and match that.

### Step 2c — Call the Backend Util Creation Service

Call `POST /utils/v1/create-util/{projectId}` (existing backend endpoint) with:

```json
{
  "utilName": "login_as_standard_user",
  "testMode": "Web",
  "testData": "<serialized per Step 2b>",
  "utilTestCaseSteps": ["navigate to \"/login\"", "..."],
  "elementIds": [
    "uuid-of-email_textbox",
    "uuid-of-password_textbox",
    "uuid-of-login_button",
    "uuid-of-dashboard_header"
  ],
  "fileIds": [],
  "featureId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "module": "Authentication",
  "projectId": "248af507-...",
  "userId": "15eb541f-...",
  "createdBy": "claude-code"
}
```

Capture the response: expect `{ id, utilName, uniqueKey, ... }` from the backend.

---

## 3. Response Body

After processing all utils in the batch, return:

```json
HTTP 200
{
  "created": [
    {
      "id": "uuid-of-created-util",
      "utilName": "login_as_standard_user",
      "uniqueKey": "Util-00123"
    }
  ],
  "count": 1
}
```

One entry in `created` per util, in the same order as the input `utils` array. The `id` and `uniqueKey` are what the Claude plugin uses to replace `execute util "placeholder"` with `execute util "real-uuid"` in test case steps.

---

## 4. Error Handling

| Scenario | HTTP Status | Response |
|---|---|---|
| Missing or invalid `x-api-key` | 401 | `{ "error": "Unauthorized" }` |
| `project_id` or `feature` UUID not found | 404 | `{ "error": "Project/Feature not found", "field": "project_id" }` |
| Element creation fails for one util | 500 | Surface the backend error verbatim; include `utilName` in the error message so the caller knows which util failed |
| Util creation fails on backend | 500 | Surface the backend error verbatim with `utilName` |
| `utils` array is empty | 400 | `{ "error": "utils array must not be empty" }` |

### Partial Failure (207)

If some utils succeed and some fail, return 207 with a mixed response:

```json
HTTP 207
{
  "created": [
    { "id": "uuid", "utilName": "login_as_standard_user", "uniqueKey": "Util-00123" }
  ],
  "failed": [
    { "utilName": "logout_user", "error": "Feature not found: 3fa85f64-..." }
  ],
  "count": 1
}
```

---

## 5. What NOT to Do

- **Do not re-analyze or re-interpret steps.** The `utilTestCaseSteps` are already in autopilot format authored by Claude. Store them verbatim — no NLP, no LLM call, no syntax transformation.
- **Do not create duplicate elements.** Always check by name + projectId before creating.
- **Do not create duplicate utils.** If a util with the same `utilName` and `featureId` already exists in the project, either return its existing UUID (idempotent) or return a 409 Conflict — match the behavior of the existing `POST /api/test-cases/create-from-claude` endpoint.

---

## 6. Implementation Checklist

- [ ] Add route `POST /api/utils/create-from-claude` to the platform API router
- [ ] Apply the existing `x-api-key` auth middleware
- [ ] Implement element resolution (lookup by name → create if missing) — reuse the same helper used by `POST /api/test-cases/create-from-claude`
- [ ] Call `POST /utils/v1/create-util/{projectId}` for each util with resolved element IDs
- [ ] Return `{ created: [{id, utilName, uniqueKey}], count }` on success
- [ ] Return 207 with `created` + `failed` arrays on partial failure
- [ ] Write one integration test: POST with 2 utils (one with existing element, one with new element) → verify both are created and both UUIDs are returned
