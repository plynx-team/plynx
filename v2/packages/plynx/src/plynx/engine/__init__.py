"""Workflow execution engine: executor protocol, local/fake executors, and DAG scheduler."""

from pathlib import Path

from plynx.engine.executor import (
    ExecutionRequest,
    Executor,
    LaunchHandle,
    NodeResult,
    StatusCallback,
)
from plynx.engine.fake_executor import (
    FakeExecutionRecord,
    FakeExecutor,
    FakeNodeScript,
)
from plynx.engine.runner import LocalExecutor
from plynx.engine.scheduler import Scheduler, SchedulerOptions


def create_executor(workspace_root: Path | None = None) -> Executor:
    """Return the default ``Executor`` instance (``LocalExecutor``)."""
    return LocalExecutor(workspace_root)


__all__ = [
    "ExecutionRequest",
    "Executor",
    "FakeExecutionRecord",
    "FakeExecutor",
    "FakeNodeScript",
    "LaunchHandle",
    "LocalExecutor",
    "NodeResult",
    "Scheduler",
    "SchedulerOptions",
    "StatusCallback",
    "create_executor",
]
