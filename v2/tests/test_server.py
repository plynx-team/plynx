"""Tests for the FastAPI server skeleton (Task 0.9)."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner
from plynx.api_models import (
    CleanResponse,
    NodeLogEvent,
    NodePosition,
    OpEntry,
    RunEvent,
    RunListResponse,
    RunState,
    RunStatus,
    RunStatusData,
    UploadResponse,
    ValidateWorkflowResponse,
    Viewport,
    WorkflowDocument,
    WorkflowInputSpec,
    WorkflowLayout,
    WorkflowListItem,
)
from plynx.cas import BlobStore
from plynx.cli import main
from plynx.server import (
    NonLoopbackHostError,
    create_app,
    is_loopback_host,
    run_server,
    validate_host,
)
from plynx.store import RunStore
from plynx.store.run_store import generate_run_id
from plynx_sdk.protocol import ResultFileValue, ResultManifest
from pydantic import TypeAdapter

from tests.test_validator import EXAMPLE_WORKFLOW

_EVENT_ADAPTER: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)


@dataclass(frozen=True)
class SseFrame:
    """Parsed Server-Sent Event frame."""

    event_id: int | None
    event_type: str
    data: RunEvent


def _parse_sse_stream(raw_body: str) -> list[SseFrame]:
    frames: list[SseFrame] = []
    for block in raw_body.split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        event_id: int | None = None
        event_type = "message"
        data_lines: list[str] = []
        for line in lines:
            if line.startswith("id:"):
                event_id = int(line.partition(":")[2].strip())
            elif line.startswith("event:"):
                event_type = line.partition(":")[2].strip()
            elif line.startswith("data:"):
                data_lines.append(line.partition(":")[2].strip())
        if data_lines:
            raw_json = "\n".join(data_lines)
            parsed_event: RunEvent = _EVENT_ADAPTER.validate_python(json.loads(raw_json))
            frames.append(SseFrame(event_id=event_id, event_type=event_type, data=parsed_event))
    return frames


def test_health_and_not_found(tmp_path: Path) -> None:
    """GET /health returns 200 ok; GET /runs/{unknown} returns 404 ApiErrorResponse."""
    app = create_app(tmp_path)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok", "version": "2.0.0"}

            v1_health = await client.get("/api/v1/health")
            assert v1_health.status_code == 200
            assert v1_health.json() == {"status": "ok", "version": "2.0.0"}

            missing = await client.get("/runs/nonexistent")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "run_not_found"

    asyncio.run(_check())


def test_cli_run_in_other_process_stream_and_last_event_id(tmp_path: Path) -> None:
    """CLI run in another process streams ordered events and supports Last-Event-ID."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    store = RunStore(tmp_path)
    app = create_app(tmp_path)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from plynx.cli import main; main()",
            "run",
            "--answer",
            "pick.cp_0=foo",
            str(wf_path),
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10.0
        run_id: str | None = None
        while time.monotonic() < deadline:
            runs = store.list_runs()
            if runs:
                run_id = runs[0].id
                break
            time.sleep(0.01)
        assert run_id is not None, "CLI subprocess did not create a run in time"

        async def _stream_and_reconnect(target_run_id: str) -> None:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(f"/runs/{target_run_id}/stream")
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                all_frames = _parse_sse_stream(resp.text)

                proc.wait(timeout=10)
                assert proc.returncode == 0

                recorded_events = store.event_log(target_run_id).read_after(0)
                assert len(all_frames) == len(recorded_events)
                assert [f.event_id for f in all_frames] == [e.seq for e in recorded_events]
                assert [f.event_type for f in all_frames] == [e.type for e in recorded_events]
                assert [f.data for f in all_frames] == recorded_events

                cutoff_seq = 3
                reconnect_resp = await client.get(
                    f"/runs/{target_run_id}/stream",
                    headers={"Last-Event-ID": str(cutoff_seq)},
                )
                assert reconnect_resp.status_code == 200
                later_frames = _parse_sse_stream(reconnect_resp.text)
                expected_later = [e for e in recorded_events if (e.seq or 0) > cutoff_seq]
                assert len(later_frames) == len(expected_later)
                assert [f.data for f in later_frames] == expected_later

                state_resp = await client.get(f"/runs/{target_run_id}")
                assert state_resp.status_code == 200
                state = RunState.model_validate(state_resp.json())
                assert state.status == RunStatus.SUCCESS

        asyncio.run(_stream_and_reconnect(run_id))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_post_runs_and_stream(tmp_path: Path) -> None:
    """POST /runs starts a run whose events stream via GET /runs/{id}/stream."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    shutil.copy(EXAMPLE_WORKFLOW, wf_dir / "foo_or_woo.yaml")

    app = create_app(tmp_path)

    async def _run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/runs",
                json={"workflow_path": "workflows/foo_or_woo.yaml", "inputs": {}},
            )
            assert create_resp.status_code == 201, create_resp.text
            run_id = create_resp.json()["run_id"]

            store = RunStore(tmp_path)

            async def _answer_when_open() -> None:
                deadline = time.monotonic() + 10.0
                while time.monotonic() < deadline:
                    cp = await asyncio.to_thread(store.get_checkpoint, run_id, "pick", "cp_0")
                    if cp is not None:
                        await asyncio.to_thread(
                            store.answer_checkpoint,
                            run_id,
                            "pick",
                            "cp_0",
                            "foo",
                        )
                        return
                    await asyncio.sleep(0.02)

            answer_task = asyncio.create_task(_answer_when_open())
            try:
                stream_resp = await client.get(f"/runs/{run_id}/stream")
            finally:
                await answer_task
            assert stream_resp.status_code == 200
            frames = _parse_sse_stream(stream_resp.text)
            assert frames
            event_frames = [f for f in frames if f.event_type != "node_log"]
            assert event_frames
            assert event_frames[0].event_id == 1
            assert [f.event_id for f in event_frames] == list(range(1, len(event_frames) + 1))

            state_resp = await client.get(f"/runs/{run_id}")
            assert state_resp.status_code == 200
            state = RunState.model_validate(state_resp.json())
            assert state.status == RunStatus.SUCCESS

    asyncio.run(_run())


def test_server_returns_built_index_html_at_root(tmp_path: Path) -> None:
    """GET / returns the built UI index.html from packages/plynx/src/plynx/static/."""
    from plynx.server.app import DEFAULT_STATIC_DIR

    static_dir = DEFAULT_STATIC_DIR
    if not (static_dir / "index.html").is_file():
        static_dir = tmp_path / "static"
        static_dir.mkdir(parents=True)
        (static_dir / "index.html").write_text(
            "<!doctype html><html><head><title>PLynx v2</title></head>"
            '<body><div id="root"></div></body></html>\n',
            encoding="utf-8",
        )

    app = create_app(tmp_path, static_dir=static_dir)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "text/html" in resp.headers.get("content-type", "")
            assert '<div id="root"></div>' in resp.text
            assert "PLynx v2" in resp.text

    asyncio.run(_check())


def test_read_ops_endpoint(tmp_path: Path) -> None:
    """GET /ops and GET /api/v1/ops return validated OpEntry list."""
    app = create_app(tmp_path)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ops")
            assert resp.status_code == 200
            ops_data = resp.json()
            assert isinstance(ops_data, list)
            assert len(ops_data) > 0
            validated = [OpEntry.model_validate(item) for item in ops_data]
            assert any(op.id == "standard_io/demo:AskFooOrWoo" for op in validated)

            v1_resp = await client.get("/api/v1/ops")
            assert v1_resp.status_code == 200
            assert v1_resp.json() == ops_data

    asyncio.run(_check())


def test_read_workflows_and_workflow_by_path(tmp_path: Path) -> None:
    """GET /workflows and GET /workflows/{path} return validated models."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_file = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_file)

    # Layout sidecar
    sidecar = wf_dir / ".foo_or_woo.layout.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema": 1,
                "nodes": {"pick": {"x": 10.0, "y": 20.0}},
                "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.5},
            }
        ),
        encoding="utf-8",
    )

    app = create_app(tmp_path)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # List workflows
            list_resp = await client.get("/workflows")
            assert list_resp.status_code == 200
            items = [WorkflowListItem.model_validate(it) for it in list_resp.json()]
            assert len(items) == 1
            assert items[0].path == "workflows/foo_or_woo.yaml"
            assert items[0].name == "foo_or_woo"
            assert items[0].stage_count >= 1

            # Get workflow document
            doc_resp = await client.get("/workflows/workflows/foo_or_woo.yaml")
            assert doc_resp.status_code == 200
            doc = WorkflowDocument.model_validate(doc_resp.json())
            assert "pick" in doc.workflow.nodes
            assert doc.layout is not None
            assert doc.layout.nodes["pick"].x == 10.0
            assert doc.layout.viewport.zoom == 1.5

            # API v1 prefix
            v1_resp = await client.get("/api/v1/workflows/workflows/foo_or_woo.yaml")
            assert v1_resp.status_code == 200
            assert v1_resp.json() == doc_resp.json()

            # 404 for missing workflow
            missing_resp = await client.get("/workflows/workflows/nonexistent.yaml")
            assert missing_resp.status_code == 404
            assert missing_resp.json()["error"]["code"] == "workflow_not_found"

            # 400 for invalid workflow YAML
            bad_wf = wf_dir / "broken.yaml"
            bad_wf.write_text("not a yaml mapping: [1, 2, 3]\n", encoding="utf-8")
            bad_resp = await client.get("/workflows/workflows/broken.yaml")
            assert bad_resp.status_code == 400
            assert bad_resp.json()["error"]["code"] == "invalid_workflow"

            # 400 for path traversal outside workspace (via symlink)
            outside_target = tmp_path.parent / "outside.yaml"
            outside_target.write_text("version: 1\nnodes: {}\n", encoding="utf-8")
            outside_symlink = wf_dir / "outside_link.yaml"
            outside_symlink.symlink_to(outside_target)
            outside_resp = await client.get("/workflows/workflows/outside_link.yaml")
            assert outside_resp.status_code == 400
            assert outside_resp.json()["error"]["code"] == "invalid_workflow_path"

    asyncio.run(_check())


