---
name: schedule-test-run
description: Schedule an existing test run to execute at a future date and time, on a chosen environment. Prompts for the environment from the ones assigned to the user whenever the request doesn't name one. Use when the user asks to schedule, defer, or set a time for a test run (e.g. "schedule the regression suite for tomorrow 9pm").
---

# Schedule a Test Run

Set an existing test run to execute later, on a specific environment.

> **Scheduling mutates an existing run configuration** — it flips `scheduleExecution` on and
> overwrites the stored date, time, and environment. It is not a preview. Confirm the full
> schedule with the user (Step 5) before calling `schedule_test_run`.

> **This schedules a *test run*, not a test case.** Individual test cases can't be scheduled —
> they run immediately via `run-tests`. If the user names a test case, tell them it needs to be
> part of a test run first (`create_test_run` / `add_or_remove_test_cases_from_test_run`).

---

## Step 1 — Resolve the test run

The user will give a test run name or unique key (e.g. `TR-0007`, `"Nightly regression"`).

Call `get_test_runs_with_filters` with `nameOrUniqueKey` set to what they gave.

- Exactly one result → use its `id`.
- Multiple results → show name + uniqueKey + status, ask which one.
- No results → say so and stop. Don't create a test run unless the user asks.

---

## Step 2 — Environment (ask whenever it wasn't specified)

**If the user named an environment in their request**, use it — but still fetch the list below
and confirm the name matches one they actually have access to. A name the backend doesn't
recognize is stored as-is and surfaces later as a confusing run-time failure.

**If the user did not mention an environment at all — which is the common case — always ask.**
Do not reuse whatever environment the run config already holds, and do not guess:

1. Call `get_environments_assigned_to_user` with:
   - `userID` → the `userId` from the project's `config.json`
   - `projectId` → the project default
2. Present every returned environment so the choice is informed — the name alone is often
   ambiguous between similarly-named environments:

   | # | Environment | URL | Description |
   |---|---|---|---|
   | 1 | `QA` | `https://qa.example.com` | QA regression box |
   | 2 | `Staging` | `https://stg.example.com` | Pre-prod mirror |

3. Ask which one to schedule against. **Ask even when only one environment is returned** — the
   user should see which environment their run is being pinned to.
4. If the list comes back empty, stop: no environments are assigned to this user, so there is
   nothing valid to schedule against. Tell them to get one assigned in the platform.

> **Pass the environment *name*, not its UUID.** `schedule_test_run`'s `environment` field takes
> the display name (`serverName`, e.g. `"Staging"`) and sends it to the backend as `envName`.
> This is the exception to this plugin's usual "resolve to a UUID first" rule — passing a UUID
> here schedules the run against an environment named after a UUID, which will not resolve.

---

## Step 3 — Date and time

| Field | Format | Notes |
|---|---|---|
| `scheduledDate` | `YYYY-MM-DD` | e.g. `2026-08-14` |
| `scheduledTime` | `HH:mm`, 24-hour | e.g. `21:30`, not `9:30 PM` |
| `userTimezone` | IANA name | e.g. `Asia/Kolkata`, `America/New_York` — never an abbreviation like `IST` or an offset like `+05:30` |

Resolve relative phrasing ("tomorrow 9pm", "next Monday morning") against today's date, then
**state the absolute date you resolved it to** in the Step 5 confirmation — that is where an
off-by-one day gets caught, and a silently wrong date means the run fires on the wrong day.

If the user gave a time but no timezone, use the system timezone (`date +%Z` / the IANA name
from the host) and say which one you used rather than asking. Ask only if the host timezone
can't be determined.

Verify the resulting instant is in the **future**. If it isn't, say so and ask for a new
time — a past schedule either never fires or fires immediately, depending on the backend.

---

## Step 4 — Ambiguity worth one question

Ask before scheduling if either is true:

- The run's current status is `Scheduled`, `Auto Scheduled`, or `In Progress` — scheduling
  overwrites an existing schedule, or collides with a run already going. Confirm that's intended.
- The user said "schedule it" with no time at all. Don't invent one; ask.

---

## Step 5 — Confirm, then schedule

Show the full picture and get an explicit yes:

> Scheduling **Nightly regression** (`TR-0007`):
>
> | | |
> |---|---|
> | Environment | `Staging` |
> | Date | `2026-08-14` (Friday) |
> | Time | `21:30` |
> | Timezone | `Asia/Kolkata` |
>
> Schedule it?

On confirmation, call `schedule_test_run` with `id`, `projectId`, `scheduledDate`,
`scheduledTime`, `userTimezone`, and `environment` (the name from Step 2).

---

## Step 6 — Report

On success, restate what was scheduled — including the environment and timezone, since those
are the two fields the user is most likely to have gotten wrong:

> ✅ **Nightly regression** (`TR-0007`) is scheduled for **2026-08-14 at 21:30 Asia/Kolkata** on
> **Staging**.

Don't call `wait_for_test_execution_completion` — the run executes later, so there is nothing
to wait on now.

---

## Error handling

| Error | Action |
|-------|--------|
| No test run matches | Say so, list near matches, stop. |
| Multiple test runs match | Show the list, ask which one. |
| `get_environments_assigned_to_user` returns `[]` | Stop — nothing valid to schedule against. Tell the user to get an environment assigned. |
| User names an environment not in the returned list | Don't pass it through. Show the valid list and ask them to pick from it. |
| Failed to retrieve test run configuration | The run has no run config yet. Tell the user to open and save it once in the platform, then retry. |
| Backend rejects the date/time | Surface verbatim, then re-check format: `YYYY-MM-DD`, 24-hour `HH:mm`, IANA timezone. |
| Scheduled time is in the past | Don't call the tool. Ask for a future time. |
