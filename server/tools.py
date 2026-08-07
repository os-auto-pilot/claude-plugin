"""MCP tool definitions for the Oniesoft test platform.

Each tool is a thin, typed wrapper over a backend REST endpoint. Tools fill in
the project/user defaults from the environment when the caller omits them, so
the model can call them with minimal arguments.
"""

from __future__ import annotations

import asyncio
from enum import unique
import json
import os
from typing import Any, List, Optional, Union
import uuid

from mcp.server.fastmcp import FastMCP

from server.request_response_model import *

from . import client

mcp = FastMCP("auto-pilot plugin")


_MISSING_ID_HELP = (
    "No {field} given and no default configured. Read the `config.json` file in "
    "the project's root directory (the folder you're working in, not the plugin "
    "directory) and pass its `{field}` value explicitly as the `{field}` argument "
    "to this tool. Do not search `.credentials.json` or `settings.json` for this — "
    "those don't contain it."
)


def _project(project_id: uuid.UUID | None) -> str:
    if project_id:
        return str(project_id)
    pid = client.default_project_id()
    if pid:
        return str(uuid.UUID(str(pid)))
    raise ValueError(_MISSING_ID_HELP.format(field="projectId"))


def _user(user_id: uuid.UUID | None) -> str | None:
    if user_id:
        return str(user_id)
    uid = client.default_user_id()
    if uid:
        return str(uuid.UUID(str(uid)))
    return None


# --------------------------------------------------------------- generation ----
# @mcp.tool()
# async def create_test_cases(
#     user_input: str,
#     module: str,
#     feature: str,
#     test_mode: str = "web",
#     project_id: str | None = None,
#     user_prompt: str = "",
#     browser_type: str = "Chrome",
#     platform: str = "",
#     env_id: str = "",
#     apk_id: str = "",
#     severity: str = "Minor",
# ) -> dict[str, Any]:
#     """Generate and persist test cases from a natural-language description.

#     test_mode is one of: "web" (UI), "api" (HTTP/REST), or "mobile" (native
#     Android/iOS). The backend routes web/mobile through the UI pipeline and api
#     through the API pipeline, then stores the resulting test cases in the project.

#     Returns the created test case ids and counts.
#     """
#     payload = {
#         "user_input": user_input,
#         "module": module,
#         "feature": feature,
#         "testMode": test_mode,
#         "projectId": _project(project_id),
#         "createdBy": _user(None) or "claude-code",
#         "userId": _user(None) or "",
#         "user_prompt": user_prompt,
#         "browserType": browser_type,
#         "platform": platform,
#         "envId": env_id,
#         "apkId": apk_id,
#         "severity": severity,
#     }
#     return await client.post_platform("/api/test-cases/create", payload)


@mcp.tool()
async def get_autopilot_steps(test_mode: str) -> list[dict]:
    """Return the complete list of supported autopilot step templates for a given test mode.

    ⚠️  SKILL-SCOPED TOOL — only call this from within the /analyze-requirements skill,
    during Step 2c (parallel extraction) BEFORE writing any autopilot steps.
    Do NOT call this tool in any other context or skill.

    Args:
        test_mode: "web", "mobile", or "api"

    Returns:
        List of step definitions — each has "name", "description", "step" (the exact
        template string to use), and "keywords". Write autopilot steps using ONLY
        the "step" templates returned here.
    """
    payload = {"test_mode": test_mode}
    resp = await client.get_platform("/api/test-steps", params=payload)
    if resp["status_code"] != 200:
        raise ValueError(f"Failed to fetch autopilot steps: {resp['data']}")
    return resp["data"]["test_steps"] if "test_steps" in resp["data"] else []


@mcp.tool()
async def save_claude_test_cases(
    request: CreateTestCaseFromClaudeRequest,
) -> dict[str, Any]:
    """Persist test cases that Claude authored in Phase 1/2 — NO LLM re-analysis.

    Use this (not create_test_cases) after /analyze-requirements + element-discoverer
    have produced fully structured test cases. The backend only creates elements with
    real selectors and validates step syntax; it does NOT re-interpret the content.

    input: CreateTestCaseFromClaudeRequest with test_cases, module, feature, test_mode, project_id, user_id, browser_type, platform, env_id, apk_id

    Returns the created test case ids and counts.
    """
    uid = _user(request.user_id) or ""
    payload = {
        "test_cases": [tc.model_dump(mode="json") for tc in request.test_cases],
        "module": request.module,
        "feature": str(request.feature),
        "test_mode": request.test_mode,
        "project_id": _project(request.project_id),
        "user_id": uid,
        "created_by": request.created_by,
        "browser_type": request.browser_type,
        "platform": request.platform,
        "env_id": request.env_id,
        "apk_id": request.apk_id,
    }
    return await client.post_platform("/api/test-cases/create-from-claude", payload)