def test_workflow_inputs_unwired_with_stage_ids(tmp_path: Path) -> None:
    """GET /workflows/{path}/inputs lists unwired input ports with stage IDs."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_file = wf_dir / "unwired.yaml"
    # Echo node has 'text' required with no default, not wired here
    wf_file.write_text(
        """version: 1
name: test_unwired
stages:
  print_stage:
    title: "Print Stage"
nodes:
  echo_node:
    op: standard_io/demo:Echo
    stage: print_stage
    inputs: {}
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/workflows/workflows/unwired.yaml/inputs")
            assert resp.status_code == 200
            inputs = [WorkflowInputSpec.model_validate(it) for it in resp.json()]
            assert len(inputs) == 1
            assert inputs[0].node_id == "echo_node"
            assert inputs[0].name == "text"
            assert inputs[0].type == "str"
            assert inputs[0].required is True
            assert inputs[0].stage_id == "print_stage"

            # /api/v1 prefix
            v1_resp = await client.get("/api/v1/workflows/workflows/unwired.yaml/inputs")
            assert v1_resp.status_code == 200
            assert v1_resp.json() == resp.json()

    asyncio.run(_check())


def test_read_runs_pagination_and_get_run_prefix(tmp_path: Path) -> None:
    """GET /runs supports limit/cursor; GET /runs/{id} supports prefix and error codes."""
    store = RunStore(tmp_path)
    # Create 3 runs in store
    id1 = store.create_run(
        workflow_path="workflows/w1.yaml",
        workflow_bytes=b"version: 1\nnodes: {}\n",
        node_ids=[],
    )
    time.sleep(0.01)
    id2 = store.create_run(
        workflow_path="workflows/w2.yaml",
        workflow_bytes=b"version: 1\nnodes: {}\n",
        node_ids=[],
    )
    time.sleep(0.01)
    id3 = store.create_run(
        workflow_path="workflows/w3.yaml",
        workflow_bytes=b"version: 1\nnodes: {}\n",
        node_ids=[],
    )

    app = create_app(tmp_path)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Page 1: limit 2
            page1_resp = await client.get("/runs?limit=2")
            assert page1_resp.status_code == 200
            page1 = RunListResponse.model_validate(page1_resp.json())
            assert len(page1.runs) == 2
            assert page1.runs[0].id == id3
            assert page1.runs[1].id == id2
            assert page1.next_cursor == id2

            # Page 2: with cursor
            page2_resp = await client.get(f"/runs?limit=2&cursor={page1.next_cursor}")
            assert page2_resp.status_code == 200
            page2 = RunListResponse.model_validate(page2_resp.json())
            assert len(page2.runs) == 1
            assert page2.runs[0].id == id1
            assert page2.next_cursor is None

            # Get run with full ID
            r3_resp = await client.get(f"/runs/{id3}")
            assert r3_resp.status_code == 200
            r3_state = RunState.model_validate(r3_resp.json())
            assert r3_state.id == id3
            assert r3_state.workflow_path == "workflows/w3.yaml"

            # Get run with unique prefix (full timestamp plus part of hex suffix)
            prefix = id3[:-2]
            prefix_resp = await client.get(f"/runs/{prefix}")
            assert prefix_resp.status_code == 200
            prefix_state = RunState.model_validate(prefix_resp.json())
            assert prefix_state.id == id3

            # Ambiguous prefix (shared timestamp prefix) returns 409
            ambig_prefix = id3[:15]
            ambig_resp = await client.get(f"/runs/{ambig_prefix}")
            assert ambig_resp.status_code == 409
            assert ambig_resp.json()["error"]["code"] == "ambiguous_run_id"

            # 404 for unknown run
            missing_resp = await client.get("/runs/unknown_id_12345")
            assert missing_resp.status_code == 404
            assert missing_resp.json()["error"]["code"] == "run_not_found"

    asyncio.run(_check())


