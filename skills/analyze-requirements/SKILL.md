---
name: analyze-requirements
description: Analyze a requirement document, codebase, or Swagger/OpenAPI spec and generate structured manual test cases. Web locators from codebase, Playwright recordings, or Playwright MCP. Mobile locators are Appium/Selenium xpath only; without a mobile recording or codebase, persist selector as the literal string selector — never Playwright JSON.
---

# Analyze Requirements → Generate Manual Test Cases

You are the test case author. Analyze the provided input and produce structured
manual test cases in the standard Oniesoft template.

> **IMPORTANT — Output file location:** Always write ALL output files (`test-cases-*.md`, `test-coverage.md`, `swagger-spec.json`, etc.) to the **current working directory** — the folder the user launched Claude from. Never write files into the plugin directory or the skill's own folder. Use plain filenames (no path prefix) so they land in the cwd automatically.

Before authoring anything that will be persisted (utils via `save_claude_utils`, test cases via `save_claude_test_cases`), resolve the current user's **display name** with `get_user_details_by_id_or_email_or_unique_key` and use **`empName` from the response** — never the email, never a UUID — for the `userName` (utils) / `created_by` (test cases) field. See `skills/push-to-autopilot/SKILL.md` → "Known backend quirks" for why this matters and what happens if you get it wrong.

## Hard rules — test mode vs locators

**Decide `test_mode` before writing any Element Info, locator JSON, or Phase 2 handoff.** If the user has not already said web / API / mobile (native Android/iOS), ask once and wait.

| Mode | Allowed locators | Playwright MCP | Playwright `locator_spec` JSON |
|------|------------------|----------------|--------------------------------|
| **web** | Playwright locators / CSS / XPath | Allowed in Phase 2 when there is no codebase/recording | Allowed (from recordings) |
| **api** | None (no Element Info) | Never | Never |
| **mobile** | Appium / Selenium only: accessibility id, resource-id, Appium XPath | **Never** | **Never** |

**Requirements-only (no recording, no codebase) — STOP and ask first.** Do not invent locators.

> I only have the requirements document — no recordings and no codebase. Element locators will be incomplete unless you share one of:
> - A recording (web: Playwright `.spec.ts` / `.spec.js`; mobile: Appium or Selenium)
> - A codebase path (web frontend, or native mobile / React Native / Flutter)
>
> How should I proceed?
> - Share recordings and/or a codebase (best locators)
> - Continue from requirements only

Then wait. If the user continues from requirements only:

- **Web:** generate test cases with Element Info cells as `—`. Phase 2 **may** use Playwright MCP against a live URL to fill locators. Do not invent Playwright JSON in Phase 1.
- **Mobile:** generate test cases **without real locators**. For every `el:` element, put the **literal string** `selector` in **both** the CSS Selector and XPath columns (and Accessibility ID if that column is used). Do **not** guess CSS, XPath, `getByRole`, or `locator_spec` JSON. Skip Playwright MCP and skip browser-based Phase 2. Phase 3 must send `"css_selector": "selector"` and `"xpath": "selector"`.

**Mobile with a recording or codebase:** copy Appium/Selenium locators only (xpath / accessibility id / resource-id). Never transcribe them into Playwright `{"steps":[{"method":"get_by_role",...}]}` JSON.

Write `<!-- TEST-MODE: web|api|mobile -->` at the top of every generated `test-cases-*.md`.

## Step 1 — Intake: requirement doc / Swagger / codebase

Ask for **test mode** (if unknown) and the **primary source** in a single message — do not ask for recordings yet:

> **Test type** (required): web, API, or native mobile?
>
> **Please share your primary source (provide at least one):**
>
> - Requirements / feature document
> - Swagger / OpenAPI spec URL or file
> - Codebase path (web frontend/backend, native mobile, or full-stack)
> - HAR file — optional, adds backend error message accuracy

After the user provides this, proceed to **Step 1b**.

## Step 1b — Detect Codebase Type (if codebase provided)

If a codebase was provided, classify it by inspecting file extensions, directory names, and key imports:

| Signals | Classification | Test type to generate |
|---|---|---|
| `.tsx`, `.jsx`, `.vue`, `.svelte`, `components/`, `pages/`, HTML templates (browser UI) | **Frontend** | Web test cases |
| `controllers/`, `routes/`, `views.py`, `serializers.py`, `schema.prisma`, `models/`, REST/GraphQL handlers, `app.py`, `main.py` (FastAPI/Flask) | **Backend** | API test cases |
| Both frontend and backend signals present | **Full-stack** | Web + API |
| Android `res/layout`, `android:id`, Kotlin/Java Activities, iOS storyboards, `accessibilityIdentifier`, Appium tests, React Native / Flutter **native app** screens | **Native mobile** | Mobile test cases |

This classification determines test type for everything that follows:
- Frontend / Full-stack **web** codebase → Web test cases; do **not** ask for Playwright recordings
- Native mobile codebase → Mobile test cases; do **not** ask for Playwright recordings; extract Appium/Selenium locators (Branch M)
- Backend codebase → API test cases only; skip Phase 2 (element-discoverer) entirely
- User explicitly asked for **mobile** but the codebase is a **web** frontend → still `test_mode=mobile` only if they insist; do **not** copy Playwright locators into mobile elements. Ask for a mobile recording/codebase, otherwise use literal `selector`.

If a matching codebase was provided, proceed directly to **Step 2**.

