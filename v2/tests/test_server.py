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
from plynx.api_models import RunEvent, RunState, RunStatus
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

            stream_resp = await client.get(f"/runs/{run_id}/stream")
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
