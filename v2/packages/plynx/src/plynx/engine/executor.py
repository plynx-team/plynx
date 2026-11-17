"""Executor protocol and execution data structures (ARCHITECTURE.md section 'Executors')."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from plynx_sdk.protocol import CheckpointManifest, InputsManifest, OutputsManifest

from plynx.api_models import NodeStatus


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


@dataclass(frozen=True)
class LaunchHandle:
    """Opaque handle returned by ``Executor.launch`` (reserved for post-v2.0.0)."""

    handle_id: str
    run_id: str
    node_id: str


@runtime_checkable
class Executor(Protocol):
    """Protocol implemented by node executors (``FakeExecutor``, ``LocalExecutor``)."""

    async def run(self, request: ExecutionRequest) -> NodeResult:
        """Execute a node attempt and wait for it to finish."""
        ...

    async def launch(self, request: ExecutionRequest) -> LaunchHandle:
        """Hand a node to an external engine and return immediately (not implemented in v2.0.0)."""
        ...
