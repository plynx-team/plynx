"""DAG workflow scheduler using ``graphlib.TopologicalSorter`` and ``asyncio``."""

from __future__ import annotations

import asyncio
import graphlib
import os
import shutil
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plynx_sdk.protocol import (
    CheckpointManifest,
    DirectoryEntry,
    InputDirectoryValue,
    InputFileValue,
    InputsManifest,
    InputValue,
    OutputDirectoryValue,
    OutputFileValue,
    OutputValue,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ResultValue,
    ScalarValue,
)

from plynx.api_models import (
    CheckpointResolvedData,
    NodeCheckpointData,
    NodeStatus,
    NodeStatusData,
    RunState,
    RunStatus,
    RunStatusData,
)
from plynx.engine.executor import ExecutionRequest, Executor
from plynx.registry import FakeRegistry, OpRegistry
from plynx.store.run_store import RunStore, atomic_write_text
from plynx.workflow.models import NodeRef, NodeSpec, Workflow

CheckpointCallback = Callable[[str, str, CheckpointManifest], Awaitable[str | None] | str | None]
NodeStatusCallback = Callable[[str, NodeStatus, int], None]


@dataclass
class SchedulerOptions:
    """Options controlling a single workflow scheduler invocation."""

    concurrency: int | None = None
    run_inputs: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    non_interactive: bool = False
    no_cache: bool = False
    checkpoint_callback: CheckpointCallback | None = None
    on_node_status: NodeStatusCallback | None = None


def _output_to_input_value(
    val: OutputValue,
    *,
    src_node_dir: Path | None = None,
    dst_node_dir: Path | None = None,
    port_name: str | None = None,
) -> InputValue:
    if isinstance(val, ScalarValue):
        return ScalarValue(value=val.value)
    if isinstance(val, OutputFileValue):
        if src_node_dir is not None and dst_node_dir is not None and port_name is not None:
            src_file = src_node_dir / val.path
            if src_file.is_file():
                filename = src_file.name
                dst_file = dst_node_dir / "inputs" / port_name / filename
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                if dst_file.exists():
                    dst_file.unlink()
                try:
                    os.link(src_file, dst_file)
                except OSError:
                    shutil.copy2(src_file, dst_file)
                return InputFileValue(
                    path=f"inputs/{port_name}/{filename}",
                    sha256="fake",
                    size_bytes=dst_file.stat().st_size,
                )
        return InputFileValue(path=val.path, sha256="fake", size_bytes=0)
    if isinstance(val, OutputDirectoryValue):
        if src_node_dir is not None and dst_node_dir is not None and port_name is not None:
            src_dir = src_node_dir / val.path
            if src_dir.is_dir():
                dst_dir = dst_node_dir / "inputs" / port_name
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                return InputDirectoryValue(path=f"inputs/{port_name}", tree_sha256="fake")
        return InputDirectoryValue(path=val.path, tree_sha256="fake")
    raise TypeError(f"Unsupported OutputValue: {type(val).__name__}")


def _output_to_result_value(val: OutputValue) -> ResultValue:
    if isinstance(val, ScalarValue):
        return ScalarValue(value=val.value)
    if isinstance(val, OutputFileValue):
        filename = Path(val.path).name or "output"
        return ResultFileValue(
            sha256="fake",
            size_bytes=0,
            media=val.media,
            filename=filename,
        )
    if isinstance(val, OutputDirectoryValue):
        return ResultDirectoryValue(
            tree_sha256="fake",
            entries=[DirectoryEntry(path="placeholder", sha256="fake", size_bytes=0)],
        )
    raise TypeError(f"Unsupported OutputValue: {type(val).__name__}")


