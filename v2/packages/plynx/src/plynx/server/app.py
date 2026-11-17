"""FastAPI application and REST/SSE endpoints (PROTOCOL.md sections 9 & 10)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from plynx_sdk.protocol import ResultFileValue, ResultManifest
from pydantic import ValidationError
from ruamel.yaml import YAML

from plynx.api_models import (
    AnswerCheckpointRequest,
    ApiErrorDetail,
    ApiErrorResponse,
    CreateRunRequest,
    CreateRunResponse,
    HealthResponse,
    NodeLogData,
    NodeLogEvent,
    OpEntry,
    RunListResponse,
    RunState,
    RunStatus,
    RunStatusEvent,
    StageGateStatus,
    UploadResponse,
    WorkflowDocument,
    WorkflowInputSpec,
    WorkflowLayout,
    WorkflowListItem,
)
from plynx.cas import BlobStore
from plynx.engine import Executor, Scheduler, SchedulerOptions, create_executor
from plynx.registry import OpRegistry, Registry, find_workspace_root
from plynx.store import (
    AmbiguousRunIdError,
    RunNotFoundError,
    RunStore,
    StoreError,
    atomic_write_bytes,
)
from plynx.workflow.models import load_workflow
from plynx.workflow.validator import get_unbound_run_inputs, validate_workflow

TERMINAL_RUN_STATUSES = frozenset({RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELED})
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ApiErrorResponse(error=ApiErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


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


def _discover_workflows(workspace_root: Path) -> list[WorkflowListItem]:
    cfg_path = workspace_root / "plynx.yaml"
    wf_dir_names: list[str] = ["workflows", "examples/workflows"]
    if cfg_path.is_file():
        try:
            yaml = YAML(typ="safe")
            parsed = yaml.load(cfg_path.read_text(encoding="utf-8"))
            if isinstance(parsed, Mapping) and "workflows" in parsed:
                val = parsed["workflows"]
                if isinstance(val, str):
                    wf_dir_names = [val]
                elif isinstance(val, list):
                    wf_dir_names = [str(x) for x in val]
        except Exception:
            pass

    items: list[WorkflowListItem] = []
    seen_paths: set[str] = set()

    for dir_name in wf_dir_names:
        wf_dir = (workspace_root / dir_name).resolve()
        if not wf_dir.is_dir():
            continue
        for ext in ("*.yaml", "*.yml"):
            for candidate in sorted(wf_dir.rglob(ext)):
                if candidate.name.startswith((".", "#")):
                    continue
                try:
                    rel_path = candidate.resolve().relative_to(workspace_root.resolve()).as_posix()
                except ValueError:
                    rel_path = candidate.as_posix()
                if rel_path in seen_paths:
                    continue
                try:
                    wf = load_workflow(candidate)
                    name = wf.name or candidate.stem
                    stage_count = len(wf.stages)
                    items.append(
                        WorkflowListItem(
                            path=rel_path,
                            name=name,
                            stage_count=stage_count,
                        )
                    )
                    seen_paths.add(rel_path)
                except Exception:
                    continue

    items.sort(key=lambda it: it.path)
    return items


def create_app(
    workspace_root: Path | None = None,
    *,
    executor_factory: Callable[[Path | None], Executor] = create_executor,
    registry: OpRegistry | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the PLynx FastAPI application."""
    ws_root = (workspace_root or find_workspace_root()).resolve()
    ui_static_dir = (static_dir or DEFAULT_STATIC_DIR).resolve()
    store = RunStore(ws_root)
    store.reconcile_dead_owners()
    op_registry: OpRegistry = Registry(ws_root) if registry is None else registry
    background_tasks: set[asyncio.Task[Any]] = set()

    app = FastAPI(title="PLynx", version="2.0.0")
    app.state.workspace_root = ws_root
    app.state.store = store
    app.state.registry = op_registry
    app.state.background_tasks = background_tasks

    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    async def get_health() -> HealthResponse:
        """Return server health and version."""
        return HealthResponse()

    @router.get("/ops", response_model=list[OpEntry])
    async def get_ops() -> list[OpEntry]:
        """Return all registered operations."""
        if hasattr(op_registry, "refresh"):
            await asyncio.to_thread(op_registry.refresh)
        return await asyncio.to_thread(op_registry.list_ops)

    @router.get("/workflows", response_model=list[WorkflowListItem])
    async def list_workflows_endpoint() -> list[WorkflowListItem]:
        """Return list of discovered workflow files in the workspace."""
        return await asyncio.to_thread(_discover_workflows, ws_root)

    @router.get("/workflows/{path:path}/inputs", response_model=list[WorkflowInputSpec])
    async def get_workflow_inputs(path: str) -> Any:
        """Return run inputs still unbound for the given workflow path."""
        wf_candidate = (ws_root / path).resolve()
        try:
            wf_candidate.relative_to(ws_root)
        except ValueError:
            return _error_response(
                400,
                "invalid_workflow_path",
                "workflow path must stay inside the workspace root",
            )
        if not wf_candidate.is_file():
            return _error_response(
                404,
                "workflow_not_found",
                f"Workflow file not found: {path}",
            )
        try:
            wf_model = await asyncio.to_thread(load_workflow, wf_candidate)
        except Exception as exc:
            return _error_response(400, "invalid_workflow", str(exc))
        return get_unbound_run_inputs(wf_model, op_registry)

    @router.get("/workflows/{path:path}", response_model=WorkflowDocument)
    async def get_workflow_endpoint(path: str) -> Any:
        """Return the workflow document and optional layout sidecar."""
        wf_candidate = (ws_root / path).resolve()
        try:
            wf_candidate.relative_to(ws_root)
        except ValueError:
            return _error_response(
                400,
                "invalid_workflow_path",
                "workflow path must stay inside the workspace root",
            )
        if not wf_candidate.is_file():
            return _error_response(
                404,
                "workflow_not_found",
                f"Workflow file not found: {path}",
            )
        try:
            wf_model = await asyncio.to_thread(load_workflow, wf_candidate)
        except Exception as exc:
            return _error_response(400, "invalid_workflow", str(exc))

        sidecar = wf_candidate.with_name(f".{wf_candidate.stem}.layout.json")
        layout: WorkflowLayout | None = None
        if sidecar.is_file():
            try:
                sidecar_text = await asyncio.to_thread(sidecar.read_text, encoding="utf-8")
                layout = WorkflowLayout.model_validate_json(sidecar_text)
            except Exception:
                layout = None

        return WorkflowDocument(workflow=wf_model, layout=layout)

    @router.get("/runs", response_model=RunListResponse)
    async def list_runs(
        limit: int = Query(default=50, ge=1, le=500),
        cursor: str | None = Query(default=None),
    ) -> RunListResponse:
        """Return recent runs ordered newest first."""
        items = await asyncio.to_thread(store.list_runs, limit=limit + 1, cursor=cursor)
        if len(items) > limit:
            next_cursor = items[limit - 1].id
            runs = items[:limit]
        else:
            next_cursor = None
            runs = items
        return RunListResponse(runs=runs, next_cursor=next_cursor)

    @router.get("/runs/{run_id}", response_model=RunState)
    async def get_run(run_id: str) -> Any:
        """Return the full ``RunState`` for ``run_id`` (or unique prefix)."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        state = await asyncio.to_thread(store.get_run_state, resolved_id)
        if state is None:
            return _error_response(404, "run_not_found", f"Run {run_id!r} not found")
        return state

    @router.post("/runs", response_model=CreateRunResponse, status_code=201)
    async def create_run_endpoint(body: CreateRunRequest) -> Any:
        """Start a new workflow run asynchronously and return ``{ run_id }``."""
        wf_candidate = (ws_root / body.workflow_path).resolve()
        try:
            rel_wf = wf_candidate.relative_to(ws_root).as_posix()
        except ValueError:
            return _error_response(
                400,
                "invalid_workflow_path",
                "workflow_path must stay inside the workspace root",
            )
        if not wf_candidate.is_file():
            return _error_response(
                404,
                "workflow_not_found",
                f"Workflow file not found: {body.workflow_path}",
            )

        try:
            wf_model = await asyncio.to_thread(load_workflow, wf_candidate)
        except (ValidationError, ValueError, OSError) as exc:
            return _error_response(400, "invalid_workflow", str(exc))

        issues = validate_workflow(wf_model, op_registry)
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            msg = "; ".join(issue.message for issue in errors)
            return _error_response(422, "validation_failed", msg)

        workflow_bytes = await asyncio.to_thread(wf_candidate.read_bytes)
        sidecar = wf_candidate.with_name(f".{wf_candidate.stem}.layout.json")
        layout_bytes = await asyncio.to_thread(sidecar.read_bytes) if sidecar.is_file() else None

        run_id = await asyncio.to_thread(
            store.create_run,
            workflow_path=rel_wf,
            workflow_bytes=workflow_bytes,
            layout_bytes=layout_bytes,
            node_ids=list(wf_model.nodes.keys()),
            run_inputs=body.inputs,
        )

        executor = executor_factory(ws_root)
        scheduler = Scheduler(store, executor, op_registry)
        opts = SchedulerOptions(
            run_inputs=dict(body.inputs),
            no_cache=body.no_cache,
        )
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
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return CreateRunResponse(run_id=run_id)

    @router.post("/runs/{run_id}/cancel")
    async def cancel_run_endpoint(run_id: str) -> Any:
        """Request cancellation for a run."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        await asyncio.to_thread(store.request_cancel, resolved_id)
        return {"status": "ok", "run_id": resolved_id}

    @router.post("/runs/{run_id}/resume", response_model=CreateRunResponse)
    async def resume_run_endpoint(run_id: str) -> Any:
        """Resume an existing failed, canceled, or waiting run."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        state = await asyncio.to_thread(store.get_run_state, resolved_id)
        if state is None:
            return _error_response(404, "run_not_found", f"Run {run_id!r} not found")
        if state.status == RunStatus.SUCCESS:
            return _error_response(
                409,
                "run_not_resumable",
                f"Run {resolved_id!r} already succeeded and cannot be resumed",
            )
        if state.status == RunStatus.RUNNING:
            return _error_response(
                409, "run_not_resumable", f"Run {resolved_id!r} is currently running"
            )

        try:
            await asyncio.to_thread(store.claim_run_for_resume, resolved_id)
        except StoreError as exc:
            return _error_response(409, "run_not_resumable", str(exc))

        executor = executor_factory(ws_root)
        scheduler = Scheduler(store, executor, op_registry)
        opts = SchedulerOptions(no_cache=True)
        task = asyncio.create_task(scheduler.resume(resolved_id, options=opts))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return CreateRunResponse(run_id=resolved_id)

    @router.post("/runs/{run_id}/checkpoints/{node_id}/{checkpoint_id}/answer")
    async def answer_checkpoint_endpoint(
        run_id: str,
        node_id: str,
        checkpoint_id: str,
        body: AnswerCheckpointRequest,
    ) -> Any:
        """Submit an answer to an open checkpoint prompt."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        cp = await asyncio.to_thread(store.get_checkpoint, resolved_id, node_id, checkpoint_id)
        if cp is None:
            return _error_response(
                404,
                "checkpoint_not_found",
                f"Checkpoint '{node_id}.{checkpoint_id}' not found in run {resolved_id!r}",
            )
        if cp.answer is not None:
            return _error_response(
                409,
                "checkpoint_already_answered",
                f"Checkpoint '{node_id}.{checkpoint_id}' has already been answered",
            )

        applied = await asyncio.to_thread(
            store.answer_checkpoint,
            resolved_id,
            node_id,
            checkpoint_id,
            body.answer,
        )
        if not applied:
            return _error_response(
                409,
                "checkpoint_already_answered",
                f"Checkpoint '{node_id}.{checkpoint_id}' has already been answered",
            )
        return {"status": "ok", "checkpoint_id": checkpoint_id, "answer": body.answer}

    @router.post("/runs/{run_id}/stages/{stage_id}/approve")
    async def approve_stage_endpoint(run_id: str, stage_id: str) -> Any:
        """Approve a stage approval gate awaiting approval."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        gate = await asyncio.to_thread(store.get_stage_gate, resolved_id, stage_id)
        if gate is None:
            return _error_response(
                404,
                "stage_gate_not_found",
                f"Stage gate '{stage_id}' not found in run {resolved_id!r}",
            )
        if gate.status == StageGateStatus.APPROVED:
            return _error_response(
                409,
                "stage_gate_already_approved",
                f"Stage gate '{stage_id}' has already been approved",
            )

        applied = await asyncio.to_thread(store.approve_stage_gate, resolved_id, stage_id)
        if not applied:
            return _error_response(
                409,
                "stage_gate_already_approved",
                f"Stage gate '{stage_id}' has already been approved",
            )
        return {"status": "ok", "stage_id": stage_id}

    @router.get("/runs/{run_id}/nodes/{node_id}/logs/{stream}")
    async def get_node_logs(
        run_id: str,
        node_id: str,
        stream: str,
        offset: int = Query(default=0, ge=0),
    ) -> Any:
        """Return plain-text logs for a node stream from offset with X-Next-Offset header."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        if stream not in ("stdout", "stderr"):
            return _error_response(
                400,
                "invalid_stream",
                f"Stream must be 'stdout' or 'stderr', got {stream!r}",
            )

        log_path = store.run_dir(resolved_id) / "logs" / f"{node_id}.{stream}.log"
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

    @router.post("/uploads", response_model=UploadResponse, status_code=201)
    async def upload_file_endpoint(file: UploadFile) -> Any:
        """Upload a multipart file into ``.plynx/uploads/``."""
        raw_filename = file.filename or ""
        if (
            not raw_filename
            or "/" in raw_filename
            or "\\" in raw_filename
            or ".." in raw_filename
            or Path(raw_filename).name != raw_filename
        ):
            return _error_response(
                400,
                "invalid_filename",
                "Uploaded filename cannot contain path separators or traversal characters",
            )

        uploads_dir = ws_root / ".plynx" / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        dest = (uploads_dir / raw_filename).resolve()
        try:
            dest.relative_to(uploads_dir.resolve())
        except ValueError:
            return _error_response(
                400,
                "invalid_filename",
                "Uploaded file path must stay inside the uploads directory",
            )

        content = await file.read()
        await asyncio.to_thread(atomic_write_bytes, dest, content)

        rel_path = dest.relative_to(ws_root.resolve()).as_posix()
        return UploadResponse(path=rel_path)

    @router.get("/runs/{run_id}/nodes/{node_id}/outputs/{name}")
    async def get_node_output(run_id: str, node_id: str, name: str) -> Any:
        """Download or fetch an output artifact from a node."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        result_path = store.node_dir(resolved_id, node_id) / "result.json"
        if not result_path.is_file():
            return _error_response(
                404,
                "output_not_found",
                f"No outputs found for node '{node_id}' in run {resolved_id!r}",
            )

        try:
            raw_bytes = await asyncio.to_thread(result_path.read_bytes)
            manifest = ResultManifest.from_json(raw_bytes)
        except Exception as exc:
            return _error_response(500, "result_parse_error", str(exc))

        if name not in manifest.outputs:
            return _error_response(
                404,
                "output_not_found",
                f"Output '{name}' not found for node '{node_id}'",
            )

        output_val = manifest.outputs[name]
        if isinstance(output_val, ResultFileValue):
            blob_store = BlobStore.from_workspace(ws_root)
            blob_path = blob_store.blob_path(output_val.sha256)
            if not blob_path.is_file():
                return _error_response(
                    404,
                    "blob_not_found",
                    f"Blob {output_val.sha256} not found in store",
                )
            media_type = output_val.media or "application/octet-stream"
            filename = output_val.filename or f"{name}.bin"
            return FileResponse(
                blob_path,
                media_type=media_type,
                filename=filename,
            )

        return JSONResponse(content=output_val.to_dict())

    @router.get("/runs/{run_id}/stream")
    async def stream_run_events(run_id: str, request: Request) -> Any:
        """Tail ``events.jsonl`` and log files for ``run_id`` as Server-Sent Events (SSE)."""
        try:
            resolved_id = await asyncio.to_thread(store.resolve_run_id, run_id)
        except RunNotFoundError as exc:
            return _error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return _error_response(409, "ambiguous_run_id", str(exc))

        after_seq = _parse_last_event_id(request)
        event_log = store.event_log(resolved_id)
        logs_dir = store.run_dir(resolved_id) / "logs"

        parsed_log_offset: int | None = None
        raw_log_offset = request.query_params.get("log_offset")
        if raw_log_offset is not None:
            try:
                parsed_log_offset = max(int(raw_log_offset), 0)
            except ValueError:
                parsed_log_offset = None

        log_offsets: dict[tuple[str, str], int] = {}
        last_emit_times: dict[tuple[str, str], float] = {}

        def _get_new_log_frames(force_flush: bool = False) -> list[str]:
            frames: list[str] = []
            if not logs_dir.is_dir():
                return frames
            now = time.monotonic()
            for log_file in sorted(logs_dir.glob("*.log")):
                name = log_file.name
                if not name.endswith(".log"):
                    continue
                parts = name[:-4].split(".", 1)
                if len(parts) != 2 or parts[1] not in ("stdout", "stderr"):
                    continue
                nid, stream_name = parts[0], parts[1]
                key = (nid, stream_name)

                if key not in log_offsets:
                    if parsed_log_offset is not None:
                        log_offsets[key] = parsed_log_offset
                    elif after_seq == 0:
                        log_offsets[key] = 0
                    else:
                        try:
                            log_offsets[key] = log_file.stat().st_size
                        except OSError:
                            log_offsets[key] = 0

                cur_offset = log_offsets[key]
                last_emit = last_emit_times.get(key, 0.0)

                # Batch at most one event per 50 ms per node/stream, unless forcing final flush
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
                lines = text.splitlines()
                log_data = NodeLogData(
                    run_id=resolved_id,
                    node_id=nid,
                    stream=stream_name,  # type: ignore[arg-type]
                    offset=cur_offset,
                    lines=lines,
                )
                log_event = NodeLogEvent(
                    ts=time.time(),
                    data=log_data,
                )
                payload = json.dumps(
                    log_event.model_dump(mode="json", exclude_none=True),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                frames.append(
                    _format_sse_frame(
                        event_type="node_log",
                        data_json=payload,
                        seq=None,
                    )
                )
                log_offsets[key] = new_offset
                last_emit_times[key] = now

            return frames

        async def _event_generator() -> AsyncIterator[str]:
            nonlocal after_seq
            while True:
                events = await asyncio.to_thread(event_log.read_after, after_seq)
                saw_terminal = False
                for ev in events:
                    if ev.seq is not None:
                        after_seq = ev.seq
                    payload = json.dumps(
                        ev.model_dump(mode="json", exclude_none=True),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield _format_sse_frame(
                        event_type=ev.type,
                        data_json=payload,
                        seq=ev.seq,
                    )
                    if isinstance(ev, RunStatusEvent) and ev.data.status in TERMINAL_RUN_STATUSES:
                        saw_terminal = True

                log_frames = await asyncio.to_thread(_get_new_log_frames, force_flush=saw_terminal)
                for frame in log_frames:
                    yield frame

                if saw_terminal:
                    final_log_frames = await asyncio.to_thread(
                        _get_new_log_frames, force_flush=True
                    )
                    for frame in final_log_frames:
                        yield frame
                    break

                state = await asyncio.to_thread(store.get_run_state, resolved_id)
                if state is not None and state.status in TERMINAL_RUN_STATUSES:
                    trailing = await asyncio.to_thread(event_log.read_after, after_seq)
                    for ev in trailing:
                        if ev.seq is not None:
                            after_seq = ev.seq
                        payload = json.dumps(
                            ev.model_dump(mode="json", exclude_none=True),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        yield _format_sse_frame(
                            event_type=ev.type,
                            data_json=payload,
                            seq=ev.seq,
                        )
                    final_log_frames = await asyncio.to_thread(
                        _get_new_log_frames, force_flush=True
                    )
                    for frame in final_log_frames:
                        yield frame
                    break

                if await request.is_disconnected():
                    break
                await asyncio.sleep(0.02)

        return StreamingResponse(
            _event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    app.include_router(router)
    app.include_router(router, prefix="/api/v1")

    @app.get("/", response_model=None)
    async def serve_index() -> Any:
        """Serve the built UI index.html at ``/``."""
        index_file = ui_static_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file, media_type="text/html")
        return HTMLResponse(
            content="<!doctype html><html><body><h1>PLynx UI not built</h1></body></html>",
            status_code=404,
        )

    assets_dir = ui_static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    return app