## Step 1c — Identify flows and collect recordings

**MANDATORY for Web and Mobile when no matching codebase was provided — do not skip, do not proceed to Step 2 until this step is complete.**

**Skip this step when:**
- A frontend or full-stack **web** codebase was provided (web element identifiers already exist)
- A **native mobile** codebase was provided (Appium/Selenium identifiers already exist)
- Test mode is **API** (no UI elements)

If no matching codebase was provided, scan the requirement doc / Swagger for distinct user flows, then ask **mode-specific** recordings. **Never ask a mobile user for Playwright recordings. Never apply Branch R (Playwright JSON) to mobile.**

**Web — ask:**

> I found these flows in the requirements:
> - *(list all flows)*
>
> For each flow, Playwright recordings (positive + negative) improve element names, validation messages, and test data.
>
> Please share what you have:
> - Positive recording (`.spec.ts` / `.spec.js`)
> - Negative recording
> - Codebase path
> - Or continue from requirements only (Phase 2 can use Playwright MCP on a live URL)

**Mobile — ask:**

> I found these flows in the requirements:
> - *(list all flows)*
>
> For each flow, Appium or Selenium recordings (or a native app codebase) are required for real locators. Playwright locators and Playwright MCP are **not** valid for mobile.
>
> Please share what you have:
> - Appium/Selenium recording (Java/Python/JS) or inspector dump with xpath / accessibility id / resource-id
> - Native mobile / React Native / Flutter codebase
> - Or continue from requirements only — elements will be created with selector value **`selector`** (no guessed locators)

**STOP. Wait for the user's response. Do NOT generate test cases yet.**

Map what was provided, then proceed to **Step 2**:

| Flow | Positive recording | Negative recording | Source |
|---|---|---|---|
| Create Client | `client_creation_positive.ts` | `client_creation_negative.ts` | Recording |
| Delete Client | — | — | Requirements only |

## Step 2 — Scope check

Before generating, scan the input and list all modules and features detected.
If there are more than 3 modules or 10+ features, **ask the user**:
> "I found these modules: [list]. Which ones should I cover first?"

Generate only for the selected scope. Track coverage in
`test-coverage.md` (create or update it in the working directory):

```markdown
# Test Coverage Tracker
| Module | Feature | Status | File | Date |
|--------|---------|--------|------|------|
| Auth | Login | Done | test-cases-auth-login.md | 2026-06-22 |
| Auth | Register | Pending | — | — |
```

## Step 2b — Resolve existing utils

Before generating test cases, check whether the user named any existing utils in their prompt (by util name or unique key, e.g. "use the login util" or "Util-00123").

For each mentioned util, call `fetch_util_details` with the name or unique key as the `query` parameter to retrieve its UUID. Use that UUID directly in test case steps — do not create a new util for it.

Also call `fetch_util_details` for the relevant module/feature to discover any other utils already in the project that could be reused instead of recreated.

## Step 2c — Load autopilot step templates

Before any extraction, call `get_autopilot_steps` with the relevant `test_mode` (`web`, `api`, or `mobile`). For full-stack **web+API** projects call it twice — once for `web` and once for `api`. For native mobile call it once with `mobile` — do not also load `web` step templates for a mobile file.

Use the returned `step` templates as the **only valid autopilot syntax** when writing steps in Step 3. Do not invent steps outside this list.

## Step 2d — Parallel Extraction

Run all applicable branches **simultaneously** (they are independent). Each branch produces inputs used in Step 3 test case generation.

---

### Branch S — Swagger / OpenAPI spec provided

**If the user gives a URL** (not a local file), fetch the spec using the provided script — do NOT use Playwright or a browser:

```
python skills/analyze-requirements/scripts/fetch_swagger.py "<url>" --output swagger-spec.json
```

If a bearer token is needed: add `--token "<token>"`.

The script handles Swagger UI HTML pages, JSON specs, and YAML specs automatically. It resolves the real spec URL from the UI page and falls back to common paths (`/openapi.json`, `/api-docs`, etc.) if needed. It also writes a companion **`swagger-spec.endpoints.json`** — one flattened entry per `(method, path)` operation with that endpoint's request `content_types`, `request_fields` (file-upload fields pre-flagged with `"is_file": true`), path/query/header parameters, `auth`, and `responses`. **Read `swagger-spec.endpoints.json` first** — it is the authoritative, pre-extracted source for exactly the per-endpoint facts below (especially content-type and file fields); fall back to reading `swagger-spec.json` directly only for anything the summary doesn't cover.

**If the user gives a local file** (`.json` / `.yaml` / `.yml`), read it directly — no script needed. There is no pre-built endpoints summary in this case, so extract the fields below by hand from the spec, endpoint by endpoint.

Extract directly from the spec (or from `swagger-spec.endpoints.json` when available) — no recordings needed, no codebase grep needed for constraints:

- Field names, types, `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `enum`, `required`
- Field descriptions (often contain business rules)
- `example` / `examples` values → use as +Ve test data
- `4xx` response schemas → extract error message text and field-error mapping
- **Request content-type per endpoint** — `content_types` in the summary (or `consumes` / `requestBody.content` keys read directly from the spec). Record it alongside the endpoint so Step 3 picks the right body step(s): `with body` for `application/json`, or `with form data` + `with file params` for `multipart/form-data` — see "For API test cases" below. Do this **per endpoint** — a spec can mix both.
- **File-upload fields per endpoint** — fields flagged `"is_file": true` in the summary (or, reading the spec directly: OpenAPI 3.x properties with `type: string, format: binary`, or Swagger 2.0 params with `in: formData, type: file`). These need the `with file params` step, not `with form data`.

Produces: **Validation Schema Map**

```
Validation Schema Map:
  Field: email
    required: true, format: email
    errors: { invalid: "Invalid email format" }   ← from 4xx response schema
  Field: password
    required: true, minlength: 8, maxlength: 128
    errors: { too_short: "Password must be at least 8 characters" }
