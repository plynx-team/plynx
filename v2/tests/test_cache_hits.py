"""Tests for cache hits, fresh run lookup, --no-cache, and missing blob handling.

PLAN.md task 3.5.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from plynx.api_models import InputPortSpec, NodeStatus, OpEntry, OutputPortSpec, RunStatus
from plynx.cas import BlobStore, make_writable
from plynx.engine.executor import ExecutionRequest, Executor, NodeResult
from plynx.engine.scheduler import Scheduler, SchedulerOptions
from plynx.registry import FakeRegistry
from plynx.store import RunStore
from plynx.workflow.models import Workflow
from plynx_sdk.protocol import (
    OutputFileValue,
    OutputsManifest,
    ScalarValue,
)


class CountingExecutor(Executor):
    """An executor that produces file and scalar outputs and counts execution calls."""

    def __init__(self) -> None:
        self.spawn_count = 0

    async def run(self, request: ExecutionRequest) -> NodeResult:
        self.spawn_count += 1
        workdir = request.node_dir / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        if "ProduceFile" in request.op:
            out_file = workdir / "result.txt"
            out_file.write_text("generated file content", encoding="utf-8")
            outputs = OutputsManifest(
                started_at=10.0,
                finished_at=11.0,
                outputs={
                    "file": OutputFileValue(path="workdir/result.txt", media="text/plain"),
                },
            )
        else:
            in_val = request.inputs.inputs.get("text")
            val = in_val.value if isinstance(in_val, ScalarValue) else "out"
            outputs = OutputsManifest(
                started_at=10.0,
                finished_at=11.0,
                outputs={"out": ScalarValue(value=f"{val}_done")},
            )

        return NodeResult(
            status=NodeStatus.SUCCESS,
            exit_code=0,
            started_at=10.0,
            finished_at=11.0,
            outputs=outputs,
        )

    async def launch(self, request: ExecutionRequest) -> Any:
        raise NotImplementedError


def _cacheable_workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "cache_flow",
            "nodes": {
                "step1": {
                    "op": "test/ops:ProduceFile",
                    "inputs": {},
                },
                "step2": {
                    "op": "test/ops:Echo",
                    "inputs": {"text": "hello"},
                },
            },
        }
    )


def _build_registry() -> FakeRegistry:
    return FakeRegistry(
        [
            OpEntry(
                id="test/ops:ProduceFile",
                pack="test",
                module="ops",
                name="ProduceFile",
                kind="class",
                title="Produce file",
                category="Test",
                cacheable=True,
                description="",
                inputs=[],
                outputs=[OutputPortSpec(name="file", type="file", media="text/plain")],
                source="test/ops.py",
                valid=True,
            ),
            OpEntry(
                id="test/ops:Echo",
                pack="test",
                module="ops",
                name="Echo",
                kind="class",
                title="Echo",
                category="Test",
                cacheable=True,
                description="",
                inputs=[InputPortSpec(name="text", type="str", required=True)],
                outputs=[OutputPortSpec(name="out", type="str")],
                source="test/ops.py",
                valid=True,
            ),
            OpEntry(
                id="test/ops:Uncacheable",
                pack="test",
                module="ops",
                name="Uncacheable",
                kind="class",
                title="Uncacheable",
                category="Test",
                cacheable=False,
                description="",
                inputs=[],
                outputs=[],
                source="test/ops.py",
                valid=True,
            ),
        ]
    )


def test_cache_hits_and_zero_child_spawns(tmp_path: Path) -> None:
    """Accept: second run reports cache_hit = true for all nodes and starts no child process."""
    store = RunStore(tmp_path)
    executor = CountingExecutor()
    registry = _build_registry()
    scheduler = Scheduler(store, executor, registry=registry)
    wf = _cacheable_workflow()

    # Run 1: fresh run, all nodes miss cache and execute
    state1 = asyncio.run(scheduler.run(wf))
    assert state1.status == RunStatus.SUCCESS
    assert executor.spawn_count == 2
    for node in state1.nodes.values():
        assert node.status == NodeStatus.SUCCESS
        assert node.cache_hit is False

    # Run 2: fresh run, all nodes hit cache and no child processes are spawned
    executor.spawn_count = 0
    state2 = asyncio.run(scheduler.run(wf))
    assert state2.status == RunStatus.SUCCESS
    assert executor.spawn_count == 0  # No child process spawned!
    for node in state2.nodes.values():
        assert node.status == NodeStatus.SUCCESS
        assert node.cache_hit is True


def test_deleting_blob_turns_node_into_miss_without_error(tmp_path: Path) -> None:
    """Accept: deleting a blob turns that node into a miss without an error."""
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    executor = CountingExecutor()
    registry = _build_registry()
    scheduler = Scheduler(store, executor, registry=registry, blob_store=blob_store)
    wf = _cacheable_workflow()

    # Initial run to populate cache and CAS
    state1 = asyncio.run(scheduler.run(wf))
    assert state1.status == RunStatus.SUCCESS

    # Find the blob for step1's file output
    run1_node_dir = store.node_dir(state1.id, "step1")
    from plynx_sdk.protocol import ResultFileValue, ResultManifest

    res1 = ResultManifest.from_json((run1_node_dir / "result.json").read_bytes())
    file_val = res1.outputs["file"]
    assert isinstance(file_val, ResultFileValue)
    blob_path = blob_store.blob_path(file_val.sha256)
    assert blob_path.is_file()

    # Delete the blob
    make_writable(blob_path)
    blob_path.unlink()
    assert not blob_path.is_file()

    # Fresh run: step1 misses cache because blob is missing; no error raised!
    executor.spawn_count = 0
    state2 = asyncio.run(scheduler.run(wf))
    assert state2.status == RunStatus.SUCCESS
    # step1 had a missing blob so it executed; step2 had all blobs (scalar) so it hit cache
    assert state2.nodes["step1"].cache_hit is False
    assert state2.nodes["step2"].cache_hit is True
    assert executor.spawn_count == 1
    # Blob was re-created in blob_store
    assert blob_path.is_file()


def test_no_cache_option_bypasses_cache(tmp_path: Path) -> None:
    """Running with --no-cache bypasses cache lookup."""
    store = RunStore(tmp_path)
    executor = CountingExecutor()
    registry = _build_registry()
    scheduler = Scheduler(store, executor, registry=registry)
    wf = _cacheable_workflow()

    # Run 1 populates cache
    asyncio.run(scheduler.run(wf))
    assert executor.spawn_count == 2

    # Run 2 with no_cache=True
    executor.spawn_count = 0
    state2 = asyncio.run(scheduler.run(wf, options=SchedulerOptions(no_cache=True)))
    assert state2.status == RunStatus.SUCCESS
    assert executor.spawn_count == 2
    for node in state2.nodes.values():
        assert node.cache_hit is False


def test_non_cacheable_op_is_never_cached(tmp_path: Path) -> None:
    """An op with cacheable=False is never cached."""
    store = RunStore(tmp_path)
    executor = CountingExecutor()
    registry = _build_registry()
    scheduler = Scheduler(store, executor, registry=registry)

    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "uncacheable_flow",
            "nodes": {
                "uncached": {
                    "op": "test/ops:Uncacheable",
                    "inputs": {},
                },
            },
        }
    )

    asyncio.run(scheduler.run(wf))
    assert executor.spawn_count == 1

    # Second run still misses
    executor.spawn_count = 0
    state2 = asyncio.run(scheduler.run(wf))
    assert state2.status == RunStatus.SUCCESS
    assert executor.spawn_count == 1
    assert state2.nodes["uncached"].cache_hit is False


def test_resume_respects_no_cache_option(tmp_path: Path) -> None:
    """scheduler.resume() uses cache by default and skips cache when options.no_cache=True."""
    store = RunStore(tmp_path)
    executor = CountingExecutor()
    registry = _build_registry()
    scheduler = Scheduler(store, executor, registry=registry)
    wf = _cacheable_workflow()
    wf_yaml = (
        b"version: 1\nname: cache_flow\nnodes:\n"
        b"  step1:\n    op: test/ops:ProduceFile\n    inputs: {}\n"
        b"  step2:\n    op: test/ops:Echo\n    inputs:\n      text: hello\n"
    )

    # 1. Populate cache with a full run.
    state1 = asyncio.run(scheduler.run(wf, workflow_bytes=wf_yaml))
    assert state1.status == RunStatus.SUCCESS
    assert executor.spawn_count == 2

    # 2. Create a failed run where step2 still needs to run; resume with no_cache=False (default).
    run_cached = store.create_run(
        workflow_path="wf.yaml",
        workflow_bytes=wf_yaml,
        node_ids=["step1", "step2"],
        status=RunStatus.FAILED,
    )
    store.update_node_status(run_cached, "step1", NodeStatus.FAILED, attempt=1, error="err")
    store.update_node_status(run_cached, "step2", NodeStatus.PENDING, attempt=0)

    executor.spawn_count = 0
    resumed_cached = asyncio.run(scheduler.resume(run_cached, options=SchedulerOptions()))
    assert resumed_cached.status == RunStatus.SUCCESS
    assert executor.spawn_count == 0
    assert resumed_cached.nodes["step1"].cache_hit is True
    assert resumed_cached.nodes["step2"].cache_hit is True

    # 3. Create another failed run and resume with no_cache=True; both nodes must execute.
    run_uncached = store.create_run(
        workflow_path="wf.yaml",
        workflow_bytes=wf_yaml,
        node_ids=["step1", "step2"],
        status=RunStatus.FAILED,
    )
    store.update_node_status(run_uncached, "step1", NodeStatus.FAILED, attempt=1, error="err")
    store.update_node_status(run_uncached, "step2", NodeStatus.PENDING, attempt=0)

    executor.spawn_count = 0
    resumed_uncached = asyncio.run(
        scheduler.resume(run_uncached, options=SchedulerOptions(no_cache=True))
    )
    assert resumed_uncached.status == RunStatus.SUCCESS
    assert executor.spawn_count == 2
    assert resumed_uncached.nodes["step1"].cache_hit is False
    assert resumed_uncached.nodes["step2"].cache_hit is False
