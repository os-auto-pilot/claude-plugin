"""Offline tests for the MCP tool wrappers.

Runs without a live backend: a MockTransport records each outgoing request so we
can assert URL, method, auth header, and body shaping.

    uv run --with-requirements server/requirements.txt --python ">=3.10" -m pytest tests/test_tools.py -q
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

# Config is read at import time — set it before importing the package.
os.environ.setdefault("PLATFORM_API_KEY", "testkey123")
os.environ.setdefault("PLATFORM_PROJECT_ID", "3fa85f64-5717-4562-b3fc-2c963f66afa6")
os.environ.setdefault("PLATFORM_USER_ID", "3fa85f64-5717-4562-b3fc-2c963f66afa6")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import pydantic  # noqa: E402
import pytest  # noqa: E402

from server import client, tools  # noqa: E402
from server.request_response_model import (  # noqa: E402
    AUTOPILOT_PORTAL_URL,
    ClaudeTestCaseInput,
    CreateTestCaseFromClaudeRequest,
    MAX_VIRTUAL_USERS,
    RunTestCaseInput,
    UploadDataFileInput,
)

PROJECT_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
USER_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

calls: list[httpx.Request] = []


def _handler(request: httpx.Request) -> httpx.Response:
    calls.append(request)
    if str(request.url).endswith("/datafiles/v1/upload"):
        return httpx.Response(
            200,
            json={
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "fileName": "t.csv",
                "fileSize": 8,
                "uploadedBy": "Surya",
            },
        )
    if "/ordered-test-cases" in str(request.url):
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "testRunName": "Smoke",
                        "status": "PASS",
                        "featureName": "Login",
                        "moduleName": "Auth",
                        "severity": "High",
                        "testMode": "Web",
                        "author": "Surya",
                    }
                ],
                "last": True,
            },
        )
    return httpx.Response(200, json={"ok": True})


@pytest.fixture(autouse=True)
def mock_client():
    """Point the shared httpx client at a recording mock transport."""
    calls.clear()
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(_handler),
        headers=client._headers(),
    )
    yield
    # Sync close — pytest-asyncio runs async tests but fixture teardown is sync.
    if client._client is not None and not client._client.is_closed:
        # Leave client open for the next test; replaced on next fixture setup.
        pass


def _last() -> httpx.Request:
    return calls[-1]


def _body(req: httpx.Request) -> dict:
    return json.loads(req.content) if req.content else {}


async def test_create_test_case_from_defect_posts_platform_payload():
    await tools.create_test_case_from_defect("DEF-1")
    r = _last()
    assert r.method == "POST"
    assert str(r.url) == "http://localhost:8000/api/test-cases/create-from-defect"
    assert r.headers["x-api-key"] == "testkey123"
    b = _body(r)
    assert b["defectId"] == "DEF-1"
    assert b["projectId"] == PROJECT_ID
    assert b["userId"] == USER_ID


async def test_create_test_case_from_defect_project_override():
    override = uuid.UUID("11111111-1111-1111-1111-111111111111")
    await tools.create_test_case_from_defect("DEF-2", project_id=override)
    assert _body(_last())["projectId"] == str(override)


async def test_fetch_test_run_results_paginates_backend():
    result = await tools.fetch_test_run_results("run-abc")
    r = _last()
    assert r.method == "GET"
    assert str(r.url).startswith(
        "http://localhost:8088/testrun/v1/run-abc/ordered-test-cases"
    )
    assert r.headers["x-api-key"] == "testkey123"
    assert result["run_name"] == "Smoke"
    assert result["pass"] == 1


async def test_upload_datafile_sends_multipart():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write("a,b\n1,2\n")
        csv_path = fh.name
    try:
        await tools.upload_datafile(
            UploadDataFileInput(
                file_path=csv_path,
                file_name="t",
                uploaded_by="Surya",
                project_id=uuid.UUID(PROJECT_ID),
            )
        )
    finally:
        os.remove(csv_path)

    r = _last()
    assert r.method == "POST"
    assert str(r.url) == "http://localhost:8088/datafiles/v1/upload"
    ct = r.headers["content-type"]
    assert ct.startswith("multipart/form-data; boundary="), ct
    assert r.headers["x-api-key"] == "testkey123"


async def test_save_claude_test_cases_performance_file_ids():
    tc = ClaudeTestCaseInput(
        name="Load test orders",
        description="d",
        steps=['define load step "Create Order" {}', "run the load test"],
        file_ids=["file-id-123"],
    )
    req = CreateTestCaseFromClaudeRequest(
        test_cases=[tc],
        module="Perf",
        feature=uuid.UUID(PROJECT_ID),
        test_mode="Performance",
        created_by="Surya",
        project_id=uuid.UUID(PROJECT_ID),
        user_id=uuid.UUID(USER_ID),
    )
    await tools.save_claude_test_cases(req)
    r = _last()
    b = _body(r)
    assert str(r.url) == "http://localhost:8000/api/test-cases/create-from-claude"
    assert b["test_mode"] == "Performance"
    assert b["test_cases"][0]["file_ids"] == ["file-id-123"]


def test_upload_datafile_rejects_bad_file_names():
    for bad_name in ("ord_load1.csv", "order data", "ord/load1"):
        with pytest.raises(ValueError):
            UploadDataFileInput(file_path="/tmp/x", file_name=bad_name, uploaded_by="Surya")


async def test_run_test_case_load_profile_fields():
    tc_id, uid, env_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def _mk(**kw) -> RunTestCaseInput:
        return RunTestCaseInput(testCaseId=tc_id, userId=uid, envId=env_id, **kw)

    for value in ("30s", "2m", "180", "3m"):
        assert _mk(duration=value).duration == value

    for value in ("4m", "181", "1h"):
        with pytest.raises(pydantic.ValidationError) as exc:
            _mk(duration=value)
        assert AUTOPILOT_PORTAL_URL in str(exc.value)

    for value in ("abc", "0s", "-1m", "2x"):
        with pytest.raises(pydantic.ValidationError):
            _mk(duration=value)

    assert _mk(rampPattern="Linear").rampPattern == "linear"
    assert _mk(rampPattern="WAVED").rampPattern == "waved"
    assert _mk(virtualUsers=MAX_VIRTUAL_USERS).virtualUsers == MAX_VIRTUAL_USERS

    for value in (0, MAX_VIRTUAL_USERS + 1):
        with pytest.raises(pydantic.ValidationError):
            _mk(virtualUsers=value)

    calls.clear()
    await tools.run_test_case(_mk(virtualUsers=250, duration="2m", rampPattern="Waved"))
    body = _body(_last())
    assert str(_last().url) == "http://localhost:8088/testcases/v1/run-test-case"
    assert body["virtualUsers"] == 250
    assert "virtualUser" not in body
    assert body["duration"] == "2m"
    assert body["rampPattern"] == "waved"

    calls.clear()
    await tools.run_test_case(_mk())
    body = _body(_last())
    assert set(body) == {"testCaseId", "browserType", "envId", "platform", "userId"}

    calls.clear()
    await tools.run_test_case(_mk(virtualUsers=5))
    body = _body(_last())
    assert body["virtualUsers"] == 5
    assert "duration" not in body and "rampPattern" not in body
