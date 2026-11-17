"""Workflow execution engine: executor protocol, fake executor, and DAG scheduler."""

from pathlib import Path

from plynx.engine.executor import (
    ExecutionRequest,
    Executor,
    LaunchHandle,
    NodeResult,
)
from plynx.engine.fake_executor import (
    FakeExecutionRecord,
    FakeExecutor,
    FakeNodeScript,
)
from plynx.engine.scheduler import Scheduler, SchedulerOptions


def create_executor(workspace_root: Path | None = None) -> Executor:
    """Return the default ``Executor`` instance (``FakeExecutor`` in Phase 0)."""
    _ = workspace_root
    return FakeExecutor()


__all__ = [
    "ExecutionRequest",
    "Executor",
    "FakeExecutionRecord",
    "FakeExecutor",
    "FakeNodeScript",
    "LaunchHandle",
    "NodeResult",
    "Scheduler",
    "SchedulerOptions",
    "create_executor",
]
