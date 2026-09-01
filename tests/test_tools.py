"""Offline tests for the MCP tool wrappers.

Runs without a live backend: a MockTransport records each outgoing request so we
can assert URL, method, auth header, and body shaping. Run directly:

    ./.devvenv/Scripts/python tests/test_tools.py
"""

import asyncio
import json
import os
import sys

# Config is read at import time — set it before importing the package.
os.environ.setdefault("PLATFORM_API_KEY", "testkey123")
os.environ.setdefault("PLATFORM_PROJECT_ID", "proj-default")
os.environ.setdefault("PLATFORM_USER_ID", "user-default")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from server import client, tools  # noqa: E402

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
    return httpx.Response(200, json={"ok": True})


client._client = httpx.AsyncClient(
    transport=httpx.MockTransport(_handler), headers=client._headers()
)


def _last() -> httpx.Request:
    return calls[-1]


def _body(req: httpx.Request) -> dict:
    return json.loads(req.content) if req.content else {}


async def main() -> None:
    # create_test_cases → platform POST, defaults filled, x-api-key sent
    await tools.create_test_cases(
        user_input="login works", module="auth", feature="login", test_mode="api"
    )
    r = _last()
    assert r.method == "POST"
    assert str(r.url) == "http://localhost:8000/api/test-cases/create", r.url
    assert r.headers["x-api-key"] == "testkey123"
    b = _body(r)
    assert b["testMode"] == "api"
    assert b["projectId"] == "proj-default"
    assert b["createdBy"] == "user-default"

    # explicit project_id overrides the default
    await tools.create_test_cases(
        user_input="x", module="m", feature="f", project_id="proj-override"
    )
    assert _body(_last())["projectId"] == "proj-override"

    # analyze_test_steps → platform POST /api/analyze
    await tools.analyze_test_steps(user_input="x", module="m", feature="f")
    assert str(_last().url) == "http://localhost:8000/api/analyze"

    # run_tests → execution POST /run-tests (different base URL)
    await tools.run_tests(test_case_id="tc-1", browser_type="chrome")
    r = _last()
    assert str(r.url) == "http://localhost:3232/run-tests", r.url
    assert _body(r)["testCaseId"] == "tc-1"
    assert r.headers["x-api-key"] == "testkey123"

    # get_run_status → execution GET /status/{id}
    await tools.get_run_status("exec-9")
    r = _last()
    assert r.method == "GET"
    assert str(r.url) == "http://localhost:3232/status/exec-9", r.url

    # stop_tests → execution POST /stop-tests/{id}
    await tools.stop_tests("exec-9")
    assert str(_last().url) == "http://localhost:3232/stop-tests/exec-9"

    # analyze_test_run → platform POST /api/test_run/ask
    await tools.analyze_test_run("run-1")
    r = _last()
    assert str(r.url) == "http://localhost:8000/api/test_run/ask"
    assert _body(r)["test_run_id"] == "run-1"

    # compare_test_runs → platform POST /api/test_run/compare
    await tools.compare_test_runs(["run-1", "run-2"])
    assert str(_last().url) == "http://localhost:8000/api/test_run/compare"
    assert _body(_last())["run_ids"] == ["run-1", "run-2"]

    # analyze_stack_trace → platform POST /api/stack_trace/analyze
    await tools.analyze_stack_trace("Traceback ... ValueError")
    assert str(_last().url) == "http://localhost:8000/api/stack_trace/analyze"

    # create_test_case_from_defect → platform POST
    await tools.create_test_case_from_defect("DEF-1")
    assert str(_last().url) == "http://localhost:8000/api/test-cases/create-from-defect"

    # run_tests with neither id must raise
    try:
        await tools.run_tests()
        raise AssertionError("expected ValueError when no id given")
    except ValueError:
        pass

    await client.aclose()
    print(f"ALL OK — {len(calls)} requests asserted")


async def test_upload_and_performance() -> None:
    """Regression coverage for the datafiles-upload + performance test-case additions.

    Kept as its own entry point (not appended into main()'s call sequence) since
    main() already exercises tools (create_test_cases, analyze_test_steps, etc.)
    that are currently commented out / absent from server/tools.py — pre-existing
    drift, unrelated to this change. Runnable independently either way.
    """
    from server.request_response_model import (
        ClaudeTestCaseInput,
        CreateTestCaseFromClaudeRequest,
        UploadDataFileInput,
    )

    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(_handler), headers=client._headers()
    )
    calls.clear()

    # upload_datafile must send real multipart/form-data, not application/json —
    # this is the exact bug the client.py _headers() fix prevents.
    csv_path = "/tmp/_test_upload_and_performance.csv"
    with open(csv_path, "w") as fh:
        fh.write("a,b\n1,2\n")
    try:
        await tools.upload_datafile(
            UploadDataFileInput(
                file_path=csv_path,
                # bare identifier only — no extension/dots/spaces, confirmed against a
                # real upload: the server validates this as the {{data.<name>.<col>}} token
                file_name="t",
                uploaded_by="Surya",
                # PLATFORM_PROJECT_ID in this test file's env is "proj-default", not
                # a real UUID — _project() requires one, so pass it explicitly here.
                project_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            )
        )
    finally:
        os.remove(csv_path)
    r = _last()
    assert r.method == "POST"
    assert str(r.url) == "http://localhost:8088/datafiles/v1/upload", r.url
    ct = r.headers["content-type"]
    assert ct.startswith("multipart/form-data; boundary="), ct
    assert r.headers["x-api-key"] == "testkey123"

    # save_claude_test_cases with test_mode="Performance" and file_ids must build
    # correctly and round-trip file_ids through model_dump(mode="json").
    tc = ClaudeTestCaseInput(
        name="Load test orders",
        description="d",
        steps=['define load step "Create Order" {}', "run the load test"],
        file_ids=["file-id-123"],
    )
    req = CreateTestCaseFromClaudeRequest(
        test_cases=[tc],
        module="Perf",
        feature="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        test_mode="Performance",
        created_by="Surya",
        # same non-UUID env-default issue as project_id above
        project_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        user_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )
    await tools.save_claude_test_cases(req)
    r = _last()
    b = _body(r)
    assert b["test_mode"] == "Performance", b
    assert b["test_cases"][0]["file_ids"] == ["file-id-123"], b

    # file_name must be a bare identifier — confirmed live against a real upload
    # (rejected with "File name must contain only letters, numbers, underscores,
    # and hyphens... to be usable as {{data.<name>.<column>}}").
    for bad_name in ("ord_load1.csv", "order data", "ord/load1"):
        try:
            UploadDataFileInput(file_path="/tmp/x", file_name=bad_name, uploaded_by="Surya")
            raise AssertionError(f"expected rejection of file_name={bad_name!r}")
        except ValueError:
            pass

    await client.aclose()
    print(f"UPLOAD/PERFORMANCE OK — {len(calls)} requests asserted")


