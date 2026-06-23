"""MCP tool definitions for the Oniesoft test platform.

Each tool is a thin, typed wrapper over a backend REST endpoint. Tools fill in
the project/user defaults from the environment when the caller omits them, so
the model can call them with minimal arguments.
"""

from __future__ import annotations

from typing import Any
import uuid

from mcp.server.fastmcp import FastMCP

from server.request_response_model import FeatureCreationInput, FeatureCreationOutput, ModuleIdByNameOrUniqueKeyInput

from . import client

mcp = FastMCP("oniesoft-test-platform")


def _project(project_id: str | None) -> str:
    pid = project_id or client.DEFAULT_PROJECT_ID
    if not pid:
        raise ValueError(
            "No project_id given and no default configured. Pass project_id or set "
            "default_project_id in the plugin config."
        )
    return pid


def _user(user_id: str | None) -> str | None:
    return user_id or client.DEFAULT_USER_ID


# --------------------------------------------------------------- generation ----
@mcp.tool()
async def create_test_cases(
    user_input: str,
    module: str,
    feature: str,
    test_mode: str = "web",
    project_id: str | None = None,
    user_prompt: str = "",
    browser_type: str = "Chrome",
    platform: str = "",
    env_id: str = "",
    apk_id: str = "",
    severity: str = "Minor",
) -> dict[str, Any]:
    """Generate and persist test cases from a natural-language description.

    test_mode is one of: "web" (UI), "api" (HTTP/REST), or "mobile" (native
    Android/iOS). The backend routes web/mobile through the UI pipeline and api
    through the API pipeline, then stores the resulting test cases in the project.

    Returns the created test case ids and counts.
    """
    payload = {
        "user_input": user_input,
        "module": module,
        "feature": feature,
        "testMode": test_mode,
        "projectId": _project(project_id),
        "createdBy": _user(None) or "claude-code",
        "userId": _user(None) or "",
        "user_prompt": user_prompt,
        "browserType": browser_type,
        "platform": platform,
        "envId": env_id,
        "apkId": apk_id,
        "severity": severity,
    }
    return await client.post_platform("/api/test-cases/create", payload)


@mcp.tool()
async def analyze_test_steps(
    user_input: str,
    module: str,
    feature: str,
    test_mode: str = "web",
    project_id: str | None = None,
) -> dict[str, Any]:
    """Analyze a description and return the selected test steps + elements + test
    data WITHOUT persisting a full test case. Useful to preview what would be
    generated before committing.
    """
    payload = {
        "user_input": user_input,
        "module": module,
        "feature": feature,
        "testMode": test_mode,
        "projectId": _project(project_id),
        "createdBy": _user(None) or "claude-code",
    }
    return await client.post_platform("/api/analyze", payload)


@mcp.tool()
async def save_claude_test_cases(
    test_cases: list[dict],
    module: str,
    feature: str,
    feature_id: str,
    test_mode: str = "web",
    project_id: str | None = None,
    user_id: str | None = None,
    browser_type: str = "Chrome",
    platform: str = "",
    env_id: str = "",
    apk_id: str = "",
) -> dict[str, Any]:
    """Persist test cases that Claude authored in Phase 1/2 — NO LLM re-analysis.

    Use this (not create_test_cases) after /analyze-requirements + element-discoverer
    have produced fully structured test cases. The backend only creates elements with
    real selectors and validates step syntax; it does NOT re-interpret the content.

    Each item in test_cases must have:
      name        (str)  — test case name, e.g. "TC-001: Login with valid creds"
      description (str)  — short description (max 600 chars)
      type        (str)  — "Functional +Ve" | "Functional -Ve"
      priority    (str)  — "Minor" | "Major" | "Blocker" | "Critical"
      test_phase  (str)  — default "QA"
      steps       (list) — autopilot-format step strings (see SKILL.md format guide)
      elements    (list) — [{name, css_selector, xpath}]  (css_selector preferred)
      test_data   (list) — [{field, value, type}]  (type is usually "text")

    feature_id is the UUID of the feature in the autopilot backend (needed to
    create/look up elements). Get it from the project config or the UI.

    Returns the created test case ids and counts.
    """
    uid = _user(user_id) or ""
    payload = {
        "test_cases": test_cases,
        "module": module,
        "feature": feature,
        "feature_id": feature_id,
        "test_mode": test_mode,
        "project_id": _project(project_id),
        "user_id": uid,
        "created_by": uid or "claude-code",
        "browser_type": browser_type,
        "platform": platform,
        "env_id": env_id,
        "apk_id": apk_id,
    }
    return await client.post_platform("/api/test-cases/create-from-claude", payload)


