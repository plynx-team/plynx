"""In-memory ``FakeExecutor`` with scripted results, delays, failures, and checkpoints."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from plynx_sdk.protocol import (
    CheckpointManifest,
    InputsManifest,
    OutputsManifest,
    OutputValue,
    ScalarValue,
)

from plynx.api_models import NodeStatus
from plynx.engine.executor import ExecutionRequest, LaunchHandle, NodeResult
from plynx.store.run_store import atomic_write_text

OutputsFactory = Callable[[InputsManifest], Mapping[str, OutputValue]]


@dataclass
class FakeNodeScript:
    """Scripted behavior for a single node in ``FakeExecutor``."""

    delay: float = 0.0
    fail: bool = False
    exit_code: int | None = None
    error: str | None = None
    checkpoint: CheckpointManifest | None = None
    outputs: Mapping[str, OutputValue] | OutputsFactory | None = None


@dataclass(frozen=True)
class FakeExecutionRecord:
    """Recorded execution span and inputs for a node attempt in ``FakeExecutor``."""

    run_id: str
    node_id: str
    op: str
    attempt: int
    started_at: float
    finished_at: float
    inputs: InputsManifest
    status: NodeStatus


def _default_outputs_for_op(op: str, inputs: InputsManifest) -> dict[str, OutputValue]:
    if op == "standard_io/demo:Echo":
        text_in = inputs.inputs.get("text")
        val = text_in.value if isinstance(text_in, ScalarValue) else ""
        return {"text": ScalarValue(value=val)}
    if op in ("standard_io/demo:Concat", "standard_io/text:Concat"):
        a_in = inputs.inputs.get("a")
        b_in = inputs.inputs.get("b")
        a_str = str(a_in.value) if isinstance(a_in, ScalarValue) and a_in.value is not None else ""
        b_str = str(b_in.value) if isinstance(b_in, ScalarValue) and b_in.value is not None else " "
        return {"text": ScalarValue(value=a_str + b_str)}
    outputs: dict[str, OutputValue] = {}
    for key, item in inputs.inputs.items():
        if isinstance(item, ScalarValue):
            outputs[key] = ScalarValue(value=item.value)
    return outputs


@dataclass
class FakeExecutor:
    """Fake ``Executor`` supporting scripted outputs, delays, failures, and checkpoints."""

    scripts: dict[str, FakeNodeScript] = field(default_factory=dict)
    default_delay: float = 0.0
    executions: list[FakeExecutionRecord] = field(default_factory=list)
    active_count: int = 0
    max_active_count: int = 0

    def __init__(
        self,
        scripts: Mapping[str, FakeNodeScript] | None = None,
        *,
        default_delay: float = 0.0,
    ) -> None:
        self.scripts = dict(scripts) if scripts is not None else {}
        self.default_delay = default_delay
        self.executions = []
        self.active_count = 0
        self.max_active_count = 0

    async def launch(self, request: ExecutionRequest) -> LaunchHandle:
        """Raise ``NotImplementedError`` per ARCHITECTURE.md."""
        raise NotImplementedError("Executor.launch is not implemented in v2.0.0")

    async def run(self, request: ExecutionRequest) -> NodeResult:
        """Run a scripted or default fake node attempt."""
        self.active_count += 1
        if self.active_count > self.max_active_count:
            self.max_active_count = self.active_count

        started_at = time.time()
        try:
            script = self.scripts.get(request.node_id)
            delay = script.delay if script is not None else self.default_delay
            if delay > 0:
                await asyncio.sleep(delay)

            checkpoint = self._resolve_checkpoint(request, script)
            if (
                checkpoint is not None
                and checkpoint.checkpoint_id not in request.inputs.checkpoint_answers
            ):
                finished_at = time.time()
                atomic_write_text(
                    request.node_dir / "checkpoint.json",
                    checkpoint.to_json(),
                )
                return self._record_and_return(
                    request,
                    NodeResult(
                        status=NodeStatus.WAITING_FOR_USER,
                        exit_code=10,
                        started_at=started_at,
                        finished_at=finished_at,
                        checkpoint=checkpoint,
                    ),
                )

            if script is not None and script.fail:
                finished_at = time.time()
                code = script.exit_code if script.exit_code is not None else 1
                err = script.error or f"Node '{request.node_id}' failed"
                return self._record_and_return(
                    request,
                    NodeResult(
                        status=NodeStatus.FAILED,
                        exit_code=code,
                        started_at=started_at,
                        finished_at=finished_at,
                        error=err,
                    ),
                )

            outputs_map = self._resolve_outputs(request, script, checkpoint)
            finished_at = time.time()
            if finished_at < started_at:
                finished_at = started_at
            outputs_manifest = OutputsManifest(
                started_at=started_at,
                finished_at=finished_at,
                outputs=outputs_map,
            )
            atomic_write_text(
                request.node_dir / "outputs.json",
                outputs_manifest.to_json(),
            )
            return self._record_and_return(
                request,
                NodeResult(
                    status=NodeStatus.SUCCESS,
                    exit_code=0,
                    started_at=started_at,
                    finished_at=finished_at,
                    outputs=outputs_manifest,
                ),
            )
        finally:
            self.active_count -= 1

    def _resolve_checkpoint(
        self,
        request: ExecutionRequest,
        script: FakeNodeScript | None,
    ) -> CheckpointManifest | None:
        if script is not None and script.checkpoint is not None:
            return script.checkpoint
        if request.op == "standard_io/demo:AskFooOrWoo":
            prompt_in = request.inputs.inputs.get("prompt")
            question = (
                str(prompt_in.value)
                if isinstance(prompt_in, ScalarValue) and prompt_in.value
                else "foo or woo?"
            )
            return CheckpointManifest(
                checkpoint_id="cp_0",
                question=question,
                options=["foo", "woo"],
                allow_freeform=False,
            )
        return None

    def _resolve_outputs(
        self,
        request: ExecutionRequest,
        script: FakeNodeScript | None,
        checkpoint: CheckpointManifest | None,
    ) -> dict[str, OutputValue]:
        if script is not None and script.outputs is not None:
            if callable(script.outputs):
                return dict(script.outputs(request.inputs))
            return dict(script.outputs)
        if request.op == "standard_io/demo:AskFooOrWoo" and checkpoint is not None:
            answer = request.inputs.checkpoint_answers[checkpoint.checkpoint_id]
            return {"choice": ScalarValue(value=answer)}
        return _default_outputs_for_op(request.op, request.inputs)

    def _record_and_return(self, request: ExecutionRequest, result: NodeResult) -> NodeResult:
        self.executions.append(
            FakeExecutionRecord(
                run_id=request.run_id,
                node_id=request.node_id,
                op=request.op,
                attempt=request.attempt,
                started_at=result.started_at,
                finished_at=result.finished_at,
                inputs=request.inputs,
                status=result.status,
            )
        )
        return result


def scalar_outputs(**kwargs: Any) -> dict[str, OutputValue]:
    """Build a mapping of ``ScalarValue`` outputs for tests."""
    return {key: ScalarValue(value=val) for key, val in kwargs.items()}
