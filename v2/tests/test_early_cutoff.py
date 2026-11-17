"""Tests for early cutoff caching (PROTOCOL.md section 6, PLAN.md task 3.6)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from plynx.api_models import InputPortSpec, NodeStatus, OpEntry, OutputPortSpec, RunStatus
from plynx.cas import BlobStore
from plynx.engine.executor import ExecutionRequest, Executor, NodeResult
from plynx.engine.scheduler import Scheduler
from plynx.registry import FakeRegistry
from plynx.store import RunStore
from plynx.workflow.models import Workflow
from plynx_sdk.protocol import (
    OutputFileValue,
    OutputsManifest,
    ScalarValue,
)


class EarlyCutoffExecutor(Executor):
    """Executor tracking executions for upstream and downstream nodes."""

    def __init__(self) -> None:
        self.executions: list[str] = []

    async def run(self, request: ExecutionRequest) -> NodeResult:
        self.executions.append(request.node_id)
        workdir = request.node_dir / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        if request.node_id == "upstream":
            # Normalizes input text by stripping whitespace, producing a file
            text_inp = request.inputs.inputs.get("raw")
            raw_val = text_inp.value if isinstance(text_inp, ScalarValue) else ""
            normalized = str(raw_val).strip()

            out_file = workdir / "normalized.txt"
            out_file.write_text(normalized, encoding="utf-8")

            outputs = OutputsManifest(
                started_at=10.0,
                finished_at=11.0,
                outputs={
                    "file": OutputFileValue(path="workdir/normalized.txt", media="text/plain"),
                },
            )
        else:
            # Downstream node consumes the file
            outputs = OutputsManifest(
                started_at=10.0,
                finished_at=11.0,
                outputs={"done": ScalarValue(value=True)},
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


def _build_pipeline(raw_input: str) -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "cutoff_pipeline",
            "nodes": {
                "upstream": {
                    "op": "test/ops:Normalize",
                    "inputs": {"raw": raw_input},
                },
                "downstream": {
                    "op": "test/ops:ConsumeFile",
                    "inputs": {"file": "$upstream.file"},
                },
            },
        }
    )


def _build_registry() -> FakeRegistry:
    return FakeRegistry(
        [
            OpEntry(
                id="test/ops:Normalize",
                pack="test",
                module="ops",
                name="Normalize",
                kind="class",
                title="Normalize",
                category="Test",
                cacheable=True,
                description="",
                inputs=[InputPortSpec(name="raw", type="str", required=True)],
                outputs=[OutputPortSpec(name="file", type="file", media="text/plain")],
                source="test/ops.py",
                valid=True,
            ),
            OpEntry(
                id="test/ops:ConsumeFile",
                pack="test",
                module="ops",
                name="ConsumeFile",
                kind="class",
                title="Consume file",
                category="Test",
                cacheable=True,
                description="",
                inputs=[InputPortSpec(name="file", type="file", media="text/plain", required=True)],
                outputs=[OutputPortSpec(name="done", type="bool")],
                source="test/ops.py",
                valid=True,
            ),
        ]
    )


def test_early_cutoff_downstream_hits_cache_when_upstream_output_bytes_identical(
    tmp_path: Path,
) -> None:
    """Accept: change an upstream input so its output bytes stay identical.

    Downstream nodes still hit cache.
    """
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    executor = EarlyCutoffExecutor()
    registry = _build_registry()
    scheduler = Scheduler(store, executor, registry=registry, blob_store=blob_store)

    # Run 1: initial run with raw input containing surrounding whitespace
    wf1 = _build_pipeline("   same content   ")
    state1 = asyncio.run(scheduler.run(wf1))
    assert state1.status == RunStatus.SUCCESS
    assert state1.nodes["upstream"].cache_hit is False
    assert state1.nodes["downstream"].cache_hit is False
    assert executor.executions == ["upstream", "downstream"]

    # Run 2: change upstream input, but normalized output bytes will remain identical
    wf2 = _build_pipeline("same content\n\n\t")
    executor.executions.clear()

    state2 = asyncio.run(scheduler.run(wf2))
    assert state2.status == RunStatus.SUCCESS
    # Upstream input changed -> upstream cache key changed -> upstream misses and re-runs
    assert state2.nodes["upstream"].cache_hit is False
    assert "upstream" in executor.executions

    # But upstream output bytes were identical ("same content")!
    # Downstream's cache key depends only on its input hashes (the upstream output sha256).
    # Therefore downstream gets a cache hit and does NOT re-run!
    assert state2.nodes["downstream"].cache_hit is True
    assert "downstream" not in executor.executions
