---
name: create-defect
description: >-
  REQUIRED before calling create_defect. Create an Oniesoft defect from test failure
  or manual triage — assignee picker, module/feature resolution, user confirmation.
  Use when the user asks to log a bug, create a defect, or file an issue. Do NOT call
  create_defect directly; read and follow this skill end-to-end first, or delegate to
  the defect-creator subagent.
---

# Create Defect

Log a defect on the Oniesoft platform via `create_defect`.

> **User names, not UUIDs:** `createdBy`, `assignedTo`, `updatedBy`, `developedBy`,
> `verifiedBy`, `automatedBy`, and `reviewedBy` all take plain display names (`empName`)
> — never an email or UUID. Resolve names with `get_user_details_by_id_or_email_or_unique_key`.

---

## Step 1 — Resolve the creator

Read `config.json` for `userId`, `companyId`, and `projectId`.

Call `get_user_details_by_id_or_email_or_unique_key` with:
- `identifier` → `userId` from config
- `companyId` → from config

Use the returned `empName` as `createdBy`, `assignedBy`, and all other creator/updater
name fields (`updatedBy`, `developedBy`, `verifiedBy`, `automatedBy`, `reviewedBy`).
`assignedBy` is always the same as `createdBy` — the tool fills it in automatically if omitted.

---

## Step 2 — Choose assignee

**Always call `get_users_assigned_to_project` first** (with `projectId` from config) before
asking the user anything about assignee. Do not invent an assignee list or add an "Other"
option.

Present **every** returned user in a numbered table — use only names from the API response:

| # | Name | Email | Role |
|---|---|---|---|
| 1 | … | … | … |

Ask: *"Who should own this defect? Pick a number from the table above."*

- **Ask even when only one user is returned** — show the table, then ask.
- **Never skip the tool call** and jump straight to "give me a name or email".
- **Never add "Other"** — the table is the complete list of assignable users.

Only if `get_users_assigned_to_project` returns an **empty list**, say no users are assigned
to this project and fall back to `get_user_details_by_id_or_email_or_unique_key` with
`companyId` from config and a name/email search term.

Use the chosen user's:
- `empName` → `assignedTo` and the other name fields above (same as creator when self-assigned)
- `userId` → `assignedToUUID`

---

## Step 3 — Module and feature

`create_defect` requires `module` and `feature` as **UUIDs**.

Failed cases from `fetch_test_run_results` already carry `module` and `feature` on each
`failed_cases` entry. Use those values first — **do not look up when the value is already
a UUID**:

1. Pick module/feature from a representative case in the failure group (first case, or the
   largest shared module+feature pair across the group).
2. For each value:
   - **Valid UUID** → pass it straight to `create_defect`.
   - **Name or unique key** (e.g. `"Authentication"`, `"FEAT-0042"`) → resolve once:

     | Field | Tool |
     |---|---|
     | Module | `get_module_id_by_name_or_unique_key` with `identifier` = module value |
     | Feature | `get_feature_id_by_name_or_unique_key` with `identifier` = feature value |

     Use the returned `.id` UUID.

3. If the run payload also has `moduleId` / `featureId` fields on a failed case, prefer
   those over `module` / `feature` when present.

If cases in one group span different modules/features, use the pair from the largest
sub-group, or ask the user.

---

## Step 4 — Defect content

Collect or draft:

| Field | Guidance |
|---|---|
| `title` | Short, specific summary of the failure (≤ 120 chars) |
| `description` | Root cause, failing step, trace excerpt, environment, run name/ID |
| `priority` | **Required — you must choose.** Do not default to Minor. Pick based on impact: |
| `assignedBy` | Same as `createdBy` (auto-filled by the tool if omitted) |
| `dependency` | Comma-separated test-case unique keys, e.g. `TC-89765,TC-89099` — no spaces |
| `testMode` | `Web`, `API`, `Mobile`, or `CLI` from the failing case(s) |
| `testType` | `Automation` for automated test failures; `Manual` otherwise |
| `rootCause` | Default `Other`; set a more specific value when clear from triage |

### Priority rubric (choose one — explain your choice in the confirmation table)

| Priority | Use when |
|---|---|
| **Blocker** | Entire workflow or release is blocked; no workaround; crash, data loss, security hole, payment/auth completely broken |
| **Critical** | Core feature unusable for most users; widespread failures (many cases / key regression path); production-down class issues |
| **Major** | Important feature broken but workaround exists; single critical path fails; API returns wrong data for a key operation |
| **Minor** | Cosmetic/UI polish, edge case, flaky locator, low-traffic path, minor assertion wording mismatch |

When test-case `severity` is known from `failed_cases`, use it as a **starting point**
(Blocker→Blocker, Critical→Critical, Major→Major, Minor→Minor) but **override** if the
failure analysis shows higher or lower real-world impact.

Leave `status`, `state`, `sprint`, and `story` unset unless the user specifies them.

---

## Step 5 — Create

Call `create_defect` with all required fields:

```
title, description, priority, assignedTo, assignedToUUID, userId, createdBy,
assignedBy, updatedBy, developedBy, verifiedBy, automatedBy, reviewedBy,
module, feature, projectId, companyId
```

Plus optional: `dependency`, `testMode`, `testType`, `rootCause`,
`environment`, `browser`, `comments`.

Report back: defect `uniqueKey`, `title`, assignee, and linked test cases (`dependency`).

---

## From test-run analysis — group unique failures

Use this when the user confirms defect creation after `analyze-run` / `failure-analyst`.

1. **Group failures by root cause** — cases that failed for the same reason (same assertion,
   same missing element, same API error) belong in one group. Normalize trace text before
   comparing (strip timestamps, run IDs, and volatile URLs).

2. **One defect per group** — if 3 test cases failed with the same reason, create **one**
   defect, not three.

3. **`dependency`** — comma-join every `uniqueKey` in the group
   (from `failed_cases` in `fetch_test_run_results`). Skip cases with no unique key.

4. **Title** — summarize the shared failure, e.g.
   `Login button not found on checkout page`.

5. **Description** — list all affected test case names and unique keys, the shared root cause,
   and one representative trace. Note the test run name/ID.

6. **Skip non-defect failures** unless the user asks to include them — do not create defects
   for pure environment/setup issues (auth failure, missing test data, network timeout) unless
   the user explicitly wants those logged too.

7. **Confirm before creating** — show a table of planned defects:

   | # | Title | Test cases (unique keys) | Priority (rationale) | Assignee |
   |---|---|---|---|---|
   | 1 | … | TC-001, TC-002, TC-003 | Major — checkout blocked | … |

   Include a one-line **rationale** for each priority. Ask the user to confirm or adjust
   assignee/priority, then create each row via Step 5.

---

## Examples

**Single manual defect**

User: "Create a defect for the login failure, assign to Priya"

→ Resolve Priya via `get_user_details_by_id_or_email_or_unique_key`, resolve module/feature,
draft title/description from context, call `create_defect`.

**After run analysis — 5 failures, 2 unique causes**

| Group | Cases | Action |
|---|---|---|
| Element `#submit` not found | TC-101, TC-102, TC-103 | 1 defect, `dependency: TC-101,TC-102,TC-103` |
| API 500 on `/orders` | TC-201, TC-202 | 1 defect, `dependency: TC-201,TC-202` |

→ 2 `create_defect` calls total.
