"""Explicit application state and shared helpers for the PLynx FastAPI server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from plynx.api_models import (
    ApiErrorDetail,
    ApiErrorResponse,
    RunStatus,
    RunStatusData,
)
from plynx.engine import Executor, Scheduler, SchedulerOptions
from plynx.engine.procgroup import is_pid_alive
from plynx.registry import OpRegistry
from plynx.store import (
    AmbiguousRunIdError,
    RunNotFoundError,
    RunStore,
    StoreError,
)

TERMINAL_RUN_STATUSES = frozenset({RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELED})
logger = logging.getLogger(__name__)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build a standardized JSON error response."""
    body = ApiErrorResponse(error=ApiErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@dataclass
class ServerState:
    """Explicit shared state for a PLynx FastAPI application instance."""

    workspace_root: Path
    store: RunStore
    registry: OpRegistry
    executor_factory: Callable[[Path | None], Executor]
    background_tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    active_run_tasks: dict[asyncio.Task[Any], str] = field(default_factory=dict)

    def track_run_task(self, run_id: str, task: asyncio.Task[Any]) -> None:
        """Track a background run task and record crash state if it raises unexpectedly."""
        self.background_tasks.add(task)
        self.active_run_tasks[task] = run_id

        def _on_done(done_task: asyncio.Task[Any]) -> None:
            self.background_tasks.discard(done_task)
            self.active_run_tasks.pop(done_task, None)
            if done_task.cancelled():
                return
            exc = done_task.exception()
            if exc is None:
                return
            logger.exception("Background run task crashed for run %s", run_id, exc_info=exc)
            try:
                status = self.store.get_run_status(run_id)
                if status not in TERMINAL_RUN_STATUSES:
                    err_msg = f"Unexpected engine error: {type(exc).__name__}: {exc}"
                    self.store.update_run_status(
                        run_id,
                        RunStatus.FAILED,
                        finished_at=time.time(),
                        error=err_msg,
                    )
                    self.store.release_ownership(run_id)
                    if self.store.run_dir(run_id).is_dir():
                        self.store.event_log(run_id).append(
                            "run_status",
                            RunStatusData(
                                run_id=run_id,
                                status=RunStatus.FAILED,
                                error=err_msg,
                            ),
                        )
            except Exception:
                logger.exception("Failed to record crash status for run %s", run_id)

        task.add_done_callback(_on_done)

    async def auto_resume_if_unowned(self, resolved_id: str) -> None:
        """If a WAITING_FOR_USER run has no live owner process, resume it automatically."""
        state = await asyncio.to_thread(self.store.get_run_state, resolved_id)
        if state is None or state.status != RunStatus.WAITING_FOR_USER:
            return
        if state.owner_pid is not None and is_pid_alive(int(state.owner_pid)):
            return
        try:
            await asyncio.to_thread(self.store.claim_run_for_resume, resolved_id)
        except StoreError:
            return
        executor = self.executor_factory(self.workspace_root)
        scheduler = Scheduler(self.store, executor, self.registry)
        task = asyncio.create_task(scheduler.resume(resolved_id, options=SchedulerOptions()))
        self.track_run_task(resolved_id, task)

    async def shutdown_active_runs(self) -> None:
        """Request cancellation and await all active background run tasks during shutdown."""
        tasks_snapshot = list(self.active_run_tasks.items())
        if not tasks_snapshot:
            return
        for _task, active_run_id in tasks_snapshot:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(self.store.request_cancel, active_run_id)
        pending_tasks = [t for t, _ in tasks_snapshot if not t.done()]
        if pending_tasks:
            _done, still_pending = await asyncio.wait(pending_tasks, timeout=5.0)
            for pending in still_pending:
                pending.cancel()
            if still_pending:
                await asyncio.gather(*still_pending, return_exceptions=True)

    async def resolve_run_id_or_error(self, run_id: str) -> tuple[str | None, JSONResponse | None]:
        """Resolve ``run_id`` (or prefix), returning ``(resolved_id, None)`` or ``(None, error)``."""
        try:
            resolved_id = await asyncio.to_thread(self.store.resolve_run_id, run_id)
            return resolved_id, None
        except RunNotFoundError as exc:
            return None, error_response(404, "run_not_found", str(exc))
        except AmbiguousRunIdError as exc:
            return None, error_response(409, "ambiguous_run_id", str(exc))


def get_server_state(request: Request) -> ServerState:
    """FastAPI dependency returning the explicit ``ServerState``."""
    state: ServerState = request.app.state.server
    return state


ServerStateDep = Annotated[ServerState, Depends(get_server_state)]