```

Web test cases from Swagger still need element discovery in Phase 2 unless a frontend codebase is also provided. API test cases from Swagger need no Phase 2.

---

### Branch FE — Frontend codebase provided (Web only)

**Do not use this branch for native mobile.** Web HTML/CSS/Playwright attributes (`data-testid`, CSS, Playwright JSON) must never be copied onto `test_mode=mobile` elements.

Extract BOTH element identifiers AND validation constraints in one pass. No recordings needed. No browser launch needed.

**FE-1: Extract element identifiers**

Grep all component files (`**/*.tsx`, `**/*.jsx`, `**/*.vue`, `**/*.svelte`, `**/*.html`) for:

| Attribute / Pattern | Element type | `el:` name suffix |
|---|---|---|
| `data-testid="x"` | any | from testid value + context |
| `id="x"` on `<input>` or `<textarea>` | textbox | `_textbox` |
| `name="x"` on `<input>` | textbox | `_textbox` |
| `type="email"` on `<input>` | email field | `_textbox` |
| `type="checkbox"` | checkbox | `_checkbox` |
| `<select name="x">` | dropdown | `_dropdown` |
| `<button>text</button>` or `role="button"` | button | `_button` |
| `aria-label="x"` | any | from label + context |
| `role="alert"`, `.error`, `.field-error`, `.validation-message` | error container | `_error_label` |
| Form-level error: `.form-error`, `.alert-danger`, `role="alert"` with no field scope | error banner | `el:form_error_banner` |

Build an **Element Map**:
```
Element Map:
  el:email_textbox      → css: input[name="email"]           xpath: //input[@name='email']
  el:password_textbox   → css: input[type="password"]        xpath: //input[@type='password']
  el:login_button       → css: button[type="submit"]         xpath: //button[@type='submit']
  el:email_error_label  → css: [data-testid="email-error"]   xpath: //*[@data-testid='email-error']
  el:form_error_banner  → css: .form-error-banner            xpath: //*[contains(@class,'form-error-banner')]
```

If a `data-testid` is dynamic (e.g., `data-testid={field.id}`), note it:
```
el:username_textbox → <!-- DYNAMIC-TESTID: generated at runtime — verify selector --> css: input[name="username"]
```

**FE-2: Extract validation constraints**

Grep for validation schemas imported by or adjacent to the component files:

| Framework | Patterns to search |
|---|---|
| Zod | `z.object(`, `.min(`, `.max(`, `.email()`, `.regex(`, `.refine(` |
| Yup | `yup.object(`, `.required(`, `.min(`, `.max(`, `.matches(` |
| class-validator | `@IsEmail()`, `@MinLength(`, `@MaxLength(`, `@IsNotEmpty(`, `@Matches(` |
| Pydantic | `Field(min_length=`, `Field(max_length=`, `field_validator`, `@validator` |
| Django | `max_length=`, `MinLengthValidator`, `RegexValidator` |
| HTML attributes | `required`, `maxlength=`, `minlength=`, `pattern=` |

Also grep for error message strings: `errors.ts`, `messages.ts`, `constants.ts`, `i18n/*.json`, `locales/*.json`.

Produces: **Element Map** + **Validation Schema Map**

Write the Element Map as an `<!-- ELEMENT-MAP -->` comment block at the top of each generated `test-cases-*.md` file. Phase 2 reads this to fill Element Info tables without launching a browser.

```markdown
<!-- ELEMENT-MAP
source: frontend-codebase
elements:
  - name: email_textbox, css: input[name="email"], xpath: //input[@name='email']
  - name: password_textbox, css: input[type="password"], xpath: //input[@type='password']
  - name: login_button, css: button[type="submit"], xpath: //button[@type='submit']
  - name: email_error_label, css: [data-testid="email-error"], xpath: //*[@data-testid='email-error']
-->
```

---

### Branch BE — Backend codebase provided

Extract API test case information:
- Route definitions: HTTP method (GET/POST/PUT/DELETE/PATCH), path, handler
- Request body schemas: field names, types, required fields, validation rules
- Response schemas: success structure, error structure with error messages and status codes
- Auth requirements: Bearer token, API key, session cookie

Produces: **API Schema Map** for API test case generation. No Element Map. No Phase 2.

---

### Branch M — Native mobile codebase or Appium/Selenium recording (Mobile only)

Use this branch when `test_mode` is **mobile** and a native codebase or Appium/Selenium recording was provided.

**Forbidden:** Playwright `page.getByRole` / `getByText` / `locator_spec` JSON, Playwright MCP, CSS selectors invented from a web DOM.

Extract locators in this priority (store the real string, not JSON):

| Source | Store as |
|---|---|
| `accessibility id` / `accessibilityIdentifier` / `content-desc` | accessibility id; also Appium XPath `//*[@content-desc='…']` or `//*[@name='…']` when needed |
| Android `resource-id` / `android:id` | id; XPath `//*[@resource-id='…']` |
| Explicit Appium/Selenium `By.xpath` / `AppiumBy.XPATH` | that XPath verbatim |
| React Native `testID` / Flutter `Key` in a **mobile** codebase | Appium xpath/`~` accessibility as appropriate — still not Playwright JSON |

Write `<!-- ELEMENT-MAP source: mobile-codebase-or-recording -->` with **xpath** (and optional accessibility id) only.

Element Info table for mobile (no Playwright column):

```markdown
| Element | Accessibility ID | Appium/Selenium XPath |
|---------|------------------|-----------------------|
| email_textbox | login_email | //*[@resource-id='com.app:id/email'] |
```

On push, put the Appium/Selenium XPath in **both** `css_selector` and `xpath` (or accessibility id in `css_selector` and xpath in `xpath`). Never a Playwright JSON object.

### Branch R — Playwright recordings provided (Web only — never mobile)

Only use this branch when `test_mode` is **web** and no frontend codebase was provided (requirements doc or Swagger as the sole source for a Web feature). **If test mode is mobile, skip this entire branch** even if a `.spec.ts` file is sitting in the workspace.

Read the full recording file(s) and use LLM analysis to extract every element — do NOT use a fixed pattern table. Every `page.*` and `expect(page.*)` call must produce an element entry. Nothing is skipped.

For each line, understand the intent: what element is being interacted with, what action is performed, and what data is used. Use that understanding to assign an `el:` name and preserve the exact Playwright locator.

**Locator encoding — transcribe, do not guess.** The backend can execute a JSON locator spec that preserves the *original* Playwright locator call instead of translating it into CSS/XPath. For any locator matching the Playwright strategies below, transcribe it mechanically into this JSON shape — this is a syntax mapping (JS/TS call → JSON), not a semantic guess, so it needs no DOM access and carries no ambiguity:

```json
{"steps": [{"method": "<python_method_name>", "args": [...], "kwargs": {...}}]}
```

Chained calls (`.filter()`, `.and()`, `.or()`, `.first`, `.last`, `.nth()`, `.frameLocator()`) become successive entries in the `steps` array, in the same order as the recording. A `has`/`has_not` filter value, or an `and`/`or` argument, that is itself another locator becomes a nested `{"steps": [...]}` object in that position.

**Transcription table** (JS/TS recording syntax → JSON `method` + arg mapping):

| Recording call | JSON `method` | args / kwargs |
|---|---|---|
| `getByRole(role, {name, exact})` | `get_by_role` | `args: [role]`, `kwargs: {name, exact}` |
| `getByLabel(text, {exact})` | `get_by_label` | `args: [text]`, `kwargs: {exact}` |
| `getByText(text, {exact})` | `get_by_text` | `args: [text]`, `kwargs: {exact}` |
| `getByTestId(id)` | `get_by_test_id` | `args: [id]` (no `exact` — not supported by this method) |
| `getByPlaceholder(text, {exact})` | `get_by_placeholder` | `args: [text]`, `kwargs: {exact}` |
| `getByAltText(text, {exact})` | `get_by_alt_text` | `args: [text]`, `kwargs: {exact}` |
| `getByTitle(text, {exact})` | `get_by_title` | `args: [text]`, `kwargs: {exact}` |
| `locator(cssOrXPath)` | `locator` | `args: [cssOrXPath]` |
| `.filter({hasText, has, hasNot, hasNotText})` | `filter` | `kwargs: {has_text, has, has_not, has_not_text}` — `has`/`has_not` may be a nested `{"steps": [...]}` |
| `.and(x)` | `and_` | `args: [x as nested {"steps": [...]}]` |
| `.or(x)` | `or_` | `args: [x as nested {"steps": [...]}]` |
| `.nth(n)` | `nth` | `args: [n]` |
| `.first` | `first` | no args (it's a property, not a call) |
| `.last` | `last` | no args (property) |
| `.frameLocator(selector)` | `frame_locator` | `args: [selector]` |
| `.contentFrame()` | `content_frame` | no args (property) |

Example — the OTP-style case that motivated this: `page.getByRole('textbox', { name: 'Enter 6-digit OTP' })` becomes
`{"steps": [{"method": "get_by_role", "args": ["textbox"], "kwargs": {"name": "Enter 6-digit OTP"}}]}` — Playwright resolves the real accessible name at test-run time (via the label, `aria-label`, or whatever the actual DOM uses), so there's nothing to guess or get wrong here.

**If a locator doesn't map onto this table at all** (e.g. a recording using raw `page.evaluate(...)` custom JS, or a locator string that's genuinely just descriptive text with no real Playwright call behind it) — fall back to a plain CSS/XPath guess as before, and flag it clearly: `<!-- LOCATOR-UNVERIFIED: no direct locator-spec equivalent, derived from recording text only -->`. This should now be rare — everything else above transcribes deterministically.

**Naming convention** — `snake_case` + type suffix:

| Element type | Suffix | Example |
|---|---|---|
| Text input, textarea | `_textbox` | `el:email_textbox` |
| Button (action) | `_button` | `el:sign_in_button` |
| Dropdown container | `_dropdown` | `el:salutation_dropdown` |
| Option inside a dropdown | `_option` | `el:mr_option`, `el:andhra_pradesh_option` |
| Link / nav item | `_link` | `el:clients_link` |
| Heading / title | `_heading` | `el:client_name_heading` |
| Checkbox | `_checkbox` | `el:terms_checkbox` |
| Image | `_image` | `el:logo_image` |
| Field-level error | `_error_label` | `el:email_error_label` |
| Form-level error | `form_error_banner` | `el:form_error_banner` |

**Key rules:**
- Multiple `.click()` then `.fill()` calls on the same locator → one element entry; use the `.fill()` value as the +Ve example
- `.press('Tab')` or `.press('Enter')` → add as a note on the existing element; do not create a new entry
- `getByText('X').click()` immediately after a dropdown open step → this is a dropdown option; name it `el:<snake_case_X>_option`
- `expect(...).toContainText('X')` or `.toHaveText('X')` → extract element + record expected text X
- Elements only visible after form submission (e.g. success heading) → extract and mark as `<!-- POST-SUBMIT -->`

**From the negative recording** — apply the same full extraction, and additionally record:
- Exact error message text visible in the UI → use verbatim in -Ve test case `check text of` assertions
- Which field triggered which error

**Build a merged Recording Map** — one entry per unique element across both recordings:

```
Recording Map:
  el:email_textbox           → playwright: page.getByRole('textbox', {name:'email@example.com'}) | locator_spec: {"steps":[{"method":"get_by_role","args":["textbox"],"kwargs":{"name":"email@example.com"}}]} | +Ve: testuser@yopmail.com
  el:sign_in_button          → playwright: page.getByRole('button', {name:'Sign In'})             | locator_spec: {"steps":[{"method":"get_by_role","args":["button"],"kwargs":{"name":"Sign In"}}]}
  el:salutation_dropdown     → playwright: page.getByRole('button', {name:'Select salutation'})   | locator_spec: {"steps":[{"method":"get_by_role","args":["button"],"kwargs":{"name":"Select salutation"}}]}
  el:mr_option               → playwright: page.getByText('Mr.')                                  | locator_spec: {"steps":[{"method":"get_by_text","args":["Mr."]}]}
  el:state_dropdown          → playwright: page.getByRole('button', {name:'Select state',exact:true}) | locator_spec: {"steps":[{"method":"get_by_role","args":["button"],"kwargs":{"name":"Select state","exact":true}}]}
  el:andhra_pradesh_option   → playwright: page.getByText('Andhra Pradesh')                       | locator_spec: {"steps":[{"method":"get_by_text","args":["Andhra Pradesh"]}]}
  el:client_name_heading     → playwright: page.locator('h1')                                     | locator_spec: {"steps":[{"method":"locator","args":["h1"]}]} | expected text: "Test User" <!-- POST-SUBMIT -->
  el:email_error_label       → playwright: page.getByText('Email is required')                    | locator_spec: {"steps":[{"method":"get_by_text","args":["Email is required"]}]} | error: "Email is required"
```

The `playwright:` column stays for human/LLM readability and debugging; `locator_spec:` is the value that actually gets stored (see `skills/push-to-autopilot/SKILL.md` for how it lands in the `elements` payload). Write as `<!-- RECORDING-MAP -->` block at the top of each generated `test-cases-*.md`. Phase 2 reads this — no browser launch needed; a `locator_spec` transcribed here is already final and needs no further resolution.

---

### Branch F — Fallback (requirements doc only, no codebase, no recordings)

Mine the doc for:
- Field names and types
- Constraint language: "at least N characters" → `minlength: N`, "no more than N" → `maxlength: N`, "must be unique", "alphanumeric only"
- Quoted error messages → use verbatim where present

Flag every inferred constraint:
```markdown
<!-- CONSTRAINT-UNVERIFIED: maxlength assumed 255 for name field — verify against codebase or app -->
```

Add at the top of each generated file:
```markdown
<!-- VALIDATION-SOURCE: requirements-doc-only — constraints are inferred, not verified -->
<!-- TEST-MODE: web|mobile|api -->
```

**Web:** No Element Map. Leave Element Info locator cells as `—`. Phase 2 **may** use Playwright MCP if the user provides a live URL. Do not invent `locator_spec` JSON in Phase 1.

**Mobile — CRITICAL:** No Element Map. Do **not** run Phase 2 browser/Playwright MCP. Do **not** invent Appium xpath, CSS, or Playwright JSON. For every `el:` row, set locator cells to the literal word `selector`:

```markdown
| Element | Accessibility ID | Appium/Selenium XPath |
|---------|------------------|-----------------------|
| email_textbox | selector | selector |
| login_button | selector | selector |
```

If a Web-style three-column table is used by mistake, still put `selector` in **CSS Selector and XPath** (and `—` or `selector` in Playwright — never a JSON locator). Phase 3 must persist `"css_selector": "selector", "xpath": "selector"`.

---

### Branch V — HAR file provided (optional supplement)

Parse `4xx` responses in the HAR file. For each failed request:
- Extract request body (what invalid payload triggered the error)
- Extract response body (the actual server-side validation error messages)
- Map error messages to field names

Add these server-side error messages to the Validation Schema Map. They may differ from frontend messages — include both in -Ve test cases where relevant.

---

## Step 3 — Identify utils and generate test cases (parallel)

**Generate all markdown files in parallel — spawn one subagent per module/feature combination.** Each subagent receives:
- The Validation Schema Map (from Branch S, FE-2, BE, F, or V)
- The Element Map or Recording Map (from Branch FE or R, if available)
- The element naming convention and autopilot step format
- Its assigned output filename: `test-cases-<module>-<feature>.md`

Each subagent operates independently. After all subagents complete, collect the files and proceed to Step 4.

---

**Before writing test cases, identify reusable flows (utils).** If a setup, teardown, or action flow appears as a precondition or repeated step in 2+ test cases, extract it as a util. Check Step 2b results first — use existing util UUIDs where available.

**A util's own Autopilot Steps must never contain `execute util "<uuid>"`.** Nested/chained util calls are not supported by the autopilot backend — `execute util` is valid only inside a test case's steps. If one util's flow logically needs another util's steps (e.g. a "create order" util that would otherwise want to call a "login" util first), inline those steps directly into the util instead of referencing the other util by UUID. Keep this in mind when both extracting utils and writing their Autopilot Steps.

For each new util, write a `UTIL-NNN` section at the top of the markdown file:

```markdown
## UTIL-001: Login as Standard User
**Util Name:** login_as_standard_user
**Test Mode:** Web   *(or Mobile — never mix Playwright locators into a Mobile util)*
**Feature:** [feature name]

### Autopilot Steps
navigate to "/login"
enter "<email>" in "el:email_textbox"
enter "<password>" in "el:password_textbox"
click on "el:login_button"
check element "el:dashboard_header" is visible in the page

### Test Data
| Field    | Value            | Type |
|----------|------------------|------|
| email    | user@example.com | text |
| password | Test@123!        | text |

### Element Info *(Web: Phase 2 fills locators; Mobile without recording/codebase: use literal `selector`)*
| Element          | Playwright Locator | CSS Selector | XPath |
|------------------|--------------------|--------------|-------|
| email_textbox    | —                  | —            | —     |

For **mobile** utils, use the mobile Element Info table (Accessibility ID + Appium/Selenium XPath). Requirements-only mobile: both cells = `selector`.

**Util UUID:** *(populated after save_claude_utils call)*
```

Test cases reference a util by UUID in steps (never by name):
```
execute util "3fa85f64-5717-4562-b3fc-2c963f66afa6"
```

During Phase 1 (before `save_claude_utils` is called), use the util name as a placeholder: `execute util "login_as_standard_user"`. Replace with the real UUID once the backend returns it.

**Test data override convention**

Override is optional. Include override fields only when the requirement explicitly needs different data than the util's default.

Format: `<util-field>_i<N>_<util-uuid>` where N = invocation number.

```
| email_i1_3fa85f64-5717-4562-b3fc-2c963f66afa6    | admin@example.com | text |
| email_i2_3fa85f64-5717-4562-b3fc-2c963f66afa6    | user@example.com  | text |
| password_i1_3fa85f64-5717-4562-b3fc-2c963f66afa6 | AdminPass@1       | text |
```

---

**Test case generation rules:**

Cover all of:
- **Functional +Ve** — valid inputs, happy path, boundary-valid values
- **Functional -Ve** — invalid inputs, missing fields, wrong types, auth failures
- **Edge cases** — empty strings, max-length values, special characters, concurrent actions

**For Web test cases (+Ve):**
- Use navigation flow from the Recording Map, or infer from requirements/codebase
- Use `+Ve example` values from the Element Map / Recording Map / spec as test data
- Use `el:` names from the Element Map or Recording Map exactly as defined

**For Mobile test cases:**
- Same step syntax as web (`el:` names, enter/click/check) but `test_mode` is mobile
- Locators from Branch M only (Appium/Selenium xpath / accessibility id)
- Requirements-only: Element Info locators are the literal `selector` — never Playwright JSON, never guessed CSS/xpath
- Do not use web dropdown heuristics (`getByRole('button')`, native `<select>`) to invent mobile locators

**For Web test cases (-Ve):**
- Generate one dedicated -Ve test case per constraint in the Validation Schema Map:
  - `required: true` → TC: "Submit without [field] → verify '[field] is required'"
  - `minlength: 8` → TC: "Enter 7-char value → verify 'must be at least 8 characters'"
  - `format: email` → TC: "Enter 'notanemail' → verify 'Invalid email format'"
  - `maxlength: 50` → TC: "Enter 51-char value → verify error or truncation"
- Use **exact error message text** from the Validation Schema Map (from schema, recording, or spec) in check steps: `check text of "el:email_error_label" is "Email is required"`
- If no exact message is known, use a generic assertion and flag it: `<!-- ERROR-MESSAGE-UNVERIFIED -->`
- Fields discovered in codebase/recording but absent from requirements: flag with `<!-- FIELD-NOT-IN-REQUIREMENTS: discovered in [codebase/recording] -->`

**For API test cases:**
- Steps use autopilot API format (see format reference below)
- **Body step selection is driven by the endpoint's content-type, never assumed:** if the Validation Schema Map / API Schema Map recorded `multipart/form-data` for this endpoint, use `with form data {...}` for its non-file fields and `with file params {...}` for its file fields — do NOT use `with body {...}` for it. Use `with body {...}` only for `application/json` (the default when no content-type was recorded). Check this per endpoint, not once per file — a spec can mix JSON and multipart endpoints.
- -Ve test cases: missing required fields (→ 400), wrong types, out-of-range values, unauthorized (→ 401/403), not found (→ 404)
- No Element Info section needed for API test cases

**Naming:** Use a concise descriptive name only — do NOT prefix with TC-001 or any ID/key. The platform assigns IDs automatically.

---

**Element Info table completeness — CRITICAL:**

Every test case's (and util's) own **Element Info** table must contain a row for **every** `el:` element referenced in that section's own Test Steps / Autopilot Steps — including elements already defined in an earlier util or test case in the same file. Do not omit an element from a test case's table just because it was already resolved elsewhere in the document; repeat its row.

Phase 3 (`/push-to-autopilot`) builds each test case's `elements` payload only from that test case's own table. An `el:` reference missing from its own table will not be sent to the backend for that test case — even if the same element was fully resolved in an earlier section — and the backend cannot convert it to an element ID.

---

## Test Case Template (use exactly, every time)

```markdown
## [Concise test case name]
**Module:** [Module name]
**Feature:** [Feature name]
**Type:** Functional +Ve
**Priority:** Major
**Test Phase:** QA

### Pre-conditions
- [List what must be true before this test runs]

### Test Steps
| Step | Action | Test Data | Expected Result |
|------|--------|-----------|-----------------|
| 1    | [Action] | [Data if any] | [Expected outcome] |

### Expected Result
[Overall expected outcome in one or two sentences]

### Element Info *(Web — populated in Phase 2 unless codebase/recording already filled it)*
| Element | Playwright Locator | CSS Selector | XPath |
|---------|--------------------|--------------|-------|
| [name]  | —                  | —            | —     |

### Element Info *(Mobile — Appium/Selenium only; never Playwright JSON)*
| Element | Accessibility ID | Appium/Selenium XPath |
|---------|------------------|-----------------------|
| [name]  | selector         | selector              |

Use real accessibility id / xpath from Branch M when a mobile recording or codebase was provided. If neither was provided, keep **both** cells as the literal `selector`.

**Web + `locator_spec` (Branch R only):** put that JSON text in both the CSS Selector and XPath columns. `css_selector` is the field the backend treats as authoritative (see `skills/push-to-autopilot/SKILL.md`); `xpath` is a fallback. Do not split JSON across columns. **Never write `locator_spec` JSON for mobile.**

### API Details *(only for api test_mode)*
**Endpoint:** METHOD /path
**Request Body:**
```json
{}
```
**Expected Response:** 200 `{}`
```

### Priority guidelines
| Priority | When to use |
|----------|-------------|
| Blocker  | App cannot be used at all without this working |
| Critical | Core business flow broken |
| Major    | Important feature broken, workaround exists |
| Minor    | Cosmetic, edge case, low-impact |

## Autopilot step format

Steps must be written in autopilot format. Reference element names with the `el:` prefix exactly as named in the Element Info table.

**Web / Mobile steps:**
```
navigate to "https://app.example.com/login"
enter "test@example.com" in "el:email_textbox"
enter "<password>" in "el:password_textbox"
click on "el:login_button"
check element "el:dashboard_header" is visible in the page
check text of "el:welcome_label" is "Welcome, Admin"
check text of "el:email_error_label" is "Email is required"
select option "Admin" in "el:role_dropdown"
scroll down until "el:submit_button" is visible
```

**API steps:**
```
with bearer auth to login endpoint "/auth/login" using payload {"email": "<email>", "password": "<password>"}
with body {"name": "John", "email": "<email>"}
call post "/api/users"
check status code is 201
check "$.id" value is "<user_id>"
store the "$.id" in "created_user_id"
with path parameter "id" and "$$created_user_id"
call get "/api/users/{id}"
check status code is 200
```

**Form-data / multipart endpoints — CRITICAL:** `with body {...}` is only for `application/json` requests. If the Swagger spec records `multipart/form-data` for an endpoint (or a `swagger-spec.endpoints.json` entry flags it — see Branch S), use two separate steps instead — never `with body` for that endpoint:
- `with form data {...}` — a dict of the endpoint's non-file fields
- `with file params {...}` — a dict of `{"<field name>": "<file name>"}` for its file-upload fields (fields flagged `is_file: true` in the endpoints summary, or `type: string, format: binary` / Swagger 2.0 `in: formData, type: file` read directly from the spec)

Both steps can be used together on the same request when it has both kinds of fields; use whichever ones the endpoint actually needs.

```
✅ CORRECT — endpoint content-type is multipart/form-data, with one file field and one text field:
with form data {"description": "<description>"}
with file params {"file": "sample.pdf"}
call post "/api/documents/upload"
check status code is 201

❌ WRONG — using the JSON body step for a multipart endpoint:
with body {"file": "<file>", "description": "<description>"}
call post "/api/documents/upload"

❌ WRONG — file field put in "with form data" instead of "with file params":
with form data {"file": "<file>", "description": "<description>"}
call post "/api/documents/upload"
```

**Path parameters — CRITICAL:** Never interpolate a path value — literal, `<placeholder>`, or `$$stored_variable` — directly into the URL string. Use a dedicated path-parameter step before the `call` step, and reference the parameter by name in the URL with `{name}` curly-brace placeholders:

- One path parameter: `with path parameter "<name>" and "<value>"` — repeat this step once per parameter when there are several
- Several path parameters at once: `with path parameters {"name1": "<value1>", "name2": "<value2>"}`

```
✅ CORRECT:
with path parameter "id" and "$$created_user_id"
call get "/api/users/{id}"

with path parameters {"userId": "$$user_id", "orderId": "$$order_id"}
call get "/api/users/{userId}/orders/{orderId}"

❌ WRONG — value interpolated directly into the URL:
call get "/api/users/$$created_user_id"
call get "/api/users/123"
```

**Variable store/access rule — CRITICAL (applies to web, mobile, and API):**

Variables are stored using a plain name, but **always accessed with `$$` prefix**. No exceptions, in any test mode.

```
✅ CORRECT — store with plain name, access with $$:

# API
store the "$.csrf_token" in "csrf_token"
with headers {"x-csrf-token": "$$csrf_token"}

store the "$.id" in "user_id"
with path parameter "id" and "$$user_id"
call get "/api/users/{id}"
with body {"owner": "$$user_id", "name": "<name>"}

# Web / Mobile
store the inner text of "el:order_id_label" in "order_id"
check variable "order_id" is equal to "$$order_id"
navigate to "/orders/$$order_id"

❌ WRONG — accessing variable without $$:
with headers {"x-csrf-token": "csrf_token"}
with path parameter "id" and "user_id"
check variable "order_id" is equal to "order_id"
```

Every place a stored variable is **used** — in `with body`, `with headers`, `with query parameters`, `with path parameter(s)`, `check the expression`, `check variable`, `navigate to`, or any step that references the value — it must be prefixed with `$$`. The plain name appears only in the `store ... in "name"` step itself. Note that the URL string passed to `call get/post/put/delete` itself never carries a stored variable directly — path values always go through a `with path parameter` / `with path parameters` step and a `{name}` placeholder in the URL (see the Path parameters rule above).

---

**Dropdown / select rule — CRITICAL:**

There are two types of dropdowns and they need different steps:

**Native `<select>` tag** → use `select option` (single step):
```
select option "Admin" in "el:role_dropdown"
```

**Custom dropdown (built with `<button>`, `<div>`, `<li>` etc.)** → two click steps, but BOTH must have `el:` prefix. The option click must also be an element:
```
✅ CORRECT:
click on "el:salutation_dropdown"
click on "el:mr_option"

click on "el:state_dropdown"
click on "el:andhra_pradesh_option"

❌ WRONG — bare text without el: means the element is never created by the backend:
click on "el:salutation_dropdown"
click on "Mr."
```

How to tell which type: if the Element Info table shows `getByRole('button')` or `getByRole('combobox')` or a CSS selector with `button`/`div`/`li` for the dropdown — it is a custom dropdown, use two `click on "el:..."` steps. If the CSS selector shows `select` tag — use `select option`.

**Every value inside `click on "..."` MUST have `el:` prefix** — no exceptions. If it is an option inside a custom dropdown, give it an `el:` name (e.g. `el:mr_option`, `el:andhra_pradesh_option`) and add it to the Element Info table.

**Element name rules:**
- Use `el:` prefix in steps: `el:email_textbox`, `el:login_button`
- Include element type in name: `textbox`, `button`, `link`, `dropdown`, `checkbox`, `label`, `option`
- Dropdown options: name as `el:<value>_option` e.g. `el:mr_option`, `el:passport_option`, `el:andhra_pradesh_option`
- Error message containers: `el:fieldname_error_label` (field-level), `el:form_error_banner` (form-level)
- Use `<placeholder>` for test data that varies: `"<email>"`, `"<password>"`
- Use literal strings for fixed values: `"Admin"`, `"https://..."`, `200`

## Step 4 — After generating

1. Update `test-coverage.md` with the newly covered modules/features.
2. Tell the user:
   - How many utils were identified (if any) and their names
   - How many test cases were created (total, +Ve count, -Ve count)
   - The filename(s) written
   - Which modules/features are still pending (from the tracker)
   - Which input path was used (codebase / Swagger / recordings / fallback)
3. If utils were identified, ask: *"I identified N reusable utils: [list names]. Shall I save them to the platform now so test cases can use their real UUIDs?"*
   - If yes → call `save_claude_utils`, fill in **Util UUID** in the markdown, replace all `execute util "util_name"` placeholders with the real UUIDs returned
   - If no → leave the util name placeholders; Phase 3 (`/push-to-autopilot`) will handle this before pushing
4. Phase 2 handoff:
   - **Backend-only / API test cases** → skip Phase 2 entirely. Ask: *"Shall I push these API test cases to the platform now?"*
   - **Mobile test cases with no codebase and no Appium/Selenium recording** → skip Phase 2 entirely. Locators are already the literal `selector`. Ask: *"Shall I push these mobile test cases to the platform now? Elements will be created with selector value `selector` until you provide a recording or codebase."* Never launch Playwright MCP for mobile.
   - **Mobile test cases with native codebase or Appium/Selenium recording** → Element Map is Appium/Selenium xpath only. Ask: *"Shall I proceed to Phase 2 to copy Appium/Selenium locators into the Element Info tables? (No browser / no Playwright.)"*
   - **Web test cases with frontend codebase** → Element Map was already written to the markdown. Ask: *"Element locators have been extracted from the codebase and written to the markdown. Shall I proceed to Phase 2 to fill in the Element Info tables? (This step is fast — no browser needed)"*
   - **Web test cases with Playwright recordings** → Recording Map already written. Ask same as above.
   - **Web test cases with no codebase / no recordings** → Ask: *"Shall I proceed to Phase 2 to discover element locators with Playwright MCP? (A live app URL will be needed.)"*
   - If user proceeds (and Phase 2 is allowed for this mode) → hand off to the `element-discoverer` subagent with the filename(s)
     - Element discovery order: util sections first, then test case sections
     - Pass `test_mode` explicitly so the discoverer does not treat mobile files as web