def test_run_control_answer_double_answer_and_approve(tmp_path: Path) -> None:
    """Run started over REST can be answered and approved; double-answer returns 409 conflict."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    shutil.copy(EXAMPLE_WORKFLOW, wf_dir / "foo_or_woo.yaml")

    staged_wf = wf_dir / "staged.yaml"
    staged_wf.write_text(
        """version: 1
name: staged_demo
stages:
  s1:
    title: "Stage 1"
    require_approval: true
  s2:
    title: "Stage 2"
    require_approval: false
nodes:
  n1:
    op: standard_io/demo:Echo
    stage: s1
    inputs:
      text: "hello"
  n2:
    op: standard_io/demo:Echo
    stage: s2
    inputs:
      text: $n1.text
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path)

    async def _test_checkpoint_and_approval() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Start checkpoint run
            create_resp = await client.post(
                "/runs",
                json={"workflow_path": "workflows/foo_or_woo.yaml", "inputs": {}},
            )
            assert create_resp.status_code == 201
            cp_run_id = create_resp.json()["run_id"]

            # Poll until checkpoint is available
            deadline = time.monotonic() + 10.0
            found_cp = False
            while time.monotonic() < deadline:
                state_resp = await client.get(f"/runs/{cp_run_id}")
                assert state_resp.status_code == 200
                cps = state_resp.json().get("checkpoints", [])
                if cps and cps[0]["checkpoint_id"] == "cp_0":
                    found_cp = True
                    break
                await asyncio.sleep(0.02)
            assert found_cp, "Checkpoint was not created in time"

            # First answer succeeds
            ans_resp = await client.post(
                f"/runs/{cp_run_id}/checkpoints/pick/cp_0/answer",
                json={"answer": "foo"},
            )
            assert ans_resp.status_code == 200
            assert ans_resp.json()["status"] == "ok"

            # Double-answer returns 409 conflict
            double_resp = await client.post(
                f"/runs/{cp_run_id}/checkpoints/pick/cp_0/answer",
                json={"answer": "woo"},
            )
            assert double_resp.status_code == 409
            assert double_resp.json()["error"]["code"] == "checkpoint_already_answered"

            # Wait for run to finish successfully
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                state_resp = await client.get(f"/runs/{cp_run_id}")
                if state_resp.json()["status"] == "SUCCESS":
                    break
                await asyncio.sleep(0.02)
            assert state_resp.json()["status"] == "SUCCESS"

            # 2. Start staged run with approval gate
            staged_create_resp = await client.post(
                "/runs",
                json={"workflow_path": "workflows/staged.yaml", "inputs": {}},
            )
            assert staged_create_resp.status_code == 201
            staged_run_id = staged_create_resp.json()["run_id"]

            # Poll until stage gate s1 is WAITING
            deadline = time.monotonic() + 10.0
            found_gate = False
            while time.monotonic() < deadline:
                state_resp = await client.get(f"/runs/{staged_run_id}")
                assert state_resp.status_code == 200
                gates = state_resp.json().get("stage_gates", {})
                if gates.get("s1", {}).get("status") == "WAITING":
                    found_gate = True
                    break
                await asyncio.sleep(0.02)
            assert found_gate, "Stage gate s1 was not WAITING in time"

            # Approve stage gate
            app_resp = await client.post(f"/runs/{staged_run_id}/stages/s1/approve")
            assert app_resp.status_code == 200
            assert app_resp.json()["status"] == "ok"

            # Double-approve returns 409 conflict
            double_app_resp = await client.post(f"/runs/{staged_run_id}/stages/s1/approve")
            assert double_app_resp.status_code == 409
            assert double_app_resp.json()["error"]["code"] == "stage_gate_already_approved"

            # Wait for staged run to finish successfully
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                state_resp = await client.get(f"/runs/{staged_run_id}")
                if state_resp.json()["status"] == "SUCCESS":
                    break
                await asyncio.sleep(0.02)
            assert state_resp.json()["status"] == "SUCCESS"

    asyncio.run(_test_checkpoint_and_approval())


