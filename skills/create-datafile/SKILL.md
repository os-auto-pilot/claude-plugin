---
name: create-datafile
description: Generate a CSV data file (columns auto-detected from a Swagger endpoint's request schema, with manual override) and upload it to the platform's data-files store. Standalone — use whenever the user wants a CSV data file created and uploaded, not only as a step of performance test case generation. See performance-testing for how uploaded files get referenced in test case steps.
---

# Create a Data File

Generate a CSV, validate it, and upload it via the `upload_datafile` MCP tool. Fully
standalone — the user may just want a data file, with no test case involved.

> **File location:** write the generated CSV to the **current working directory** (the
> folder the user launched Claude from), never the plugin directory.

## Step 1 — Determine columns

Ask (or infer from context) which of these applies:

- **Swagger-driven** (default when a spec/endpoint is available): if `swagger-spec.endpoints.json`
  doesn't already exist in the cwd, fetch it first —
  `python skills/analyze-requirements/scripts/fetch_swagger.py "<url>" --output swagger-spec.json`
  (reuse this existing script, don't duplicate its logic). Then identify the target endpoint's
  `method`/`path` from that file.
- **Manual**: ask the user for exact column names (and, if they care about realistic typed data
  rather than generic strings, the type/enum for each — see `--add` below).
- **Both**: swagger-driven columns as the base, with the user free to add/remove/override before
  generating.

## Step 2 — Generate the CSV

**Ask the user how many rows / sets of data to generate before running the script** — don't
assume or silently default a row count; it directly determines how many virtual users a
performance test iterates over (or, for a standalone CSV, simply how many rows exist).

Run the bundled script:
```
python skills/create-datafile/scripts/generate_csv.py \
  --endpoints swagger-spec.endpoints.json --method POST --path /api/orders \
  --rows <N> --output <name>.csv \
  [--columns "col1,col2,..."] [--add "name:type[:enumval1,enumval2,...]"] [--remove "col3"] \
  [--seed 42]
```
- Omit `--endpoints`/`--method`/`--path` entirely for pure manual mode (columns come only from
  `--columns`/`--add`).
- `--columns` **replaces** the auto-detected set entirely (still picks up real constraints for
  any name that matches an auto-detected column); `--add` appends a column
  (`name:type[:enumval1,enumval2,...]`, e.g. `region:enum:us,eu,apac`); `--remove` drops named
  columns. Applied in that order.
- `--seed` for reproducible output across re-runs.
- The script prints a one-line stderr summary (rows/columns written, and any columns it couldn't
  confidently synthesize — e.g. a `pattern`-constrained field just gets a generic string and is
  called out for manual review). Read this before proceeding.

## Step 3 — Validate before uploading — CRITICAL, do not skip

The script only *generates*; it does not validate its own output. Read the CSV back and check:
1. Header row matches the requested/expected column list exactly (names and order).
2. Row count matches what was requested.
3. No empty cells in any column the endpoint's spec marks `required: true`.
4. Spot-check plausibility per column: `format: email` values contain `@`; enum values are all
   members of the declared enum; numeric values fall within any `minimum`/`maximum`; string
   values respect `maxLength`.
5. No duplicate header names.
6. Anything the script flagged for manual review (e.g. a `pattern` constraint) — check by eye
   whether the generated values would actually satisfy it; regenerate with a narrower `--add`
   type or hand-edit the CSV if not.

**Do not upload if any check fails** — report the discrepancy and either re-run the script with
corrected args or hand-edit the CSV first.

## Step 4 — Upload

1. Resolve the uploader's display name once: call `get_user_details_by_id_or_email_or_unique_key`
   and use **`empName`** from the response — never an email, never a UUID (same convention as
   `created_by` elsewhere in this plugin).
2. Pick a `file_name` that is a **bare identifier: letters, numbers, underscores, and hyphens
   only, no extension, no dots, no spaces, ≤20 characters** — all server-enforced (confirmed
   against a live upload: a name like `ord_load1.csv` is rejected outright with *"File name must
   contain only letters, numbers, underscores, and hyphens... to be usable as
   `{{data.<name>.<column>}}`"*). This exact string is the `<name>` token
   `{{data.<name>.<column>}}` placeholders use later — do not add `.csv` or any other suffix.
   `ord_load1` (9 chars) is correct; `ord_load1.csv` or `orders load data` are both rejected.
   Also note: file names must be unique per project — a second upload with an already-used name
   is rejected too. Check this *before* generating the CSV in Step 2; if a user-suggested name
   doesn't fit the pattern or is too long, propose a valid alternative and confirm it rather than
   silently mangling it.
3. Call `upload_datafile` with `file_path` (from Step 2), `file_name`, `uploaded_by` (from
   sub-step 1), and `project_id` (plugin default unless the user specifies otherwise).
4. Report the returned `id`, `fileName`, and `fileSize` back to the user. This `id` is what a
   test case's `file_ids` list references (see `performance-testing`); `fileName` itself (used
   exactly as registered, no extension) is the `<file>` token `{{data.<file>.<column>}}`
   placeholders use in step bodies.

## Error handling

- **400 on upload, "File name must contain only letters, numbers, underscores, and hyphens"** —
  `file_name` has a dot, space, or other disallowed character (often from including `.csv`) —
  strip it to a bare identifier. Confirmed live; `upload_datafile`'s Pydantic model now rejects
  this client-side before it even reaches the network.
- **400 on upload, "FileName Already Use In This Project"** — the name is already taken; pick a
  different one (or bump a suffix) rather than retrying the same name.
- **Other 400 on upload** — check the `uploaded_by` value isn't an email/UUID, and that
  `file_name` is genuinely ≤20 characters.
- **401/403** — same as every other tool in this plugin: missing/expired API key, or the key
  lacks the required scope.
