"""Run lifecycle, checkpoint, stage-gate, log, output, and SSE streaming routes."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from plynx_sdk.protocol import ResultFileValue, ResultManifest
from pydantic import ValidationError

from plynx.api_models import (
    AnswerCheckpointRequest,
    CreateRunRequest,
    CreateRunResponse,
    NodeLogData,
    NodeLogEvent,
    RunListResponse,
    RunState,
    RunStatus,
    RunStatusEvent,
    StageApproveRequest,
    StageGateKind,
    StageGateStatus,
    StageInputsRequest,
)
from plynx.cas import BlobStore
from plynx.engine import Scheduler, SchedulerOptions
from plynx.server.routes.workflows import dump_workflow_yaml
from plynx.server.state import (
    TERMINAL_RUN_STATUSES,
    ServerState,
    ServerStateDep,
    error_response,
)
from plynx.store import StoreError
from plynx.workflow.models import NODE_ID_PATTERN, load_workflow
from plynx.workflow.validator import validate_workflow

SSE_POLL_INTERVAL_SECONDS: float = 0.1
_PORT_NAME_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]*$")

router = APIRouter()


def _parse_last_event_id(request: Request) -> int:
    raw = request.headers.get("Last-Event-ID") or request.query_params.get("last_event_id")
    if raw is None or not raw.strip():
        return 0
    try:
        val = int(raw.strip())
    except ValueError:
        return 0
    return max(val, 0)


def _format_sse_frame(
    *,
    event_type: str,
    data_json: str,
    seq: int | None = None,
) -> str:
    lines: list[str] = []
    if seq is not None:
        lines.append(f"id: {seq}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {data_json}")
    return "\n".join(lines) + "\n\n"


class _LogTailer:
    """Incrementally tails per-node stdout/stderr log files into SSE ``node_log`` frames."""

    def __init__(
        self,
        run_id: str,
        logs_dir: Path,
        *,
        after_seq: int,
        initial_log_offset: int | None,
    ) -> None:
        self.run_id = run_id
        self.logs_dir = logs_dir
        self.after_seq = after_seq
        self.initial_log_offset = initial_log_offset
        self.log_offsets: dict[tuple[str, str], int] = {}
        self.last_emit_times: dict[tuple[str, str], float] = {}

    def collect_frames(self, *, force_flush: bool = False) -> list[str]:
        """Read any newly appended log lines and return formatted SSE frames."""
        frames: list[str] = []
        if not self.logs_dir.is_dir():
            return frames
        now = time.monotonic()
        for log_file in sorted(self.logs_dir.glob("*.log")):
            name = log_file.name
            if not name.endswith(".log"):
                continue
            parts = name[:-4].split(".", 1)
            if len(parts) != 2 or parts[1] not in ("stdout", "stderr"):
                continue
            nid, stream_name = parts[0], parts[1]
            key = (nid, stream_name)

            if key not in self.log_offsets:
                if self.initial_log_offset is not None:
                    self.log_offsets[key] = self.initial_log_offset
                elif self.after_seq == 0:
                    self.log_offsets[key] = 0
                else:
                    try:
                        self.log_offsets[key] = log_file.stat().st_size
                    except OSError:
                        self.log_offsets[key] = 0

            cur_offset = self.log_offsets[key]
            last_emit = self.last_emit_times.get(key, 0.0)
            if not force_flush and (now - last_emit < 0.050):
                continue

            try:
                with open(log_file, "rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    if size <= cur_offset:
                        continue
                    f.seek(cur_offset)
                    raw_bytes = f.read()
            except OSError:
                continue

            if not raw_bytes:
                continue

            if not force_flush and b"\n" in raw_bytes:
                last_nl = raw_bytes.rfind(b"\n")
                if last_nl == -1:
                    continue
                to_process = raw_bytes[: last_nl + 1]
                new_offset = cur_offset + last_nl + 1
            else:
                to_process = raw_bytes
                new_offset = cur_offset + len(raw_bytes)

            if not to_process:
                continue

            text = to_process.decode("utf-8", errors="replace")
            log_event = NodeLogEvent(
                ts=time.time(),
                data=NodeLogData(
                    run_id=self.run_id,
                    node_id=nid,
                    stream=stream_name,  # type: ignore[arg-type]
                    offset=cur_offset,
                    lines=text.splitlines(),
                ),
            )
            payload = json.dumps(
                log_event.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            frames.append(_format_sse_frame(event_type="node_log", data_json=payload, seq=None))
            self.log_offsets[key] = new_offset
            self.last_emit_times[key] = now

        return frames


async def _stream_run_events_generator(
    state: ServerState,
    resolved_id: str,
    request: Request,
    *,
    after_seq: int,
    tailer: _LogTailer,
) -> AsyncIterator[str]:
    event_log = state.store.event_log(resolved_id)
    event_byte_offset = 0
    while True:
        events, event_byte_offset = await asyncio.to_thread(
            event_log.read_from_offset,
            event_byte_offset,
            after_seq=after_seq,
        )
        for ev in events:
            if ev.seq is not None:
                after_seq = ev.seq
            payload = json.dumps(
                ev.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield _format_sse_frame(event_type=ev.type, data_json=payload, seq=ev.seq)

        run_status = await asyncio.to_thread(state.store.get_run_status, resolved_id)
        is_terminal = run_status is None or run_status in TERMINAL_RUN_STATUSES

        if is_terminal:
            trailing, event_byte_offset = await asyncio.to_thread(
                event_log.read_from_offset,
                event_byte_offset,
                after_seq=after_seq,
            )
            last_trailing_status: RunStatus | None = None
            for ev in trailing:
                if ev.seq is not None:
                    after_seq = ev.seq
                if isinstance(ev, RunStatusEvent):
                    last_trailing_status = ev.data.status
                payload = json.dumps(
                    ev.model_dump(mode="json", exclude_none=True),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield _format_sse_frame(event_type=ev.type, data_json=payload, seq=ev.seq)
            if (
                last_trailing_status is not None
                and last_trailing_status not in TERMINAL_RUN_STATUSES
            ):
                is_terminal = False

        log_frames = await asyncio.to_thread(tailer.collect_frames, force_flush=is_terminal)
        for frame in log_frames:
            yield frame

        if is_terminal or await request.is_disconnected():
            break
        await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    state: ServerStateDep,
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    workflow_path: str | None = Query(default=None),
) -> RunListResponse:
    """Return recent runs ordered newest first."""
    items = await asyncio.to_thread(
        state.store.list_runs,
        limit=limit + 1,
        cursor=cursor,
        workflow_path=workflow_path,
    )
    if len(items) > limit:
        return RunListResponse(runs=items[:limit], next_cursor=items[limit - 1].id)
    return RunListResponse(runs=items, next_cursor=None)


@router.get("/runs/{run_id}", response_model=RunState)
async def get_run(
    run_id: str,
    state: ServerStateDep,
) -> Any:
    """Return the full ``RunState`` for ``run_id`` (or unique prefix)."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    run_state = await asyncio.to_thread(state.store.get_run_state, resolved_id)
    if run_state is None:
        return error_response(404, "run_not_found", f"Run {run_id!r} not found")
    return run_state


