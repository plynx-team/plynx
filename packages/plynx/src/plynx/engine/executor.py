"""Executor protocol and execution data structures (ARCHITECTURE.md section 'Executors')."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from plynx_sdk.protocol import CheckpointManifest, InputsManifest, OutputsManifest

from plynx.api_models import NodeStatus

StatusCallback = Callable[[NodeStatus], Awaitable[None] | None]


@dataclass(frozen=True)
class ExecutionRequest:
    """Parameters passed to ``Executor.run`` or ``Executor.launch`` for one node attempt."""

    run_id: str
    node_id: str
    op: str
    attempt: int
    node_dir: Path
    inputs: InputsManifest
    timeout: float | None = None
    cancel_event: asyncio.Event | None = None
    on_status: StatusCallback | None = None

    async def notify_status(self, status: NodeStatus) -> None:
        """Invoke ``on_status`` if provided, awaiting coroutine results."""
        if self.on_status is not None:
            maybe_coro = self.on_status(status)
            if isinstance(maybe_coro, Awaitable):
                await maybe_coro


@dataclass(frozen=True)
class NodeResult:
    """Outcome of a single node attempt returned by ``Executor.run``."""

    status: NodeStatus
    exit_code: int
    started_at: float
    finished_at: float
    outputs: OutputsManifest | None = None
    checkpoint: CheckpointManifest | None = None
    error: str | None = None


@runtime_checkable
class Executor(Protocol):
    """Protocol implemented by node executors (``LocalExecutor``)."""

    async def run(self, request: ExecutionRequest) -> NodeResult:
        """Execute a node attempt and wait for it to finish."""
        ...