def test_run_control_cancel_and_resume(tmp_path: Path) -> None:
    """POST /runs/{id}/cancel sets cancel_requested; POST /runs/{id}/resume resumes waiting run."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    shutil.copy(EXAMPLE_WORKFLOW, wf_dir / "foo_or_woo.yaml")

    store = RunStore(tmp_path)
    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Cancel
            create_resp = await client.post(
                "/runs",
                json={"workflow_path": "workflows/foo_or_woo.yaml", "inputs": {}},
            )
            run_id = create_resp.json()["run_id"]

            cancel_resp = await client.post(f"/runs/{run_id}/cancel")
            assert cancel_resp.status_code == 200
            assert cancel_resp.json()["status"] == "ok"
            assert store.is_cancel_requested(run_id) is True

            # 2. Resume waiting/failed run
            # Create a run in WAITING_FOR_USER state with an answered checkpoint
            w_id = store.create_run(
                workflow_path="workflows/foo_or_woo.yaml",
                workflow_bytes=(wf_dir / "foo_or_woo.yaml").read_bytes(),
                node_ids=["pick", "echo"],
            )
            store.update_run_status(w_id, RunStatus.WAITING_FOR_USER)
            store.create_checkpoint(w_id, "pick", "cp_0", "foo or woo?")
            store.answer_checkpoint(w_id, "pick", "cp_0", "foo")

            resume_resp = await client.post(f"/runs/{w_id}/resume")
            assert resume_resp.status_code == 200
            assert resume_resp.json()["run_id"] == w_id

            # Wait for resumed run to complete
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                state_resp = await client.get(f"/runs/{w_id}")
                if state_resp.json()["status"] == "SUCCESS":
                    break
                await asyncio.sleep(0.02)
            assert state_resp.json()["status"] == "SUCCESS"

            # Resuming an already SUCCESS run returns 409 conflict
            again_resp = await client.post(f"/runs/{w_id}/resume")
            assert again_resp.status_code == 409
            assert again_resp.json()["error"]["code"] == "run_not_resumable"

    asyncio.run(_test())


def test_node_logs_endpoint_and_sse_batching(tmp_path: Path) -> None:
    """REST logs endpoint supports offset; node_log batches under 50ms and history+stream=file."""
    store = RunStore(tmp_path)
    run_id = store.create_run(
        workflow_path="workflows/test.yaml",
        workflow_bytes=b"version: 1\nnodes: {}\n",
        node_ids=["worker"],
    )
    logs_dir = store.run_dir(run_id) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_file = logs_dir / "worker.stdout.log"

    initial_lines = [f"line {i}\n" for i in range(3000)]
    stdout_file.write_text("".join(initial_lines), encoding="utf-8")

    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Test REST endpoint with offset=0
            resp = await client.get(f"/runs/{run_id}/nodes/worker/logs/stdout?offset=0")
            assert resp.status_code == 200
            history_text = resp.text
            next_offset = int(resp.headers["X-Next-Offset"])
            assert next_offset == stdout_file.stat().st_size
            assert history_text.splitlines() == [f"line {i}" for i in range(3000)]

            # Test slice from byte 100
            resp_slice = await client.get(f"/runs/{run_id}/nodes/worker/logs/stdout?offset=100")
            assert resp_slice.status_code == 200
            expected_slice = "".join(initial_lines).encode("utf-8")[100:].decode("utf-8")
            assert resp_slice.text == expected_slice
            assert int(resp_slice.headers["X-Next-Offset"]) == next_offset

            # Test empty log
            resp_stderr = await client.get(f"/runs/{run_id}/nodes/worker/logs/stderr?offset=0")
            assert resp_stderr.status_code == 200
            assert resp_stderr.text == ""
            assert resp_stderr.headers["X-Next-Offset"] == "0"

            # Test invalid stream
            bad_stream = await client.get(f"/runs/{run_id}/nodes/worker/logs/invalid")
            assert bad_stream.status_code == 400
            assert bad_stream.json()["error"]["code"] == "invalid_stream"

            # 2. Test SSE streaming with log tailing
            store.update_run_status(run_id, RunStatus.RUNNING)

            async def _stream_consumer() -> list[SseFrame]:
                stream_resp = await client.get(
                    f"/runs/{run_id}/stream?log_offset={next_offset}",
                    timeout=20.0,
                )
                return _parse_sse_stream(stream_resp.text)

            stream_task = asyncio.create_task(_stream_consumer())
            # Allow consumer to connect
            await asyncio.sleep(0.05)

            # Write remaining 7,000 lines (3000..9999) in bursts
            with open(stdout_file, "a", encoding="utf-8") as f:
                for i in range(3000, 10000):
                    f.write(f"line {i}\n")
                    if i % 1000 == 0:
                        f.flush()
                        await asyncio.sleep(0.01)
                f.flush()

            await asyncio.sleep(0.1)
            # Finish run
            store.update_run_status(run_id, RunStatus.SUCCESS)
            store.event_log(run_id).append(
                "run_status",
                RunStatusData(run_id=run_id, status=RunStatus.SUCCESS),
            )

            frames = await stream_task
            log_frames = [f for f in frames if f.event_type == "node_log"]
            assert len(log_frames) > 0
            # 7000 lines produced bounded SSE frames (< 50 frames!)
            assert len(log_frames) <= 50

            # All node_log frames have no id
            for frame in log_frames:
                assert frame.event_id is None
                assert isinstance(frame.data, NodeLogEvent)

            # Extract lines from stream
            stream_lines: list[str] = []
            for frame in log_frames:
                assert isinstance(frame.data, NodeLogEvent)
                stream_lines.extend(frame.data.data.lines)

            # History plus stream equals the full file!
            history_lines = history_text.splitlines()
            combined_lines = history_lines + stream_lines
            assert len(combined_lines) == 10000
            assert combined_lines == [f"line {i}" for i in range(10000)]

    asyncio.run(_test())


def test_uploads_and_outputs_blob_download(tmp_path: Path) -> None:
    """POST /uploads saves file; uploaded path works as run input; blob download works."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_file = wf_dir / "read_and_write.yaml"
    wf_file.write_text(
        """version: 1
name: test_upload_pipeline
nodes:
  reader:
    op: standard_io/demo:ReadText
    inputs: {}
  writer:
    op: standard_io/demo:WriteText
    inputs:
      text: $reader.text
      filename: result.txt
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Reject path traversal uploads
            for bad_name in ("../../evil.sh", "/etc/passwd", "sub/../evil.txt"):
                bad_resp = await client.post(
                    "/uploads",
                    files={"file": (bad_name, b"evil", "text/plain")},
                )
                assert bad_resp.status_code == 400
                assert bad_resp.json()["error"]["code"] == "invalid_filename"

            # 2. Upload valid file
            file_bytes = b"Hello from uploaded file!\nLine 2.\n"
            upload_resp = await client.post(
                "/uploads",
                files={"file": ("sample.txt", file_bytes, "text/plain")},
            )
            assert upload_resp.status_code == 201
            up_data = UploadResponse.model_validate(upload_resp.json())
            assert up_data.path == ".plynx/uploads/sample.txt"
            saved_file = tmp_path / ".plynx" / "uploads" / "sample.txt"
            assert saved_file.is_file()
            assert saved_file.read_bytes() == file_bytes

            # 3. Use uploaded file path as run input
            create_resp = await client.post(
                "/runs",
                json={
                    "workflow_path": "workflows/read_and_write.yaml",
                    "inputs": {"reader.path": up_data.path},
                },
            )
            assert create_resp.status_code == 201
            run_id = create_resp.json()["run_id"]

            # Wait for run to succeed
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                state_resp = await client.get(f"/runs/{run_id}")
                assert state_resp.status_code == 200
                state = state_resp.json()
                if state["status"] in ("SUCCESS", "FAILED"):
                    break
                await asyncio.sleep(0.05)
            assert state["status"] == "SUCCESS", f"Run failed: {state.get('error')}"

            # 4. Blob download with media type
            download_resp = await client.get(f"/runs/{run_id}/nodes/writer/outputs/file")
            assert download_resp.status_code == 200
            assert "text/plain" in download_resp.headers.get("content-type", "")
            assert download_resp.content == file_bytes

            # Test 404 for unknown output
            missing_out = await client.get(f"/runs/{run_id}/nodes/writer/outputs/nonexistent")
            assert missing_out.status_code == 404
            assert missing_out.json()["error"]["code"] == "output_not_found"

    asyncio.run(_test())


def test_workflow_save_round_trip_and_validation(tmp_path: Path) -> None:
    """PUT /workflows/{path} keeps comments on unchanged save; rejects invalid workflows."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_file = wf_dir / "foo_or_woo.yaml"
    wf_file.write_text(
        """# Workflow comment
version: 1
name: foo_or_woo # inline name comment
nodes:
  pick:
    # node comment
    op: standard_io/demo:AskFooOrWoo
    inputs:
      prompt: "foo or woo?"
""",
        encoding="utf-8",
    )

    orig_bytes = wf_file.read_bytes()
    assert b"# Workflow comment" in orig_bytes

    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Fetch document via GET
            get_resp = await client.get("/workflows/workflows/foo_or_woo.yaml")
            assert get_resp.status_code == 200
            doc = WorkflowDocument.model_validate(get_resp.json())

            # 2. Save unchanged workflow with new layout sidecar
            doc.layout = WorkflowLayout(
                nodes={"pick": NodePosition(x=100.5, y=200.5)},
                viewport=Viewport(x=10.0, y=20.0, zoom=1.5),
            )
            put_resp = await client.put(
                "/workflows/workflows/foo_or_woo.yaml",
                json=doc.model_dump(mode="json", by_alias=True),
            )
            assert put_resp.status_code == 200

            # Verify byte-identical YAML file (comments kept!)
            saved_bytes = wf_file.read_bytes()
            assert saved_bytes == orig_bytes

            # Verify layout sidecar written
            sidecar = wf_dir / ".foo_or_woo.layout.json"
            assert sidecar.is_file()
            sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
            assert sidecar_data["schema"] == 1
            assert sidecar_data["nodes"]["pick"]["x"] == 100.5
            assert sidecar_data["viewport"]["zoom"] == 1.5

            # 3. Reject invalid workflow without touching the file
            current_bytes = wf_file.read_bytes()
            invalid_doc = doc.model_copy(deep=True)
            # Unknown op
            invalid_doc.workflow.nodes["pick"].op = "standard_io/demo:UnknownOp"

            invalid_resp = await client.put(
                "/workflows/workflows/foo_or_woo.yaml",
                json=invalid_doc.model_dump(mode="json", by_alias=True),
            )
            assert invalid_resp.status_code == 422
            assert invalid_resp.json()["error"]["code"] == "validation_failed"

            # File must be untouched!
            assert wf_file.read_bytes() == current_bytes

            # 4. Test POST /workflows/validate
            val_valid = await client.post(
                "/workflows/validate",
                json={"workflow": doc.workflow.model_dump(mode="json")},
            )
            assert val_valid.status_code == 200
            val_valid_res = ValidateWorkflowResponse.model_validate(val_valid.json())
            assert not any(i.severity == "error" for i in val_valid_res.issues)

            val_invalid = await client.post(
                "/workflows/validate",
                json={"workflow": invalid_doc.workflow.model_dump(mode="json")},
            )
            assert val_invalid.status_code == 200
            val_invalid_res = ValidateWorkflowResponse.model_validate(val_invalid.json())
            assert any(i.severity == "error" for i in val_invalid_res.issues)

    asyncio.run(_test())


def test_server_cors_dev_origin_only(tmp_path: Path) -> None:
    app = create_app(tmp_path, dev_mode=True)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Allowed dev origin: localhost:3000
            resp_local = await client.get("/health", headers={"Origin": "http://localhost:3000"})
            assert resp_local.status_code == 200
            assert resp_local.headers.get("access-control-allow-origin") == "http://localhost:3000"

            # 2. Allowed dev origin: 127.0.0.1:3000
            resp_loop = await client.get("/health", headers={"Origin": "http://127.0.0.1:3000"})
            assert resp_loop.status_code == 200
            assert resp_loop.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"

            # 3. Disallowed origin: evil.com receives no CORS header
            resp_evil = await client.get("/health", headers={"Origin": "http://evil.com"})
            assert resp_evil.status_code == 200
            assert "access-control-allow-origin" not in resp_evil.headers

            # 4. Preflight request from allowed origin
            preflight_ok = await client.options(
                "/runs",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert (
                preflight_ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
            )

            # 5. Preflight request from disallowed origin receives no CORS header
            preflight_evil = await client.options(
                "/runs",
                headers={
                    "Origin": "http://evil.com",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert "access-control-allow-origin" not in preflight_evil.headers

        # 6. Dev mode disabled: even dev origin gets no CORS header
        prod_app = create_app(tmp_path, dev_mode=False)
        prod_transport = httpx.ASGITransport(app=prod_app)
        async with httpx.AsyncClient(
            transport=prod_transport, base_url="http://testserver"
        ) as prod_client:
            resp_prod = await prod_client.get(
                "/health", headers={"Origin": "http://localhost:3000"}
            )
            assert resp_prod.status_code == 200
            assert "access-control-allow-origin" not in resp_prod.headers

    asyncio.run(_test())


def test_server_loopback_host_binding_refusal(tmp_path: Path) -> None:
    # 1. Allowed loopback interfaces
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("localhost") is True
    assert is_loopback_host("::1") is True
    assert is_loopback_host("127.0.0.42") is True
    assert validate_host("127.0.0.1") == "127.0.0.1"
    assert validate_host("localhost") == "localhost"
    assert validate_host("::1") == "::1"

    # 2. Refused non-loopback hosts
    assert is_loopback_host("0.0.0.0") is False
    assert is_loopback_host("192.168.1.100") is False
    assert is_loopback_host("example.com") is False
    assert is_loopback_host("::") is False

    with pytest.raises(NonLoopbackHostError, match=r"Binding to non-loopback host.*refused"):
        validate_host("0.0.0.0")

    with pytest.raises(NonLoopbackHostError, match=r"Binding to non-loopback host.*refused"):
        validate_host("192.168.1.100")

    # 3. create_app with non-loopback host raises
    with pytest.raises(NonLoopbackHostError):
        create_app(tmp_path, host="0.0.0.0")

    # create_app with loopback host succeeds
    valid_app = create_app(tmp_path, host="127.0.0.1")
    assert valid_app is not None

    # 4. run_server with non-loopback host raises
    with pytest.raises(NonLoopbackHostError):
        run_server(valid_app, host="0.0.0.0")

    # 5. CLI plynx ui --host 0.0.0.0 fails with parameter error
    runner = CliRunner()
    res = runner.invoke(main, ["ui", "--host", "0.0.0.0", "--no-browser"])
    assert res.exit_code != 0
    assert "refused" in res.output.lower() or "loopback" in res.output.lower()


def test_server_clean_endpoint(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()
    old_time = now - (20 * 86400)  # 20 days ago

    # Create unreferenced blob and old run blob
    sha_unreferenced, _ = blob_store.put_bytes(b"orphan-server-blob")
    sha_old_run_out, _ = blob_store.put_bytes(b"old-server-run-output")

    # Create old unpinned run in store
    old_run_id = generate_run_id(now=old_time)
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
            VALUES (?, 'wf.yaml', 'sha_wf', 'SUCCESS', ?, 0)
            """,
            (old_run_id, old_time),
        )
    old_run_dir = store.run_dir(old_run_id)
    n1_dir = old_run_dir / "nodes" / "n1"
    n1_dir.mkdir(parents=True, exist_ok=True)
    manifest = ResultManifest(
        status="SUCCESS",
        cache_key="key",
        cache_hit=False,
        started_at=old_time,
        finished_at=old_time,
        outputs={
            "out": ResultFileValue(
                sha256=sha_old_run_out,
                size_bytes=len(b"old-server-run-output"),
                media=None,
                filename="out.txt",
            )
        },
    )
    (n1_dir / "result.json").write_text(manifest.to_json(), encoding="utf-8")

    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Validation error on negative days
            neg_resp = await client.post("/clean", json={"days": -1})
            assert neg_resp.status_code == 422

            # 2. Dry run clean (14 days): identifies 1 run, 2 blobs
            dry_resp = await client.post("/clean", json={"days": 14, "dry_run": True})
            assert dry_resp.status_code == 200
            dry_data = CleanResponse.model_validate(dry_resp.json())
            assert dry_data.deleted_runs == 1
            assert dry_data.deleted_blobs == 2
            assert dry_data.reclaimed_bytes > 0

            # Verify files still exist after dry run
            assert old_run_dir.exists()
            assert blob_store.exists(sha_unreferenced)
            assert blob_store.exists(sha_old_run_out)

            # 3. Real clean on /api/v1/clean: deletes old run and unreferenced blobs
            real_resp = await client.post(
                "/api/v1/clean",
                json={"days": 14, "dry_run": False},
            )
            assert real_resp.status_code == 200
            real_data = CleanResponse.model_validate(real_resp.json())
            assert real_data.deleted_runs == 1
            assert real_data.deleted_blobs == 2
            assert real_data.reclaimed_bytes > 0

            # Verify files deleted from disk
            assert not old_run_dir.exists()
            assert not blob_store.exists(sha_unreferenced)
            assert not blob_store.exists(sha_old_run_out)

            # 4. Subsequent clean on empty: returns 0 deleted
            empty_resp = await client.post("/clean", json={})
            assert empty_resp.status_code == 200
            empty_data = CleanResponse.model_validate(empty_resp.json())
            assert empty_data.deleted_runs == 0
            assert empty_data.deleted_blobs == 0
            assert empty_data.reclaimed_bytes == 0

    asyncio.run(_test())