@mcp.tool()
async def create_test_case_from_defect(
    defect_id: str,
    project_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Generate a test case from an existing defect/bug id by pulling its details
    and reproducing it as a test.
    """
    payload = {
        "defectId": defect_id,
        "projectId": _project(project_id),
        "userId": _user(user_id) or "",
        "token": "",
    }
    return await client.post_platform("/api/test-cases/create-from-defect", payload)


# ---------------------------------------------------------------- execution ----
@mcp.tool()
async def run_tests(
    test_case_id: str | None = None,
    test_run_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    browser_type: str = "chrome",
    platform: str = "",
    env_id: str = "-",
    apk_id: str = "",
    parallel: bool = False,
) -> dict[str, Any]:
    """Execute a test case or a whole test run on the Oniesoft execution engine.

    DIFFERENTIATORS (beyond Playwright-only tools):
      * Native MOBILE: set platform="local,<tunnel-id>" and apk_id=<app id> to run
        real Android/iOS app tests via Appium.
      * Self-healing SEMANTIC locators: web & mobile steps locate elements by
        meaning (fine-tuned sentence-transformers), so tests survive selector
        churn without maintenance.

    Provide either test_case_id (single case) or test_run_id (a saved run).
    Returns an execution id; poll get_run_status with it.
    """
    payload: dict[str, Any] = {
        "projectId": _project(project_id),
        "userId": _user(user_id) or "",
        "browserType": browser_type,
        "platform": platform,
        "envId": env_id,
        "apkId": apk_id,
        "parallel": parallel,
    }
    if test_case_id:
        payload["testCaseId"] = test_case_id
    if test_run_id:
        payload["testRunId"] = test_run_id
    if not test_case_id and not test_run_id:
        raise ValueError("Provide either test_case_id or test_run_id.")
    return await client.post_execution("/run-tests", payload)


@mcp.tool()
async def get_run_status(execution_id: str) -> dict[str, Any]:
    """Check whether an execution started by run_tests is still running."""
    return await client.get_execution(f"/status/{execution_id}")


@mcp.tool()
async def stop_tests(execution_id: str) -> dict[str, Any]:
    """Stop an in-progress execution started by run_tests."""
    return await client.post_execution(f"/stop-tests/{execution_id}", {})


# ----------------------------------------------------------------- analysis ----
@mcp.tool()
async def analyze_test_run(
    test_run_id: str,
    user_input: str = "",
    project_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Analyze a completed test run: top failure reasons (from stack traces) or
    an answer to a specific question (user_input). Leave user_input empty for the
    default top-3-failures summary.
    """
    payload = {
        "test_run_id": test_run_id,
        "user_input": user_input or None,
        "projectId": _project(project_id),
        "userId": _user(user_id) or "",
        "token": "",
    }
    return await client.post_platform("/api/test_run/ask", payload)


@mcp.tool()
async def compare_test_runs(
    run_ids: list[str],
    user_input: str = "",
    project_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Compare two or more test runs: differences in failures, timing, results."""
    payload = {
        "run_ids": run_ids,
        "user_input": user_input or None,
        "projectId": _project(project_id),
        "userId": _user(user_id) or "",
        "token": "",
    }
    return await client.post_platform("/api/test_run/compare", payload)


@mcp.tool()
async def analyze_stack_trace(stack_trace: str) -> dict[str, Any]:
    """Explain a raw stack trace in plain language (root cause + likely fix)."""
    return await client.post_platform("/api/stack_trace/analyze", {"stack_trace": stack_trace})


# from super agent
@mcp.tool("get_feature_id_by_name_or_unique_key")
async def get_feature_id_by_name_or_unique_key(
    input: ModuleIdByNameOrUniqueKeyInput,
) -> FeatureCreationOutput:
    """
    Get feature ID by name or unique key.

    Args:
        input (ModuleIdByNameOrUniqueKeyInput): Input containing details for retrieving feature ID. The identifier field in the input is used to filter features by name or unique key.

    Returns:
        FeatureCreationOutput: Output containing the details of the feature that matches the provided name or unique key.
    """
    headers = {
        "Authorization": f"Bearer {input.token}",
        "Content-Type": "application/json",
    }
    resp = await _http_get(
        f"{_get_backend_url()}feature/v1/get-features-by-projectId/{input.projectId}?query={input.identifier}&deleted=false&page=0&size=25&moduleName=",
        headers=headers,
    )
    if resp.status_code == 200:
        feats = resp.json().get("content", [])
        if len(feats) == 0:
            raise Exception(
                f"No feature found with name or unique key: {input.identifier}"
            )
        elif len(feats) == 1:
            return FeatureCreationOutput(
                id=uuid.UUID(feats[0].get("id")),
                name=feats[0].get("featureName"),
                uniqueKey=feats[0].get("uniqueKey"),
            )
        else:
            for feat in feats:
                if (
                    feat.get("featureName").lower() == input.identifier.lower()
                    or feat.get("uniqueKey").lower() == input.identifier.lower()
                ):
                    return FeatureCreationOutput(
                        id=uuid.UUID(feat.get("id")),
                        name=feat.get("featureName"),
                        uniqueKey=feat.get("uniqueKey"),
                    )
    else:
        raise Exception(f"Failed to retrieve features: {resp.text}")


@mcp.tool("create_feature")
async def create_feature(input: FeatureCreationInput) -> FeatureCreationOutput:
    """
    Create a feature.

    Args:
        input (FeatureCreationInput): Input containing details for the feature creation.

    Returns:
        FeatureCreationOutput: Output containing the details of the created feature.
    """
    headers = {
        "Authorization": f"Bearer {input.token}",
        "Content-Type": "application/json",
    }
    payload = {
        "featureName": input.name,
        "description": input.description,
        "companyId": str(input.companyId),
        "projectId": str(input.projectId),
    }
    resp = await _http_post(
        f"{_get_backend_url()}feature/v1/save/{input.moduleId}",
        json=payload,
        headers=headers,
    )
    if resp.status_code == 200:
        data = resp.json()
        return FeatureCreationOutput(
            id=uuid.UUID(data.get("id", str(uuid.uuid4()))),
            name=data.get("featureName", input.name),
            uniqueKey=data.get("uniqueKey", str(uuid.uuid4())),
        )
    else:
        raise Exception(f"Failed to create feature: {resp.text}")