@mcp.tool()
async def create_test_case_from_defect(
    defect_id: str,
    project_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
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
# @mcp.tool()
# async def run_tests(
#     test_case_id: str | None = None,
#     test_run_id: str | None = None,
#     project_id: uuid.UUID | None = None,
#     user_id: uuid.UUID | None = None,
#     browser_type: str = "chrome",
#     platform: str = "",
#     env_id: str = "-",
#     apk_id: str = "",
#     parallel: bool = False,
# ) -> dict[str, Any]:
#     """Execute a test case or a whole test run on the Oniesoft execution engine.

#     DIFFERENTIATORS (beyond Playwright-only tools):
#       * Native MOBILE: set platform="local,<tunnel-id>" and apk_id=<app id> to run
#         real Android/iOS app tests via Appium.
#       * Self-healing SEMANTIC locators: web & mobile steps locate elements by
#         meaning (fine-tuned sentence-transformers), so tests survive selector
#         churn without maintenance.

#     Provide either test_case_id (single case) or test_run_id (a saved run).
#     Returns an execution id; poll get_run_status with it.
#     """
#     payload: dict[str, Any] = {
#         "projectId": _project(project_id),
#         "userId": _user(user_id) or "",
#         "browserType": browser_type,
#         "platform": platform,
#         "envId": env_id,
#         "apkId": apk_id,
#         "parallel": parallel,
#     }
#     if test_case_id:
#         payload["testCaseId"] = test_case_id
#     if test_run_id:
#         payload["testRunId"] = test_run_id
#     if not test_case_id and not test_run_id:
#         raise ValueError("Provide either test_case_id or test_run_id.")
#     return await client.post_execution("/run-tests", payload)


# @mcp.tool()
# async def get_run_status(execution_id: str) -> dict[str, Any]:
#     """Check whether an execution started by run_tests is still running."""
#     return await client.get_execution(f"/status/{execution_id}")


# @mcp.tool()
# async def stop_tests(execution_id: str) -> dict[str, Any]:
#     """Stop an in-progress execution started by run_tests."""
#     return await client.post_execution(f"/stop-tests/{execution_id}", {})


# ----------------------------------------------------------------- analysis ----
@mcp.tool()
async def fetch_test_run_results(test_run_id: str) -> dict[str, Any]:
    """Fetch all test case results for a completed test run directly from the backend.

    Paginates through all results and returns aggregated stats plus a list of
    failed cases (with IDs and names) ready to pass to fetch_test_run_failure_details.

    Returns:
        run_name, overall totals (total/pass/fail/skip), breakdowns by feature /
        module / severity / test_mode / author, and failed_cases list.
    """
    page = 0
    all_cases: list[dict] = []
    run_name = "Unknown Run"

    while True:
        params = {
            "query": "",
            "testMode": "",
            "featureName": "",
            "moduleName": "",
            "author": "",
            "severity": "",
            "testType": "",
            "status": "",
            "jiraIssueFixed": "false",
            "page": page,
            "size": 25,
        }
        resp = await client.get_backend(
            f"/testrun/v1/{test_run_id}/ordered-test-cases", params=params
        )
        if resp["status_code"] != 200:
            raise ValueError(f"Failed to fetch test run results: {resp['data']}")

        data = resp["data"]
        content = data.get("content", [])
        if content and run_name == "Unknown Run":
            run_name = content[0].get("testRunName", "Unknown Run")
        all_cases.extend(content)
        if data.get("last", True):
            break
        page += 1

    # Aggregate stats
    totals = {"total": 0, "pass": 0, "fail": 0, "skip": 0}
    by_feature: dict[str, dict] = {}
    by_module: dict[str, dict] = {}
    by_severity: dict[str, dict] = {}
    by_test_mode: dict[str, dict] = {}
    by_author: dict[str, dict] = {}
    failed_cases: list[dict] = []

    def _inc(bucket: dict[str, dict], key: str, status: str) -> None:
        if key not in bucket:
            bucket[key] = {"total": 0, "pass": 0, "fail": 0, "skip": 0}
        bucket[key]["total"] += 1
        if status in bucket[key]:
            bucket[key][status] += 1

    for case in all_cases:
        status = (case.get("status") or "").lower()
        totals["total"] += 1
        if status in totals:
            totals[status] += 1
        _inc(by_feature, case.get("feature", ""), status)
        _inc(by_module, case.get("module", ""), status)
        _inc(by_severity, case.get("severity", ""), status)
        _inc(by_test_mode, case.get("testMode", ""), status)
        _inc(by_author, case.get("author", ""), status)
        if status == "fail":
            failed_cases.append(
                {"id": case["id"], "name": case.get("testCaseName", "")}
            )

    return {
        "run_name": run_name,
        **totals,
        "by_feature": by_feature,
        "by_module": by_module,
        "by_severity": by_severity,
        "by_test_mode": by_test_mode,
        "by_author": by_author,
        "failed_cases": failed_cases,
    }


@mcp.tool()
async def fetch_test_run_failure_details(
    failed_case_ids: list[str],
) -> list[dict[str, Any]]:
    """Fetch trace stacks and step details for a list of failed test case IDs.

    Call this after fetch_test_run_results to get the raw failure data Claude
    needs to identify root causes. Pass the 'id' values from failed_cases.

    Returns a list of dicts: case_id, trace_stack (last 500 chars), test_data, test_steps.
    """
    semaphore = asyncio.Semaphore(10)

    async def _fetch_one(case_id: str) -> list[dict]:
        async with semaphore:
            resp = await client.get_backend(
                f"/testrun/v1/get-test-data-result/{case_id}"
            )
        if resp["status_code"] != 200:
            return [{"case_id": case_id, "error": str(resp["data"])}]
        raw = resp["data"]
        if not isinstance(raw, list):
            raw = [raw] if raw else []
        items = []
        for item in raw:
            if str(item.get("status", "")).lower() != "fail":
                continue
            trace = str(item.get("traceStack") or "")
            test_steps = ""
            trac = item.get("testRunAndCase")
            if isinstance(trac, dict):
                test_steps = str(trac.get("testSteps") or "")
            items.append(
                {
                    "case_id": case_id,
                    "data_id": item.get("id", ""),
                    "trace_stack": trace[-500:] if len(trace) > 500 else trace,
                    "test_data": str(item.get("testData") or ""),
                    "test_steps": test_steps,
                }
            )
        return items

    nested = await asyncio.gather(*[_fetch_one(cid) for cid in failed_case_ids])
    return [item for sublist in nested for item in sublist]


@mcp.tool()
async def fetch_util_details(
    input: GetUtilsWithFiltersInput,
) -> GetUtilsWithFiltersOutput:
    """Search and filter shared utilities (utils) in a project.

    Returns a paginated list of utils matching the provided filters. Useful for
    discovering which utilities are available in a module/feature, or for looking
    up a util by name before referencing it in test steps.
    """
    project_id = _project(input.projectId)
    params: dict[str, Any] = {
        "query": input.query or "",
        "testMode": input.testMode or "",
        "feature": input.feature or "",
        "module": input.module or "",
        "page": input.page,
        "size": input.size,
        "status": str(input.status).lower() if input.status is not None else "false",
        "deleted": str(input.deleted).lower() if input.deleted is not None else "false",
    }
    resp = await client.get_backend(
        f"/utils/v1/get-all-utils/{project_id}", params=params
    )
    if resp["status_code"] != 200:
        raise ValueError(f"Failed to fetch utils: {resp['data']}")
    data = resp["data"]
    return GetUtilsWithFiltersOutput(
        content=[UtilOutput(**item) for item in data.get("content", [])],
        totalElements=data.get("totalElements", 0),
        totalPages=data.get("totalPages", 0),
        page=data.get("number", input.page),
        size=data.get("size", input.size),
        last=data.get("last", True),
    )


# def _format_test_data(entries: List[TestDataEntry]) -> list:
#     if not entries:
#         return []
#     data_dict = {td.field: {"value": td.value, "type": td.type} for td in entries}
#     return [{"data": data_dict}]


@mcp.tool()
async def save_claude_utils(request: CreateUtilFromClaudeRequest) -> dict[str, Any]:
    """Persist utils that Claude identified in Phase 1 — NO LLM re-analysis.

    Call this BEFORE save_claude_test_cases when reusable utils were identified
    during requirement analysis. The returned UUIDs must be used in test case steps
    as: execute util "<uuid>"

    Test data in a util can be overridden by a calling test case using the naming
    convention: <field>_i<N>_<util-uuid> where N is the invocation number (1, 2, ...).
    Override is optional — omitting it uses the util's default test data.

    input: CreateUtilFromClaudeRequest with utils, module, project_id, usernName
    Returns the created util UUIDs and count.
    """
    payload = {
        "utils": [u.model_dump(mode="json") for u in request.utils],
        "module": request.module,
        "project_id": _project(request.projectId),
        "userName": request.userName,
        "user_id": _user(request.user_id),
        "token": request.token,
    }
    return await client.post_platform("/api/utils/create-from-claude", payload)


# from super agent
@mcp.tool("get_feature_id_by_name_or_unique_key")
async def get_feature_id_by_name_or_unique_key(
    input: FeatureIdByNameOrUniqueKeyInput,
) -> FeatureCreationOutput | None:
    """
    Get feature ID by name or unique key.

    Args:
        input (FeatureIdByNameOrUniqueKeyInput): Input containing details for retrieving feature ID. The identifier field in the input is used to filter features by name or unique key.

    Returns:
        FeatureCreationOutput: Output containing the details of the feature that matches the provided name or unique key.
    """
    resp = await client.get_backend(
        f"/feature/v1/get-features-by-projectId/{_project(input.projectId)}?query={input.identifier}&deleted=false&page=0&size=25&moduleName=",
    )

    if resp["status_code"] == 200:
        feats = resp["data"].get("content", [])
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
        raise Exception(f"Failed to retrieve features: {resp['data']}")


@mcp.tool("create_feature")
async def create_feature(input: FeatureCreationInput) -> FeatureCreationOutput:
    """
    Create a feature.

    Args:
        input (FeatureCreationInput): Input containing details for the feature creation.

    Returns:
        FeatureCreationOutput: Output containing the details of the created feature.
    """
    payload = {
        "featureName": input.name,
        "description": input.description,
        "companyId": str(input.companyId),
        "projectId": _project(input.projectId),
    }
    resp = await client.post_backend(f"/feature/v1/save/{input.moduleId}", payload)
    if resp["status_code"] == 200:
        data = resp["data"]
        return FeatureCreationOutput(
            id=uuid.UUID(data.get("id", str(uuid.uuid4()))),
            name=data.get("featureName", input.name),
            uniqueKey=data.get("uniqueKey", str(uuid.uuid4())),
        )
    else:
        raise Exception(f"Failed to create feature: {resp['data']}")


@mcp.tool("create_module")
async def create_module(input: ModuleCreationInput) -> ModuleOutputResponse:
    """
    Create a module.

    Args:
        input (ModuleCreationInput): Input containing details for the module creation.

    Returns:
        ModuleOutputResponse: Output containing the details of the created module.
    """
    payload = {
        "moduleName": input.moduleName,
        "description": input.description,
        "companyId": str(input.companyId),
        "projectId": _project(input.projectId),
    }
    resp = await client.post_backend(f"/module/v1/save", payload)
    if resp["status_code"] == 200:
        data = resp["data"]
        return ModuleOutputResponse(
            id=uuid.UUID(data.get("id", str(uuid.uuid4()))),
            moduleName=data.get("moduleName", input.moduleName),
            uniqueKey=data.get("uniqueKey", str(uuid.uuid4())),
        )
    else:
        raise Exception(f"Failed to create module: {resp['data']}")


@mcp.tool("get_module_id_by_name_or_unique_key")
async def get_module_id_by_name_or_unique_key(
    input: ModuleIdByNameOrUniqueKeyInput,
) -> ModuleOutputResponse | None:
    """
    Get module ID by name or unique key.

    Args:
        input (ModuleIdByNameOrUniqueKeyInput): Input containing details for retrieving module ID. The identifier field in the input is used to filter modules by name or unique key.

    Returns:
        ModuleOutputResponse: Output containing the details of the module that matches the provided name or unique key.
    """
    resp = await client.get_backend(
        f"/module/v1/get-page-modules/{_project(input.projectId)}?query={input.identifier.lower()}&deleted=false&page=0&size=25",
    )
    if resp["status_code"] == 200:
        mods = resp["data"].get("content", [])
        if len(mods) == 0:
            raise Exception(
                f"No module found with name or unique key: {input.identifier}"
            )
        elif len(mods) == 1:
            return ModuleOutputResponse(
                id=uuid.UUID(mods[0].get("id")),
                moduleName=mods[0].get("moduleName"),
                uniqueKey=mods[0].get("uniqueKey"),
            )
        else:
            for mod in mods:
                if (
                    mod.get("moduleName").lower() == input.identifier.lower()
                    or mod.get("uniqueKey").lower() == input.identifier.lower()
                ):
                    return ModuleOutputResponse(
                        id=uuid.UUID(mod.get("id")),
                        moduleName=mod.get("moduleName"),
                        uniqueKey=mod.get("uniqueKey"),
                    )
    else:
        raise Exception(f"Failed to retrieve modules: {resp['data']}")


@mcp.tool("get_project_id_by_name")
async def get_project_id_by_name(
    input: ProjectIdByNameInput,
) -> list[ProjectIdByNameOutput]:
    """
    Get a list of admin projects for the user.

    Args:
        input (ProjectIdByNameInput): Input containing details for retrieving admin projects. The name field in the input is used to filter projects by name.
    Returns:
        list: A list of admin projects that match the provided name.
    """
    resp = await client.get_backend(
        f"/projects/v1/getprojectsbybranchid/{input.companyId}",
    )
    if resp["status_code"] == 200:
        matching_projects: list[ProjectIdByNameOutput] = []
        target_name = input.name.strip().lower()

        for proj in resp["data"]:
            project_name = proj.get("projectName", "").strip().lower()
            project_id = proj.get("id")
            if not project_name or not project_id:
                continue
            if project_name.lower() != target_name:
                continue

            matching_projects.append(
                ProjectIdByNameOutput(
                    id=uuid.UUID(str(project_id)),
                    name=project_name,
                )
            )

        return matching_projects
    else:
        raise Exception(f"Failed to retrieve admin projects: {resp['data']}")


@mcp.tool("get_web_environment_details_by_name_or_unique_key")
async def get_web_environment_details_by_name_or_unique_key(
    input: GetEnvironmentDetailsByNameOrUniqueKeyInput,
) -> Union[CreateWebEnvironmentOutput, List[str]]:
    """
    Get web environment details by name or unique key.

    Args:
        input (GetEnvironmentDetailsByNameOrUniqueKeyInput): Input containing details for retrieving web environment details. The identifier field in the input is used to filter web environments by name or unique key.

    Returns:
        CreateWebEnvironmentOutput: Output containing the details of the web environment that matches the provided name or unique key.
        List[str]: List of all environment names in the project when no match is found for the given identifier.
    """
    resp = await client.get_backend(
        f"/servers/v1/list-servers?projectId={_project(input.projectId)}&deleted=false",
    )
    if resp["status_code"] == 200:
        envs = resp["data"]
        if len(envs) == 0:
            raise Exception("No environments in the project")
        else:
            for env in envs:
                unique_key = env.get("uniqueKey") if env.get("uniqueKey") else ""
                if (
                    env.get("serverName", "").lower() == input.identifier.lower()
                    or unique_key.lower() == input.identifier.lower()
                ):
                    return CreateWebEnvironmentOutput(
                        id=uuid.UUID(env.get("id")),
                        serverName=env.get("serverName"),
                        uniqueKey=env.get("uniqueKey"),
                        apiBaseURL=env.get("apiBaseURL", ""),
                        serverUrl=env.get("serverUrl", ""),
                        description=env.get("description", ""),
                        basicAuth=env.get("basicAuth", False),
                        enableBook=env.get("enableBook", False),
                    )
            else:
                return [env.get("serverName", "") for env in envs]
    else:
        raise Exception(f"Failed to retrieve web environments: {resp['data']}")


@mcp.tool("get_user_details_by_id_or_email_or_unique_key")
async def get_user_details_by_id_or_email_or_unique_key(
    input: GetUserDetailsByIdOrEmailOrUniqueKeyInput,
) -> GetUserDetailsOutput:
    """
    Get user details by ID, email, or unique key.

    Args:
        input (GetUserDetailsByIdOrEmailOrUniqueKeyInput): Input containing details for retrieving user details. The identifier field in the input is used to filter users by ID, email, or unique key.

    Returns:
        GetUserDetailsOutput: Output containing the details of the user that matches the provided ID, email, or unique key.

    """
    try:
        uuid.UUID(input.identifier)
        identifier = ""
    except ValueError:
        # If the identifier is not a valid UUID, we can assume it's an email or unique key
        identifier = input.identifier
        pass
    resp = await client.get_backend(
        f"/adminview/v1/users-by-branch-role?cmpId={input.companyId}&query={identifier}&page=0&size=50"
    )
    if resp["status_code"] == 200:
        users = resp["data"].get("content", [])
        if len(users) == 0:
            raise Exception(
                f"No user found with ID, email, or unique key: {input.identifier}"
            )
        matched_user = None
        if len(users) == 1:
            matched_user = users[0]
        else:
            identifier = input.identifier.lower()
            matched_user = next(
                (
                    user
                    for user in users
                    if identifier
                    in (
                        str(user.get("email", "")).lower(),
                        str(user.get("empId", "")).lower(),
                        str(user.get("userId", "")).lower(),
                        str(user.get("empName", "")).lower(),
                    )
                ),
                None,
            )

        if matched_user is None:
            raise Exception(
                f"No exact user match found in search results for: {input.identifier}"
            )

        return GetUserDetailsOutput(**matched_user)
    else:
        raise Exception(f"Failed to retrieve users: {resp['data']}")


@mcp.tool("create_test_run")
async def create_test_run(input: TestRunCreationInput) -> TestRunCreationOutput:
    """
    Create a new test run.

    Args:
        input (TestRunCreationInput): Input containing details for creating a test run.
        In input the createdBy field will be used to set the user who created the test run, you can use the user name from the session context

    Returns:
        TestRunCreationOutput: Output containing details of the created test run.
    """
    payload = input.model_dump(exclude={"token"}, mode="json", exclude_none=True)
    resp = await client.post_backend(
        f"/testrun/v1/createtestrun",
        payload,
    )
    if resp["status_code"] == 200:
        data = resp["data"]
        return TestRunCreationOutput(**data)
    else:
        raise Exception(f"Failed to create test run: {resp['data']}")


@mcp.tool("get_test_runs_with_filters")
async def get_test_runs_with_filters(
    input: TestRunDetailsInput,
) -> List[TestRunDetailsOutput]:
    """
    Get list of test runs by applying various filters. The nameOrUniqueKey field in the input is used to filter test runs by name or unique key. Additional filters such as status and created by can also be applied to narrow down the search results.

    Args:
        input (TestRunDetailsInput): Input containing details for retrieving test run details. The nameOrUniqueKey field in the input is used to filter test runs by name or unique key.

    Returns:
        List[TestRunDetailsOutput]: Output containing the details of the test runs that match the provided name or unique key.
    """

    base_params = {
        "projectId": _project(input.projectId),
        "query": input.nameOrUniqueKey,
        "status": input.status,
        "createdBy": input.createdBy,
        "deleted": "false",
    }
    base_params = {k: v for k, v in base_params.items() if v not in (None, "")}

    page = 0
    size = 200
    collected: list[dict[str, Any]] = []

    while True:
        params = {**base_params, "page": str(page), "size": str(size)}
        resp = await client.get_backend(
            f"/testrun/v1/gettestrunbyid",
            params=params,
        )

        if resp["status_code"] != 200:
            raise Exception(f"Failed to retrieve test runs: {resp['data']}")

        body = resp["data"] or {}
        chunk = body.get("content", []) or []
        collected.extend(chunk)

        # Stop conditions for different pagination response styles
        is_last = body.get("last")
        total_pages = body.get("totalPages")
        if is_last is True:
            break
        if isinstance(total_pages, int) and page >= (total_pages - 1):
            break
        if len(chunk) < size:
            break
        if not chunk:
            break

        page += 1

    if len(collected) == 0:
        if input.nameOrUniqueKey:
            raise Exception(
                f"No test run found with name or unique key: {input.nameOrUniqueKey}"
            )
        raise Exception("No test runs found for the provided filters")

    return [TestRunDetailsOutput(**test_run) for test_run in collected]


@mcp.tool("add_or_remove_test_cases_from_test_run")
async def add_or_remove_test_cases_from_test_run(
    input: AddOrRemoveTestCasesFromTestRunInput,
) -> str:
    """
    Add or remove test cases from a test run.
    We will first filter test cases by the provided criteria and fetch their IDs, then we will add or remove the test cases from the test run based on the action specified in the input (add or remove).

    Args:
        input (AddOrRemoveTestCasesFromTestRunInput): Input containing details for adding or removing test cases from a test run. The action field in the input is used to specify whether to add or remove the specified test cases from the test run.
    Returns:
        str: A message indicating the successful addition or removal of test cases from the test run.
    """
    # add_case_ids = [str(case_id) for case_id in (input.testCaseId or [])]
    # remove_case_ids = [str(case_id) for case_id in (input.testCaseIdsToRemove or [])]
    add_case_ids: list[str] = []
    remove_case_ids: list[str] = []
    action = input.action.lower()

    def _split_csv(value: Optional[str]) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def _looks_like_unique_key(value: str) -> bool:
        normalized = value.strip().upper()
        prefix = "TC-"
        return normalized.startswith(prefix) and normalized[len(prefix) :].isdigit()

    def _append_unique(values: list[str], additions: list[str]) -> list[str]:
        seen = set(values)
        for addition in additions:
            if addition not in seen:
                values.append(addition)
                seen.add(addition)
        return values

    query_terms = _split_csv(input.nameOrUniqueKey)
    unique_key_terms = [term for term in query_terms if _looks_like_unique_key(term)]
    name_terms = [term for term in query_terms if term not in unique_key_terms]

    if unique_key_terms:
        print(f"Resolving unique keys to IDs for: {unique_key_terms}")
        resolved_unique_key_ids = await get_test_cases_uuid_by_unique_keys(
            GetTestCasesUUIDByUniqueKeyInput(
                projectId=uuid.UUID(_project(input.projectId)),
                uniqueKeys=unique_key_terms,
                active=False,
                deleted=False,
            )
        )
        resolved_unique_key_ids_as_str = [
            str(case_id) for case_id in resolved_unique_key_ids
        ]
        if action == "add":
            add_case_ids = _append_unique(add_case_ids, resolved_unique_key_ids_as_str)
        elif action == "remove":
            remove_case_ids = _append_unique(
                remove_case_ids, resolved_unique_key_ids_as_str
            )

    filter_base_params = {
        "query": ",".join(name_terms) if name_terms else None,
        "testMode": input.testMode,
        "featureName": input.featureName,
        "moduleName": input.moduleName,
        "author": input.author,
        "testType": input.testType,
        "severity": input.severity,
    }
    filter_base_params = {
        k: v for k, v in filter_base_params.items() if v not in (None, "")
    }

    should_fetch_filtered_test_cases = bool(filter_base_params)
    if should_fetch_filtered_test_cases:
        page = 0
        size = 200
        filtered_test_case_ids: list[str] = []

        while True:
            filter_params = {
                **filter_base_params,
                "page": str(page),
                "size": str(size),
            }
            print(f"Fetching test cases for filtering with params: {filter_params}")

            filter_resp = await client.get_backend(
                f"/testrun/v1/edittestrun/{input.id}/{_project(input.projectId)}",
                params=filter_params,
            )
            if filter_resp["status_code"] != 200:
                raise Exception(
                    f"Failed to retrieve test cases for filtering: {filter_resp['data']}"
                )

            body = filter_resp["data"] or {}
            data = body.get("data", {}) if isinstance(body, dict) else {}
            test_cases = data.get("testCases", []) if isinstance(data, dict) else []

            filtered_test_case_ids.extend(
                str(test_case.get("id"))
                for test_case in test_cases
                if test_case.get("id")
                and test_case.get("testType", "").lower() != "manual"
            )

            # Stop conditions for different response pagination styles
            pages = body.get("pagination", {}) if isinstance(body, dict) else {}
            is_last = pages.get(
                "last", pages.get("last") if isinstance(pages, dict) else None
            )
            total_pages = pages.get(
                "totalPages",
                pages.get("totalPages") if isinstance(pages, dict) else None,
            )

            if is_last is True:
                break
            if isinstance(total_pages, int) and page >= (total_pages - 1):
                break
            if not test_cases:
                break
            if len(test_cases) < size:
                break

            page += 1

        if len(filtered_test_case_ids) == 0:
            raise Exception(
                f"No test case found with the provided criteria to {input.action}"
            )

        if action == "add":
            add_case_ids = filtered_test_case_ids
        elif action == "remove":
            remove_case_ids = filtered_test_case_ids

    if action == "add" and not add_case_ids:
        raise Exception("No test case IDs were resolved to add to the test run")
    if action == "remove" and not remove_case_ids:
        raise Exception("No test case IDs were resolved to remove from the test run")

    payload = {
        "testCaseId": add_case_ids,
        "testCaseIdsToRemove": remove_case_ids,
        "testRunName": input.testRunName,
        "status": input.status,
        "id": str(input.id),
    }
    resp = await client.post_backend(
        f"/testrun/v1/addtestrun",
        payload,
    )
    if resp["status_code"] == 200:
        return f"Test cases successfully {action}ed the test run with ID: {input.id}"
    else:
        raise Exception(f"Failed to update test cases in test run: {resp['data']}")


@mcp.tool("get_environments_assigned_to_user")
async def get_environments_assigned_to_user(
    input: GetEnvironmentsAssignedToUserInput,
) -> List[GetEnvironmentsAssignedToUserOutput]:
    """
    Get list of environments assigned to a user. The userID field in the input is used to identify the user for which assigned environments will be retrieved.

    Args:
        input (GetEnvironmentsAssignedToUserInput): Input containing details for retrieving environments assigned to a user. The userID field in the input is used to identify the user for which assigned environments will be retrieved.

    Returns:
        List[GetEnvironmentsAssignedToUserOutput]: Output containing the list of environments assigned to the specified user.
    """
    resp = await client.get_backend(
        f"/servers/v1/servers-by-user/{_user(input.userID)}/{_project(input.projectId)}/true",
    )
    if resp["status_code"] == 200:
        environments = resp["data"]
        if len(environments) == 0:
            return []
        return [GetEnvironmentsAssignedToUserOutput(**env) for env in environments]
    else:
        raise Exception(
            f"Failed to retrieve environments assigned to user: {resp['data']}"
        )


@mcp.tool("get_projects_assigned_to_user")
async def get_projects_assigned_to_user(
    input: GetProjectsAssignedToUserInput,
) -> List[GetProjectsAssignedToUserOutput]:
    """
    Get list of projects assigned to a user. The userID field in the input is used to identify the user for which assigned projects will be retrieved.

    Args:
        input (GetProjectsAssignedToUserInput): Input containing details for retrieving projects assigned to a user. The userID field in the input is used to identify the user for which assigned projects will be retrieved.

    Returns:
        List[GetProjectsAssignedToUserOutput]: Output containing the list of projects assigned to the specified user.
    """
    resp = await client.get_backend(
        f"/projectusers/v1/getassignprojects/{_user(input.userID)}",
    )
    print(
        f"Response from get projects assigned to user API: {resp['status_code']} - {resp['data']}"
    )
    if resp["status_code"] == 200:
        projects = resp["data"]
        if len(projects) == 0:
            return []
        return [GetProjectsAssignedToUserOutput(**proj) for proj in projects]
    else:
        raise Exception(f"Failed to retrieve projects assigned to user: {resp['data']}")


@mcp.tool("get_test_cases_with_filters")
async def get_test_cases_with_filters(
    input: GetTestCasesWithFiltersInAProjectInput,
) -> (
    List[GetTestCasesWithFiltersInAProjectOutput]
    | List[GetTestCasesWithFiltersInAProjectOutputLarge]
):
    """
    Get list of test cases in a project by applying various filters.
    Filters: nameOrUniqueKey, active, deleted, testMode (Web/API/Mobile), severity (Minor/Major/Blocker/Critical), testType, moduleName, featureName, author
    active and deleted filters in input are used to include/exclude active and deleted test cases respectively, active flag false means active, deleted flag false means not deleted.
    """

    base_params = {
        "id": _project(input.projectId),
        "query": input.nameOrUniqueKey,
        "testMode": input.testMode,
        "featureName": input.featureName,
        "moduleName": input.moduleName,
        "author": input.author,
        "testType": input.testType,
        "active": False,
        "deleted": input.deleted,
    }
    base_params = {k: v for k, v in base_params.items() if v not in (None, "")}

    page = 0
    size = 200
    collected: list[dict[str, Any]] = []

    try:
        while True:
            params = {
                **base_params,
                "page": str(page),
                "size": str(size),
            }

            resp = await client.get_backend(
                f"/testcases/v1/getForProject",
                params=params,
            )

            if resp["status_code"] != 200:
                raise Exception(f"Failed to retrieve test cases: {resp['data']}")

            body = resp["data"] or {}
            test_cases = body.get("content", []) if isinstance(body, dict) else []
            collected.extend(test_cases)

            is_last = body.get("last")
            total_pages = body.get("totalPages")

            if is_last is True:
                break
            if isinstance(total_pages, int) and page >= (total_pages - 1):
                break
            if not test_cases:
                break
            if len(test_cases) < size:
                break

            page += 1

        if len(collected) == 0:
            if input.nameOrUniqueKey:
                raise Exception(
                    f"No test case found with name or unique key: {input.nameOrUniqueKey} in the project with ID: {input.projectId}"
                )
            raise Exception(
                f"No test cases found for the provided filters in the project with ID: {input.projectId}"
            )

        if len(collected) > 10:
            return [
                GetTestCasesWithFiltersInAProjectOutputLarge(**test_case)
                for test_case in collected
            ]

        return [
            GetTestCasesWithFiltersInAProjectOutput(**test_case)
            for test_case in collected
        ]

    except Exception as e:
        raise Exception(f"An error occurred while retrieving test cases: {str(e)}")


@mcp.tool("get_test_cases_uuid_by_unique_keys")
async def get_test_cases_uuid_by_unique_keys(
    input: GetTestCasesUUIDByUniqueKeyInput,
) -> List[uuid.UUID]:
    """
    Get list of test cases UUIDs in a project by taking list of unique keys of the test cases.
    This method takes list of unique keys of test cases and returns list of test case uuids.

    Args:
        input (GetTestCasesUUIDByUniqueKeyInput): Input containing details for retrieving test case UUIDs by unique keys.

    Returns:
        List[uuid.UUID]: List of UUIDs corresponding to the provided unique keys.
    """
    unique_keys = [key.strip() for key in input.uniqueKeys if key and key.strip()]
    if not unique_keys:
        raise Exception("At least one non-empty unique key is required")

    semaphore = asyncio.Semaphore(5)

    async def _fetch_uuid_for_key(unique_key: str) -> uuid.UUID:
        params = {
            "id": _project(input.projectId),
            "query": unique_key,
            "deleted": input.deleted,
            "page": "0",
            "size": "50",
            "active": input.active,
        }
        params = {k: v for k, v in params.items() if v not in (None, "")}

        async with semaphore:
            resp = await client.get_backend(
                f"/testcases/v1/getForProject",
                params=params,
            )

        if resp["status_code"] != 200:
            raise Exception(
                f"Failed to retrieve test case for unique key '{unique_key}': {resp['data']}"
            )

        test_cases = resp["data"].get("content", [])
        if len(test_cases) == 0:
            raise Exception(
                f"No test case found with unique key: {unique_key} in project with ID: {input.projectId}"
            )

        for test_case in test_cases:
            if str(test_case.get("uniqueKey", "")).lower() == unique_key.lower():
                test_case_id = test_case.get("id")
                if not test_case_id:
                    break
                return uuid.UUID(str(test_case_id))

        raise Exception(
            f"No exact test case match found for unique key: {unique_key} in project with ID: {input.projectId}"
        )

    return await asyncio.gather(
        *[_fetch_uuid_for_key(unique_key) for unique_key in unique_keys]
    )


@mcp.tool("run_test_case")
async def run_test_case(input: RunTestCaseInput) -> str:
    """
    Run or execute a test case by its ID.

    Args:
        input (RunTestCaseInput): Input containing details for running a test case. The id field in the input is used to identify the test case to be run.

    Returns:
        str: A message indicating the successful execution of the test case.
    """
    payload = {
        "testCaseId": str(input.testCaseId),
        "browserType": input.browserType,
        "envId": str(input.envId),
        "platform": input.platform,
        "userId": str(input.userId),
    }
    # Load profile for Performance test cases. Field names must match the backend's
    # TestCaseRunDto exactly — note virtualUser*s*; anything else is silently ignored
    # by Jackson and the run quietly falls back to defaults. Only send what was
    # actually specified, so LoadProfileValidator applies its own defaults otherwise.
    load_profile = {
        "virtualUsers": input.virtualUsers,
        "duration": input.duration,
        "rampPattern": input.rampPattern,
    }
    payload.update({k: v for k, v in load_profile.items() if v is not None})

    resp = await client.post_backend(
        f"/testcases/v1/run-test-case",
        payload,
    )
    if resp["status_code"] == 200:
        return f"Test case with ID {input.testCaseId} execution started successfully, You can wait for the result"
    else:
        raise Exception(
            f"Failed to execute test case: {resp['data']}, DON'T call wait_for_test_execution_completion"
        )


@mcp.tool("schedule_test_run")
async def schedule_test_run(input: ScheduleTestRunInput) -> str:
    """
    Schedule a test run to be executed at a later time.

    Args:
        input (ScheduleTestRunInput): Input containing details for scheduling a test run. The id field in the input is used to identify the test run to be scheduled.

    Returns:
        str: A message indicating the successful scheduling of the test run.
    """
    # fetch existing run configuration to get details required for scheduling the run
    resp = await client.get_backend(
        f"/runconfig/v1/getrunconfig/{input.id}/{_project(input.projectId)}"
    )
    if resp["status_code"] != 200:
        raise Exception(f"Failed to retrieve test run configuration: {resp['data']}")
    run_config = resp["data"]
    # update the run configuration with scheduling details
    # we will reuse existing run confiuration details and only update the fields required for scheduling the run
    payload = {
        "id": run_config.get("id"),
        "userId": str(input.userID),
        "testRunId": run_config.get("testRunId"),
        "userName": input.userName,
        "userTimezone": input.userTimezone,
        "apkName": "",
        "envName": input.environment,
        "envId": str(input.envID),
        "existingApkName": "",
        "existingEnvName": "",
        "scheduleExecution": True,
        "scheduledDate": input.scheduledDate,
        "scheduledTime": input.scheduledTime,
        "autoClone": run_config.get("autoClone"),
        "cloneScheduleTime": run_config.get("cloneScheduleTime"),
        "allowParallelExecution": run_config.get("allowParallelExecution"),
        "platform": "server,server"
    }
    resp = await client.put_backend(
        f"/runconfig/v1/update",
        payload,
    )
    if resp["status_code"] == 200:
        return f"Test run with ID {input.id} scheduled successfully for {input.scheduledDate} at {input.scheduledTime}"
    else:
        raise Exception(f"Failed to schedule test run: {resp['data']}")


@mcp.tool("clone_test_run")
async def clone_test_run(input: CloneTestRunInput) -> ClonedTestRunOutput:
    """
    Clone an existing test run.

    Args:
        input (CloneTestRunInput): Input containing details for cloning a test run. The id field in the input is used to identify the test run to be cloned.

    Returns:
        ClonedTestRunOutput: Output containing details of the newly cloned test run.
    """
    payload = input.model_dump(exclude={"token"}, mode="json", exclude_none=True)
    resp = await client.post_backend(
        f"/testrun/v1/cloneTestRun",
        payload,
    )
    if resp["status_code"] == 200:
        data = resp["data"]
        return ClonedTestRunOutput(
            id=data.get("id"),
            testRunName=data.get("testRunName"),
            uniqueKey=data.get("uniqueKey"),
        )
    else:
        raise Exception(f"Failed to clone test run: {resp['data']}")


@mcp.tool("create_element")
async def create_element(input: ElementCreationInput) -> ElementCreationOutput:
    """
    Create a new element.

    Args:
        input (ElementCreationInput): Input containing details for creating an element. The module in the input will be name of module and feature is UUID

    Returns:
        ElementCreationOutput: Output containing details of the created element.
    """
    payload = input.model_dump(exclude={"token"}, mode="json", exclude_none=True)
    print(f"Payload for creating element: {payload}")
    resp = await client.post_backend(
        f"/elements/v1",
        payload,
    )
    if resp["status_code"] == 200:
        data = resp["data"]
        return ElementCreationOutput(
            id=uuid.UUID(data.get("id", "")),
            name=str(data.get("name", "")),
            selector=str(data.get("selector", "")),
            createdBy=str(data.get("createdBy", "")),
        )
    else:
        raise Exception(
            f"Failed to create element: {resp['data']} with payload: {payload}"
        )


@mcp.tool("upload_datafile")
async def upload_datafile(input: UploadDataFileInput) -> DataFileUploadOutput:
    """
    Upload a CSV data file to the platform's data-files store (datafiles/v1/upload).

    Use this after generating and validating a CSV — see the /create-datafile skill.
    The returned `id` is what goes into a test case's `file_ids` list so the test case
    can reference the file's columns via {{data.<file>.<column>}} placeholders in its
    steps (e.g. performance test cases created via /performance-testing).

    Args:
        input (UploadDataFileInput): file_path (local CSV to upload), file_name
            (<=20 chars, server-enforced), project_id (falls back to plugin default),
            uploaded_by (plain display name, never email/UUID — same convention as
            save_claude_test_cases' created_by).

    Returns:
        DataFileUploadOutput: the created file's id, fileName, fileSize, and other metadata.
    """
    if not os.path.isfile(input.file_path):
        raise ValueError(f"CSV file not found at {input.file_path}")
    with open(input.file_path, "rb") as fh:
        content = fh.read()

    data = {
        "projectId": _project(input.project_id),
        "fileName": input.file_name,
        # Field name follows the Java DTO's literal casing (DataFilesDto.UploadedBy) —
        # confirmed correct against a real upload to a live dev backend.
        "UploadedBy": input.uploaded_by,
        "needToUpdate": str(input.need_to_update).lower(),
    }
    files = {"file": (os.path.basename(input.file_path), content, "text/csv")}

    resp = await client.post_backend_multipart("/datafiles/v1/upload", data, files)
    if resp["status_code"] != 200:
        raise Exception(f"Failed to upload data file: {resp['data']}")
    return DataFileUploadOutput(**resp["data"])


@mcp.tool()
async def fetch_element_details_by_id(element_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch UI element details for one or more element IDs in parallel.

    Pass a list of element IDs (UUIDs). All requests are made concurrently.
    Call this when a failure trace references element IDs to resolve their names
    and selectors. Returns one result object per ID; errors are returned inline
    rather than raising so that partial results are still usable.
    """

    async def _fetch_one(element_id: str) -> dict[str, Any]:
        resp = await client.get_backend(f"/elements/v1/{element_id}")
        if resp["status_code"] != 200:
            if resp["status_code"] == 500 or "JWT" in str(resp["data"]):
                return {
                    "id": element_id,
                    "error": f"Cannot fetch element {element_id}: invalid token or server error",
                }
            return {
                "id": element_id,
                "error": f"Failed to fetch element details: {resp['data']}",
            }
        el = resp["data"]
        return {
            "id": el.get("id"),
            "name": el.get("name"),
            "selector": el.get("selector"),
            "module": el.get("module"),
            "feature": el.get("feature"),
            "testMode": el.get("testMode"),
        }

    return list(await asyncio.gather(*[_fetch_one(eid) for eid in element_ids]))


@mcp.tool("get_element_details_by_name_or_unique_key")
async def get_element_details_by_name_or_unique_key(
    input: ModuleIdByNameOrUniqueKeyInput,
) -> ElementOutputResponse | None:
    """
    Get element ID by name or unique key.

    Args:
        input (ModuleIdByNameOrUniqueKeyInput): Input containing details for retrieving element ID. The identifier field in the input is used to search for the element by name or unique key.

    Returns:
        ElementOutputResponse: The element that matches the provided name or unique key.
    """
    project_id = _project(input.projectId)
    resp = await client.get_backend(
        f"/elements/v1?projectId={project_id}&query={input.identifier}&testMode=&createdBy=&moduleName=&featureName=&status=false&deleted=false&page=0&size=100",
    )
    if resp["status_code"] == 200:
        mods = resp["data"].get("content", [])
        if len(mods) == 0:
            raise Exception(
                f"No Element found with name or unique key: {input.identifier}"
            )
        elif len(mods) == 1:
            return ElementOutputResponse(
                id=uuid.UUID(mods[0].get("id")),
                name=mods[0].get("name"),
                uniqueKey=mods[0].get("uniqueKey"),
                selector=mods[0].get("selector"),
            )
        else:
            for mod in mods:
                if (
                    mod.get("name").lower() == input.identifier.lower()
                    or mod.get("uniqueKey").lower() == input.identifier.lower()
                ):
                    return ElementOutputResponse(
                        id=uuid.UUID(mod.get("id")),
                        name=mod.get("name"),
                        uniqueKey=mod.get("uniqueKey"),
                        selector=mod.get("selector"),
                    )
    else:
        raise Exception(f"Failed to retrieve Elements: {resp['data']}")


@mcp.tool("update_element")
async def update_element(input: ElementUpdateInput) -> str:
    """
    Update an existing element.

    Args:
        input (ElementUpdateInput): Input containing details for updating an element. The module in the input will be name of module and feature is UUID

    Returns:
        str: A message indicating the successful update of the element.
    """
    payload = input.model_dump(exclude={"token"}, mode="json", exclude_none=True)
    resp = await client.patch_backend(
        f"/elements/v1/{input.id}",
        payload,
    )
    if resp["status_code"] == 200:
        return f"Element with identifier '{input.id}' updated successfully"
    else:
        raise Exception(f"Failed to update element: {resp['data']}")


@mcp.tool("wait_for_test_execution_completion")
async def wait_for_test_execution_completion(
    input: WaitForCaseExecutionInput,
) -> TestCaseResultOutput:
    """
    Wait for the completion of a test case execution by its ID. This tool will poll the backend until the test case execution completes.

    IMPORTANT: DO NOT call this tool if the test case execution is not yet started i.e. run_test_case tool does not return a result yet.

    Args:
        input (WaitForCaseExecutionInput): Input containing details for waiting for execution of a test case.

    Returns:
        TestCaseResultOutput: The result of the test case execution.

    """
    temp = 0
    while True:
        resp = await client.get_backend(
            f"/testcases/v1/get-testcase-result/{input.testCaseId}",
        )
        if resp["status_code"] == 200:
            data = resp["data"]
            if data:
                status = data[-1].get("status")
                if len(data) > 1 and status == "In Progress":
                    status = data[0].get("status")
                    logs = data[0].get("traceStack", "")
                else:
                    logs = data[-1].get("traceStack", "")
                if status in ("Pass", "Fail", "Abort"):
                    return TestCaseResultOutput(
                        testCaseId=input.testCaseId,
                        status=status,
                        executeTime=data[-1].get("executeTime"),
                        traceStack=logs,
                    )
            await asyncio.sleep(10)  # wait for 10 seconds before polling again
        else:
            raise Exception(f"Failed to retrieve test execution status: {resp['data']}")
        temp += 1
        if temp > 30:  # timeout after 5 minutes
            raise Exception(
                f"Timeout waiting for test case execution to complete for testCaseId: {input.testCaseId} and response is {resp['data']}"
            )


@mcp.tool("get_defects_with_filters")
async def get_defects_with_filters(
    input: GetDefectOrTaskDetailsByNameOrUniqueKeyInput,
) -> List[GetDefectOrTaskDetailsOutput]:
    """
    Retrieves defects using filters like name, unique key, priority, status, state, assignedTo, assignedBy, and createdBy.
    """
    params = {
        "searchTerm": input.identifier,
        "priority": input.priority,
        "status": input.status,
        "state": input.state,
        "assignedTo": input.assignedTo,
        "assignedBy": input.assignedBy,
        "createdBy": input.createdBy,
        "deleted": "false",
    }
    # Do not send optional filters that are not provided.
    params = {k: v for k, v in params.items() if v not in (None, "")}

    resp = await client.get_backend(
        f"/api/issues/allWithPagination/{_project(input.projectId)}/0/100",
        params=params,
    )
    if resp["status_code"] == 200:
        defects = resp["data"].get("content", [])
        if len(defects) == 0:
            if input.identifier:
                raise Exception(
                    f"No defect found with name or unique key: {input.identifier}"
                )
            raise Exception("No defect found for the provided filters")
        else:
            return [GetDefectOrTaskDetailsOutput(**defect) for defect in defects]

    else:
        raise Exception(f"Failed to retrieve defects: {resp['data']}")
