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
from plynx.api_models import (
    OpEntry,
    RunEvent,
    RunListResponse,
    RunState,
    RunStatus,
    WorkflowDocument,
    WorkflowInputSpec,
    WorkflowListItem,
)
from plynx.server import create_app
from plynx.store import RunStore
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
            assert frames[0].event_id == 1
            assert [f.event_id for f in frames] == list(range(1, len(frames) + 1))

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
        json.dumps({
            "schema": 1,
            "nodes": {"pick": {"x": 10.0, "y": 20.0}},
            "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.5},
        }),
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