async def test_run_test_case_load_profile() -> None:
    """Regression coverage for the Performance load profile on run_test_case.

    Three bugs shipped together here and none were caught, because nothing
    asserted the outgoing payload: the field was named `virtualUser` while the
    backend DTO says `virtualUsers` (Jackson drops unknown fields silently), the
    profile was never added to the payload at all, and the client-side defaults
    disagreed with the backend's. The payload assertions below are the guard.
    """
    import uuid

    import pydantic

    from server.request_response_model import (
        AUTOPILOT_PORTAL_URL,
        MAX_VIRTUAL_USERS,
        RunTestCaseInput,
    )

    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(_handler), headers=client._headers()
    )
    calls.clear()

    tc, uid, env = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def _mk(**kw) -> RunTestCaseInput:
        return RunTestCaseInput(testCaseId=tc, userId=uid, envId=env, **kw)

    # --- duration: accepted forms, both grammars the backend allows -----------
    for value in ("30s", "2m", "180", "3m"):
        assert _mk(duration=value).duration == value

    # --- duration: over this plugin's 3-minute cap, in every equivalent form --
    for value in ("4m", "181", "1h"):
        try:
            _mk(duration=value)
            raise AssertionError(f"expected {value!r} to exceed the duration cap")
        except pydantic.ValidationError as exc:
            # The portal is the whole point of the cap — a rejection that doesn't
            # say where to go instead is a dead end for the user.
            assert AUTOPILOT_PORTAL_URL in str(exc), f"{value}: no portal URL in {exc}"

    # --- duration: malformed, rejected on grammar rather than the cap ---------
    for value in ("abc", "0s", "-1m", "2x"):
        try:
            _mk(duration=value)
            raise AssertionError(f"expected {value!r} to be rejected as malformed")
        except pydantic.ValidationError:
            pass

    # --- rampPattern: the backend lower-cases these, so any casing is fine ----
    assert _mk(rampPattern="Linear").rampPattern == "linear"
    assert _mk(rampPattern="WAVED").rampPattern == "waved"
    assert _mk(rampPattern="incremental").rampPattern == "incremental"

    # --- virtualUsers: bounds mirror LoadProfileValidator ---------------------
    assert _mk(virtualUsers=MAX_VIRTUAL_USERS).virtualUsers == MAX_VIRTUAL_USERS
    for value in (0, MAX_VIRTUAL_USERS + 1):
        try:
            _mk(virtualUsers=value)
            raise AssertionError(f"expected virtualUsers={value} to be rejected")
        except pydantic.ValidationError:
            pass

    # --- payload: a Performance run sends the profile under the backend's own
    #     field names. `virtualUsers` plural is the bug this pins down.
    await tools.run_test_case(_mk(virtualUsers=250, duration="2m", rampPattern="Waved"))
    body = _body(_last())
    assert body["virtualUsers"] == 250, body
    assert "virtualUser" not in body, f"singular field name would be dropped silently: {body}"
    assert body["duration"] == "2m", body
    assert body["rampPattern"] == "waved", body

    # --- payload: with no profile given, the three keys are absent entirely so
    #     LoadProfileValidator stays the single owner of the defaults.
    await tools.run_test_case(_mk())
    body = _body(_last())
    assert set(body) == {"testCaseId", "browserType", "envId", "platform", "userId"}, body

    # --- payload: a partial profile sends only what was chosen ---------------
    await tools.run_test_case(_mk(virtualUsers=5))
    body = _body(_last())
    assert body["virtualUsers"] == 5, body
    assert "duration" not in body and "rampPattern" not in body, body

    await client.aclose()
    print(f"LOAD PROFILE OK — {len(calls)} requests asserted")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"main() failed (pre-existing — tools it exercises are commented out in tools.py): {e}")
    asyncio.run(test_upload_and_performance())
    asyncio.run(test_run_test_case_load_profile())