class Scheduler:
    """Executes a validated ``Workflow`` DAG against a ``RunStore`` and an ``Executor``."""

    def __init__(
        self,
        store: RunStore,
        executor: Executor,
        registry: OpRegistry | None = None,
    ) -> None:
        self.store = store
        self.executor = executor
        self.registry: OpRegistry = FakeRegistry() if registry is None else registry

    async def run(
        self,
        workflow: Workflow,
        *,
        workflow_path: str = "workflow.yaml",
        workflow_bytes: bytes | None = None,
        layout_bytes: bytes | None = None,
        run_id: str | None = None,
        options: SchedulerOptions | None = None,
    ) -> RunState:
        """Schedule and run ``workflow``, writing statuses and events to ``self.store``."""
        opts = options or SchedulerOptions()
        concurrency = opts.concurrency or workflow.concurrency or (os.cpu_count() or 1)
        if concurrency < 1:
            concurrency = 1

        raw_wf = (
            workflow_bytes
            if workflow_bytes is not None
            else f"version: 1\nname: {workflow.name or 'workflow'}\n".encode()
        )
        node_ids = list(workflow.nodes.keys())
        existing_state = (
            await asyncio.to_thread(self.store.get_run_state, run_id)
            if run_id is not None
            else None
        )
        if existing_state is not None and run_id is not None:
            active_run_id = run_id
        else:
            active_run_id = await asyncio.to_thread(
                self.store.create_run,
                workflow_path=workflow_path,
                workflow_bytes=raw_wf,
                layout_bytes=layout_bytes,
                node_ids=node_ids,
                run_inputs=opts.run_inputs,
                run_id=run_id,
            )
        event_log = self.store.event_log(active_run_id)

        await asyncio.to_thread(
            event_log.append,
            "run_status",
            RunStatusData(run_id=active_run_id, status=RunStatus.RUNNING),
        )

        node_statuses: dict[str, NodeStatus] = {}
        node_attempts: dict[str, int] = dict.fromkeys(node_ids, 0)
        completed_outputs: dict[str, dict[str, OutputValue]] = {}

        for nid in node_ids:
            node_statuses[nid] = NodeStatus.PENDING
            await asyncio.to_thread(
                event_log.append,
                "node_status",
                NodeStatusData(
                    run_id=active_run_id,
                    node_id=nid,
                    status=NodeStatus.PENDING,
                    cache_hit=False,
                    attempt=0,
                ),
            )
            if opts.on_node_status is not None:
                opts.on_node_status(nid, NodeStatus.PENDING, 0)

        dep_graph: dict[str, set[str]] = {nid: set() for nid in node_ids}
        for nid, spec in workflow.nodes.items():
            for val in spec.inputs.values():
                if isinstance(val, NodeRef) and val.from_node in workflow.nodes:
                    dep_graph[nid].add(val.from_node)

        sorter = graphlib.TopologicalSorter(dep_graph)
        sorter.prepare()

        semaphore = asyncio.Semaphore(concurrency)
        running_tasks: dict[asyncio.Task[tuple[str, bool]], str] = {}

        async def _emit_node_status(
            nid: str,
            status: NodeStatus,
            *,
            attempt: int = 0,
            cache_hit: bool = False,
            exit_code: int | None = None,
            error: str | None = None,
            started_at: float | None = None,
            finished_at: float | None = None,
        ) -> None:
            node_statuses[nid] = status
            await asyncio.to_thread(
                self.store.update_node_status,
                active_run_id,
                nid,
                status,
                cache_hit=cache_hit,
                attempt=attempt,
                exit_code=exit_code,
                error=error,
                started_at=started_at,
                finished_at=finished_at,
            )
            await asyncio.to_thread(
                event_log.append,
                "node_status",
                NodeStatusData(
                    run_id=active_run_id,
                    node_id=nid,
                    status=status,
                    cache_hit=cache_hit,
                    attempt=attempt,
                    exit_code=exit_code,
                    error=error,
                ),
            )
            if opts.on_node_status is not None:
                opts.on_node_status(nid, status, attempt)

        async def _execute_node(nid: str) -> tuple[str, bool]:
            spec = workflow.nodes[nid]
            node_dir = self.store.node_dir(active_run_id, nid)

            async with semaphore:
                while True:
                    attempt = node_attempts[nid] + 1
                    node_attempts[nid] = attempt
                    inputs_manifest = self._build_inputs_manifest(
                        active_run_id,
                        nid,
                        spec,
                        completed_outputs,
                        opts,
                    )
                    await asyncio.to_thread(
                        atomic_write_text,
                        node_dir / "inputs.json",
                        inputs_manifest.to_json(),
                    )
                    started_ts = time.time()
                    emitted_running = False

                    async def _on_attempt_status(
                        st: NodeStatus,
                        *,
                        _nid: str = nid,
                        _attempt: int = attempt,
                    ) -> None:
                        nonlocal emitted_running, started_ts
                        if st == NodeStatus.RUNNING:
                            if emitted_running:
                                return
                            emitted_running = True
                            started_ts = time.time()
                            await _emit_node_status(
                                _nid,
                                NodeStatus.RUNNING,
                                attempt=_attempt,
                                started_at=started_ts,
                            )
                        elif st == NodeStatus.BUILDING_ENVIRONMENT:
                            await _emit_node_status(
                                _nid,
                                NodeStatus.BUILDING_ENVIRONMENT,
                                attempt=_attempt,
                            )

                    req = ExecutionRequest(
                        run_id=active_run_id,
                        node_id=nid,
                        op=spec.op,
                        attempt=attempt,
                        node_dir=node_dir,
                        inputs=inputs_manifest,
                        on_status=_on_attempt_status,
                    )
                    result = await self.executor.run(req)
                    if not emitted_running:
                        await _on_attempt_status(NodeStatus.RUNNING)

                    if result.status == NodeStatus.SUCCESS:
                        outs = result.outputs.outputs if result.outputs is not None else {}
                        completed_outputs[nid] = dict(outs)
                        result_manifest = ResultManifest(
                            status="SUCCESS",
                            cache_key="fake",
                            cache_hit=False,
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                            outputs={k: _output_to_result_value(v) for k, v in outs.items()},
                        )
                        await asyncio.to_thread(
                            atomic_write_text,
                            node_dir / "result.json",
                            result_manifest.to_json(),
                        )
                        await _emit_node_status(
                            nid,
                            NodeStatus.SUCCESS,
                            attempt=attempt,
                            exit_code=result.exit_code,
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                        )
                        return nid, True

                    if (
                        result.status == NodeStatus.WAITING_FOR_USER
                        and result.checkpoint is not None
                    ):
                        cp = result.checkpoint
                        await asyncio.to_thread(
                            self.store.create_checkpoint,
                            active_run_id,
                            nid,
                            cp.checkpoint_id,
                            cp.question,
                            options=cp.options,
                            allow_freeform=cp.allow_freeform,
                        )
                        await _emit_node_status(
                            nid,
                            NodeStatus.WAITING_FOR_USER,
                            attempt=attempt,
                            exit_code=result.exit_code,
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                        )
                        await asyncio.to_thread(
                            event_log.append,
                            "node_checkpoint",
                            NodeCheckpointData(
                                run_id=active_run_id,
                                node_id=nid,
                                checkpoint_id=cp.checkpoint_id,
                                question=cp.question,
                                options=cp.options,
                                allow_freeform=cp.allow_freeform,
                            ),
                        )

                        answer = await self._resolve_checkpoint_answer(
                            active_run_id,
                            nid,
                            cp,
                            opts,
                        )
                        if answer is None:
                            return nid, False

                        won = await asyncio.to_thread(
                            self.store.answer_checkpoint,
                            active_run_id,
                            nid,
                            cp.checkpoint_id,
                            answer,
                        )
                        if won:
                            await asyncio.to_thread(
                                event_log.append,
                                "checkpoint_resolved",
                                CheckpointResolvedData(
                                    run_id=active_run_id,
                                    node_id=nid,
                                    checkpoint_id=cp.checkpoint_id,
                                ),
                            )
                        opts.answers[f"{nid}.{cp.checkpoint_id}"] = answer
                        continue

                    await _emit_node_status(
                        nid,
                        result.status,
                        attempt=attempt,
                        exit_code=result.exit_code,
                        error=result.error,
                        started_at=result.started_at,
                        finished_at=result.finished_at,
                    )
                    return nid, True

        while sorter.is_active():
            ready_nodes = list(sorter.get_ready())
            blocked_progressed = False
            for nid in ready_nodes:
                deps = dep_graph[nid]
                if any(
                    node_statuses.get(dep)
                    in (NodeStatus.FAILED, NodeStatus.CANCELED, NodeStatus.BLOCKED)
                    for dep in deps
                ):
                    await _emit_node_status(nid, NodeStatus.BLOCKED, attempt=0)
                    sorter.done(nid)
                    blocked_progressed = True
                else:
                    task = asyncio.create_task(_execute_node(nid))
                    running_tasks[task] = nid

            if blocked_progressed and not running_tasks:
                continue
            if not running_tasks:
                break

            done, _ = await asyncio.wait(
                running_tasks.keys(),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for completed_task in done:
                running_tasks.pop(completed_task, None)
                finished_nid, mark_done = await completed_task
                if mark_done:
                    sorter.done(finished_nid)

        final_status = self._compute_final_run_status(node_statuses)
        finished_ts = (
            time.time()
            if final_status in (RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELED)
            else None
        )
        run_error: str | None = None
        if final_status == RunStatus.FAILED:
            failed_nodes = [nid for nid, st in node_statuses.items() if st == NodeStatus.FAILED]
            run_error = f"Failed node(s): {', '.join(failed_nodes)}"

        await asyncio.to_thread(
            self.store.update_run_status,
            active_run_id,
            final_status,
            finished_at=finished_ts,
            error=run_error,
        )
        await asyncio.to_thread(
            event_log.append,
            "run_status",
            RunStatusData(run_id=active_run_id, status=final_status, error=run_error),
        )

        final_state = await asyncio.to_thread(self.store.get_run_state, active_run_id)
        assert final_state is not None
        return final_state

    def _build_inputs_manifest(
        self,
        run_id: str,
        node_id: str,
        spec: NodeSpec,
        completed_outputs: Mapping[str, Mapping[str, OutputValue]],
        opts: SchedulerOptions,
    ) -> InputsManifest:
        op_entry = self.registry.get(spec.op)
        port_defaults: dict[str, Any] = {}
        if op_entry is not None:
            for port in op_entry.inputs:
                if not port.required and port.default is not None:
                    port_defaults[port.name] = port.default

        resolved_inputs: dict[str, InputValue] = {}
        for port_name, default_val in port_defaults.items():
            resolved_inputs[port_name] = ScalarValue(value=default_val)

        dst_node_dir = self.store.node_dir(run_id, node_id)
        for port_name, binding in spec.inputs.items():
            if isinstance(binding, NodeRef):
                src_outs = completed_outputs.get(binding.from_node, {})
                if binding.output in src_outs:
                    src_node_dir = self.store.node_dir(run_id, binding.from_node)
                    resolved_inputs[port_name] = _output_to_input_value(
                        src_outs[binding.output],
                        src_node_dir=src_node_dir,
                        dst_node_dir=dst_node_dir,
                        port_name=port_name,
                    )
            else:
                resolved_inputs[port_name] = ScalarValue(value=binding)

        prefix = f"{node_id}."
        for key, raw_val in opts.run_inputs.items():
            if key.startswith(prefix):
                port_name = key[len(prefix) :]
                resolved_inputs[port_name] = ScalarValue(value=raw_val)

        cp_answers: dict[str, str] = {}
        for key, ans in opts.answers.items():
            if key.startswith(prefix):
                cp_id = key[len(prefix) :]
                cp_answers[cp_id] = ans

        state = self.store.get_run_state(run_id)
        if state is not None:
            for cp in state.checkpoints:
                if cp.node_id == node_id and cp.answer is not None:
                    cp_answers[cp.checkpoint_id] = cp.answer

        return InputsManifest(inputs=resolved_inputs, checkpoint_answers=cp_answers)

    async def _resolve_checkpoint_answer(
        self,
        run_id: str,
        node_id: str,
        cp: CheckpointManifest,
        opts: SchedulerOptions,
    ) -> str | None:
        key = f"{node_id}.{cp.checkpoint_id}"
        if key in opts.answers:
            return opts.answers[key]

        existing = await asyncio.to_thread(
            self.store.get_checkpoint,
            run_id,
            node_id,
            cp.checkpoint_id,
        )
        if existing is not None and existing.answer is not None:
            return existing.answer

        if opts.non_interactive:
            return None

        if opts.checkpoint_callback is not None:
            maybe_coro = opts.checkpoint_callback(node_id, cp.checkpoint_id, cp)
            if isinstance(maybe_coro, Awaitable):
                return await maybe_coro
            return maybe_coro

        if cp.options:
            return cp.options[0]
        return ""

    @staticmethod
    def _compute_final_run_status(node_statuses: Mapping[str, NodeStatus]) -> RunStatus:
        statuses = set(node_statuses.values())
        if NodeStatus.CANCELED in statuses:
            return RunStatus.CANCELED
        if NodeStatus.FAILED in statuses:
            return RunStatus.FAILED
        if NodeStatus.WAITING_FOR_USER in statuses:
            return RunStatus.WAITING_FOR_USER
        return RunStatus.SUCCESS