@router.post("/runs", response_model=CreateRunResponse, status_code=201)
async def create_run_endpoint(
    body: CreateRunRequest,
    state: ServerStateDep,
) -> Any:
    """Start a new workflow run asynchronously and return ``{ run_id }``."""
    wf_candidate = (state.workspace_root / body.workflow_path).resolve()
    try:
        rel_wf = wf_candidate.relative_to(state.workspace_root).as_posix()
    except ValueError:
        return error_response(
            400,
            "invalid_workflow_path",
            "workflow_path must stay inside the workspace root",
        )

    layout_bytes: bytes | None = None
    if body.workflow is not None:
        wf_model = body.workflow
        workflow_bytes = dump_workflow_yaml(wf_model)
        if body.layout is not None:
            layout_bytes = (
                json.dumps(
                    body.layout.model_dump(mode="json", by_alias=True),
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")
        else:
            sidecar = wf_candidate.with_name(f".{wf_candidate.stem}.layout.json")
            layout_bytes = (
                await asyncio.to_thread(sidecar.read_bytes) if sidecar.is_file() else None
            )
    else:
        if not wf_candidate.is_file():
            return error_response(
                404,
                "workflow_not_found",
                f"Workflow file not found: {body.workflow_path}",
            )
        try:
            wf_model = await asyncio.to_thread(load_workflow, wf_candidate)
        except (ValidationError, ValueError, OSError) as exc:
            return error_response(400, "invalid_workflow", str(exc))

        workflow_bytes = await asyncio.to_thread(wf_candidate.read_bytes)
        sidecar = wf_candidate.with_name(f".{wf_candidate.stem}.layout.json")
        layout_bytes = await asyncio.to_thread(sidecar.read_bytes) if sidecar.is_file() else None

    issues = validate_workflow(wf_model, state.registry)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        msg = "; ".join(issue.message for issue in errors)
        return error_response(422, "validation_failed", msg)

    run_id = await asyncio.to_thread(
        state.store.create_run,
        workflow_path=rel_wf,
        workflow_bytes=workflow_bytes,
        layout_bytes=layout_bytes,
        node_ids=list(wf_model.nodes.keys()),
        run_inputs=body.inputs,
    )

    executor = state.executor_factory(state.workspace_root)
    scheduler = Scheduler(state.store, executor, state.registry)
    opts = SchedulerOptions(run_inputs=dict(body.inputs), no_cache=body.no_cache)
    task = asyncio.create_task(
        scheduler.run(
            wf_model,
            workflow_path=rel_wf,
            workflow_bytes=workflow_bytes,
            layout_bytes=layout_bytes,
            run_id=run_id,
            options=opts,
        )
    )
    state.track_run_task(run_id, task)
    return CreateRunResponse(run_id=run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel_run_endpoint(
    run_id: str,
    state: ServerStateDep,
) -> Any:
    """Request cancellation for a run."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    await asyncio.to_thread(state.store.request_cancel, resolved_id)
    return {"status": "ok", "run_id": resolved_id}


@router.post("/runs/{run_id}/resume", response_model=CreateRunResponse)
async def resume_run_endpoint(
    run_id: str,
    state: ServerStateDep,
) -> Any:
    """Resume an existing failed, canceled, or waiting run."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    run_state = await asyncio.to_thread(state.store.get_run_state, resolved_id)
    if run_state is None:
        return error_response(404, "run_not_found", f"Run {run_id!r} not found")
    if run_state.status == RunStatus.SUCCESS:
        return error_response(
            409,
            "run_not_resumable",
            f"Run {resolved_id!r} already succeeded and cannot be resumed",
        )
    if run_state.status == RunStatus.RUNNING:
        return error_response(
            409,
            "run_not_resumable",
            f"Run {resolved_id!r} is currently running",
        )

    try:
        await asyncio.to_thread(state.store.claim_run_for_resume, resolved_id)
    except StoreError as exc:
        return error_response(409, "run_not_resumable", str(exc))

    executor = state.executor_factory(state.workspace_root)
    scheduler = Scheduler(state.store, executor, state.registry)
    task = asyncio.create_task(scheduler.resume(resolved_id, options=SchedulerOptions()))
    state.track_run_task(resolved_id, task)
    return CreateRunResponse(run_id=resolved_id)


@router.post("/runs/{run_id}/checkpoints/{node_id}/{checkpoint_id}/answer")
async def answer_checkpoint_endpoint(
    run_id: str,
    node_id: str,
    checkpoint_id: str,
    body: AnswerCheckpointRequest,
    state: ServerStateDep,
) -> Any:
    """Submit an answer to an open checkpoint prompt."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    cp = await asyncio.to_thread(state.store.get_checkpoint, resolved_id, node_id, checkpoint_id)
    if cp is None:
        return error_response(
            404,
            "checkpoint_not_found",
            f"Checkpoint '{node_id}.{checkpoint_id}' not found in run {resolved_id!r}",
        )
    if cp.answer is not None:
        return error_response(
            409,
            "checkpoint_already_answered",
            f"Checkpoint '{node_id}.{checkpoint_id}' has already been answered",
        )

    applied = await asyncio.to_thread(
        state.store.answer_checkpoint,
        resolved_id,
        node_id,
        checkpoint_id,
        body.answer,
    )
    if not applied:
        return error_response(
            409,
            "checkpoint_already_answered",
            f"Checkpoint '{node_id}.{checkpoint_id}' has already been answered",
        )
    await state.auto_resume_if_unowned(resolved_id)
    return {"status": "ok", "checkpoint_id": checkpoint_id, "answer": body.answer}


@router.post("/runs/{run_id}/stages/{stage_id}/approve")
async def approve_stage_endpoint(
    run_id: str,
    stage_id: str,
    state: ServerStateDep,
    body: StageApproveRequest | None = None,
) -> Any:
    """Approve a stage approval gate awaiting approval."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    gate = await asyncio.to_thread(state.store.get_stage_gate, resolved_id, stage_id)
    if gate is None:
        return error_response(
            404,
            "stage_gate_not_found",
            f"Stage gate '{stage_id}' not found in run {resolved_id!r}",
        )
    if gate.status == StageGateStatus.APPROVED:
        return error_response(
            409,
            "stage_gate_already_approved",
            f"Stage gate '{stage_id}' has already been approved",
        )

    if body is not None and body.inputs:
        await asyncio.to_thread(state.store.update_run_inputs, resolved_id, body.inputs)

    applied = await asyncio.to_thread(
        state.store.approve_stage_gate,
        resolved_id,
        stage_id,
        kind=gate.kind,
    )
    if not applied:
        return error_response(
            409,
            "stage_gate_already_approved",
            f"Stage gate '{stage_id}' has already been approved",
        )
    await state.auto_resume_if_unowned(resolved_id)
    return {"status": "ok", "stage_id": stage_id, "kind": gate.kind.value}


@router.post("/runs/{run_id}/stages/{stage_id}/inputs")
async def stage_inputs_endpoint(
    run_id: str,
    stage_id: str,
    body: StageInputsRequest,
    state: ServerStateDep,
) -> Any:
    """Submit inputs for a stage and approve its input gate if waiting."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    if body.inputs:
        await asyncio.to_thread(state.store.update_run_inputs, resolved_id, body.inputs)

    gate = await asyncio.to_thread(
        state.store.get_stage_gate,
        resolved_id,
        stage_id,
        kind=StageGateKind.INPUT,
    )
    if gate is not None and gate.status == StageGateStatus.WAITING:
        await asyncio.to_thread(
            state.store.approve_stage_gate,
            resolved_id,
            stage_id,
            kind=StageGateKind.INPUT,
        )

    await state.auto_resume_if_unowned(resolved_id)
    return {"status": "ok", "stage_id": stage_id, "kind": StageGateKind.INPUT.value}


@router.get("/runs/{run_id}/nodes/{node_id}/logs/{stream}")
async def get_node_logs(
    run_id: str,
    node_id: str,
    stream: str,
    state: ServerStateDep,
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Return plain-text logs for a node stream from offset with X-Next-Offset header."""
    if not NODE_ID_PATTERN.match(node_id):
        return error_response(
            400,
            "invalid_node_id",
            f"Node ID {node_id!r} is invalid: must match {NODE_ID_PATTERN.pattern}",
        )

    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    if stream not in ("stdout", "stderr"):
        return error_response(
            400,
            "invalid_stream",
            f"Stream must be 'stdout' or 'stderr', got {stream!r}",
        )

    logs_dir = state.store.run_dir(resolved_id) / "logs"
    log_path = (logs_dir / f"{node_id}.{stream}.log").resolve()
    try:
        log_path.relative_to(logs_dir.resolve())
    except ValueError:
        return error_response(
            400,
            "invalid_node_id",
            "Log path must stay inside the logs directory",
        )

    if not log_path.is_file():
        return Response(
            content="",
            media_type="text/plain; charset=utf-8",
            headers={"X-Next-Offset": str(offset)},
        )

    def _read_log() -> tuple[str, int]:
        with open(log_path, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            if offset >= file_size:
                return "", file_size
            f.seek(offset)
            data = f.read()
            next_offset = f.tell()
            return data.decode("utf-8", errors="replace"), next_offset

    text, next_offset = await asyncio.to_thread(_read_log)
    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"X-Next-Offset": str(next_offset)},
    )


@router.get("/runs/{run_id}/nodes/{node_id}/outputs/{name}")
async def get_node_output(
    run_id: str,
    node_id: str,
    name: str,
    state: ServerStateDep,
) -> Any:
    """Download or fetch an output artifact from a node."""
    if not NODE_ID_PATTERN.match(node_id):
        return error_response(
            400,
            "invalid_node_id",
            f"Node ID {node_id!r} is invalid: must match {NODE_ID_PATTERN.pattern}",
        )

    if not _PORT_NAME_RE.match(name):
        return error_response(
            400,
            "invalid_output_name",
            f"Output port name {name!r} is invalid: must match {_PORT_NAME_RE.pattern}",
        )

    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    node_dir = state.store.node_dir(resolved_id, node_id).resolve()
    try:
        node_dir.relative_to(state.store.run_dir(resolved_id).resolve())
    except ValueError:
        return error_response(
            400,
            "invalid_node_id",
            "Node path must stay inside the run directory",
        )

    result_path = node_dir / "result.json"
    if not result_path.is_file():
        return error_response(
            404,
            "output_not_found",
            f"No outputs found for node '{node_id}' in run {resolved_id!r}",
        )

    try:
        raw_bytes = await asyncio.to_thread(result_path.read_bytes)
        manifest = ResultManifest.from_json(raw_bytes)
    except Exception as exc:
        return error_response(500, "result_parse_error", str(exc))

    if name not in manifest.outputs:
        return error_response(
            404,
            "output_not_found",
            f"Output '{name}' not found for node '{node_id}'",
        )

    output_val = manifest.outputs[name]
    if isinstance(output_val, ResultFileValue):
        blob_store = BlobStore.from_workspace(state.workspace_root)
        blob_path = blob_store.blob_path(output_val.sha256)
        if not blob_path.is_file():
            return error_response(
                404,
                "blob_not_found",
                f"Blob {output_val.sha256} not found in store",
            )
        media_type = output_val.media or "application/octet-stream"
        filename = output_val.filename or f"{name}.bin"
        return FileResponse(blob_path, media_type=media_type, filename=filename)

    return JSONResponse(content=output_val.to_dict())


@router.get("/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    state: ServerStateDep,
) -> Any:
    """Tail ``events.jsonl`` and log files for ``run_id`` as Server-Sent Events (SSE)."""
    resolved_id, err = await state.resolve_run_id_or_error(run_id)
    if err is not None:
        return err
    assert resolved_id is not None

    after_seq = _parse_last_event_id(request)
    parsed_log_offset: int | None = None
    raw_log_offset = request.query_params.get("log_offset")
    if raw_log_offset is not None:
        try:
            parsed_log_offset = max(int(raw_log_offset), 0)
        except ValueError:
            parsed_log_offset = None

    tailer = _LogTailer(
        resolved_id,
        state.store.run_dir(resolved_id) / "logs",
        after_seq=after_seq,
        initial_log_offset=parsed_log_offset,
    )
    return StreamingResponse(
        _stream_run_events_generator(
            state,
            resolved_id,
            request,
            after_seq=after_seq,
            tailer=tailer,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
