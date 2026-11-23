"""DAG workflow scheduler using ``graphlib.TopologicalSorter`` and ``asyncio``."""

from __future__ import annotations

import asyncio
import contextlib
import graphlib
import os
import time
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plynx_sdk.protocol import (
    CheckpointManifest,
    InputFileValue,
    InputsManifest,
    OutputValue,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ResultValue,
    ScalarValue,
)

from plynx.api_models import (
    CheckpointResolvedData,
    CheckpointResolvedEvent,
    CheckpointState,
    NodeCheckpointData,
    NodeStatus,
    NodeStatusData,
    RunState,
    RunStatus,
    RunStatusData,
    StageApprovalData,
    StageGateKind,
    StageGateStatus,
    StageResolvedData,
    StageResolvedEvent,
    WorkflowInputSpec,
)
from plynx.cas import (
    BlobStore,
    compute_cache_key,
    compute_cache_key_raw,
    compute_inputs_hash,
    compute_params_hash,
    enforce_cache_budget,
    ingest_outputs,
    materialize_inputs,
    write_result_manifest,
)
from plynx.config import load_workspace_config
from plynx.engine.executor import ExecutionRequest, Executor, NodeResult
from plynx.registry import OpRegistry, PackRegistry
from plynx.store.event_log import EventLog
from plynx.store.run_store import RunNotFoundError, RunStore, atomic_write_text
from plynx.workflow.models import NodeRef, NodeSpec, Workflow, parse_workflow_yaml

CheckpointCallback = Callable[[str, str, CheckpointManifest], Awaitable[str | None] | str | None]
StageApprovalCallback = Callable[[str, str], Awaitable[bool] | bool]
StageInputsCallback = Callable[
    [str, str, list[WorkflowInputSpec]],
    Awaitable[dict[str, Any] | None] | dict[str, Any] | None,
]
NodeStatusCallback = Callable[[str, NodeStatus, int], None]


@dataclass
class SchedulerOptions:
    """Options controlling a single workflow scheduler invocation."""

    concurrency: int | None = None
    run_inputs: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, str] = field(default_factory=dict)
    non_interactive: bool = False
    no_cache: bool = False
    poll_interval: float = 0.2
    cancel_event: asyncio.Event | None = None
    checkpoint_callback: CheckpointCallback | None = None
    stage_approval_callback: StageApprovalCallback | None = None
    stage_inputs_callback: StageInputsCallback | None = None
    on_node_status: NodeStatusCallback | None = None


class _RunExecution:
    """Explicit per-run execution state and orchestration for ``Scheduler.run()``."""

    def __init__(
        self,
        scheduler: Scheduler,
        workflow: Workflow,
        active_run_id: str,
        concurrency: int,
        opts: SchedulerOptions,
    ) -> None:
        self.scheduler = scheduler
        self.store = scheduler.store
        self.workflow = workflow
        self.active_run_id = active_run_id
        self.opts = opts
        self.event_log: EventLog = self.store.event_log(active_run_id)
        self.resolved_answers: dict[str, str] = dict(opts.answers)
        self.current_run_status = RunStatus.RUNNING
        self.run_status_lock = asyncio.Lock()

        self.node_ids = list(workflow.nodes.keys())
        self.node_statuses: dict[str, NodeStatus] = {}
        self.node_attempts: dict[str, int] = dict.fromkeys(self.node_ids, 0)
        self.completed_outputs: dict[str, dict[str, ResultValue | OutputValue]] = {}
        self.precompleted_nodes: set[str] = set()
        self.resuming_waiting_nodes: dict[str, CheckpointState] = {}

        self.dep_graph: dict[str, set[str]] = {nid: set() for nid in self.node_ids}
        for nid, spec in workflow.nodes.items():
            for val in spec.inputs.values():
                if isinstance(val, NodeRef) and val.from_node in workflow.nodes:
                    self.dep_graph[nid].add(val.from_node)

        self.sorter: graphlib.TopologicalSorter[str] = graphlib.TopologicalSorter(self.dep_graph)
        self.sorter.prepare()

        self.stage_order = list(workflow.stages.keys())
        self.stage_index = {sid: idx for idx, sid in enumerate(self.stage_order)}
        self.stage_nodes: dict[str, list[str]] = {sid: [] for sid in self.stage_order}
        for nid, spec in workflow.nodes.items():
            self.stage_nodes.setdefault(spec.stage, []).append(nid)

        self.semaphore = asyncio.Semaphore(concurrency)
        self.running_tasks: dict[asyncio.Task[tuple[str, bool]], str] = {}
        self.gate_tasks: dict[
            asyncio.Task[tuple[str, StageGateKind, bool]],
            tuple[str, StageGateKind],
        ] = {}
        self.runnable_nodes: set[str] = set()
        self.waiting_nodes: set[str] = set()
        self.waiting_gates: set[tuple[str, StageGateKind]] = set()
        self.opened_input_gates: set[str] = set()
        self.approved_input_gates: set[str] = set()
        self.opened_approval_gates: set[str] = set()
        self.approved_approval_gates: set[str] = set()
        self.emitted_cp_resolutions: set[tuple[str, str]] = set()
        self.emitted_gate_resolutions: set[tuple[str, StageGateKind]] = set()

        self.cancel_event = opts.cancel_event if opts.cancel_event is not None else asyncio.Event()
        self.poll_sleep = max(opts.poll_interval, 0.005)
        self.pending_discard: list[str] = []
        self.deferred_ready: list[str] = []

    async def execute(self, *, resume: bool, existing_state: RunState | None) -> RunState:
        """Execute the workflow run from start to finish."""
        await asyncio.to_thread(
            self.event_log.append,
            "run_status",
            RunStatusData(run_id=self.active_run_id, status=RunStatus.RUNNING),
        )
        await self._init_nodes_state(resume=resume, existing_state=existing_state)
        if resume and existing_state is not None:
            await self._restore_stage_gates()

        cancel_poller_task: asyncio.Task[None] = asyncio.create_task(self._poll_cancel_requested())
        try:
            await self._run_main_loop()
        finally:
            if not cancel_poller_task.done():
                cancel_poller_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await cancel_poller_task

        for done_nid in self.pending_discard:
            self.runnable_nodes.discard(done_nid)
        self.pending_discard.clear()

        return await self._finalize_run()

    async def _init_nodes_state(
        self,
        *,
        resume: bool,
        existing_state: RunState | None,
    ) -> None:
        if not (resume and existing_state is not None):
            for nid in self.node_ids:
                self.node_statuses[nid] = NodeStatus.PENDING
                await asyncio.to_thread(
                    self.event_log.append,
                    "node_status",
                    NodeStatusData(
                        run_id=self.active_run_id,
                        node_id=nid,
                        status=NodeStatus.PENDING,
                        cache_hit=False,
                        attempt=0,
                    ),
                )
                if self.opts.on_node_status is not None:
                    self.opts.on_node_status(nid, NodeStatus.PENDING, 0)
            return

        prior_events = await asyncio.to_thread(self.event_log.read_after, 0)
        for ev in prior_events:
            if isinstance(ev, CheckpointResolvedEvent):
                self.emitted_cp_resolutions.add((ev.data.node_id, ev.data.checkpoint_id))
            elif isinstance(ev, StageResolvedEvent):
                self.emitted_gate_resolutions.add((ev.data.stage_id, ev.data.kind))

        cps_by_node: dict[str, list[CheckpointState]] = {}
        for cp_state in existing_state.checkpoints:
            cps_by_node.setdefault(cp_state.node_id, []).append(cp_state)

        for nid in self.node_ids:
            prev_node = existing_state.nodes.get(nid)
            if prev_node is not None and prev_node.status == NodeStatus.SUCCESS:
                res_path = self.store.node_dir(self.active_run_id, nid) / "result.json"
                if res_path.is_file():
                    try:
                        raw_res = await asyncio.to_thread(res_path.read_bytes)
                        res_manifest = ResultManifest.from_json(raw_res)
                        self.completed_outputs[nid] = dict(res_manifest.outputs)
                        self.node_statuses[nid] = NodeStatus.SUCCESS
                        self.node_attempts[nid] = prev_node.attempt
                        self.precompleted_nodes.add(nid)
                        continue
                    except Exception:
                        pass

            if prev_node is not None and prev_node.status == NodeStatus.WAITING_FOR_USER:
                self.node_statuses[nid] = NodeStatus.WAITING_FOR_USER
                self.node_attempts[nid] = prev_node.attempt
                node_cps = cps_by_node.get(nid, [])
                open_cp = next((c for c in node_cps if c.answer is None), None)
                target_cp = open_cp or (node_cps[-1] if node_cps else None)
                if target_cp is not None:
                    self.resuming_waiting_nodes[nid] = target_cp
                continue

            if prev_node is not None and prev_node.status in (
                NodeStatus.FAILED,
                NodeStatus.CANCELED,
                NodeStatus.BLOCKED,
                NodeStatus.RUNNING,
                NodeStatus.BUILDING_ENVIRONMENT,
            ):
                self.node_attempts[nid] = prev_node.attempt
                self.node_statuses[nid] = NodeStatus.PENDING
                await asyncio.to_thread(self.store.reset_node_for_retry, self.active_run_id, nid)
                await asyncio.to_thread(
                    self.event_log.append,
                    "node_status",
                    NodeStatusData(
                        run_id=self.active_run_id,
                        node_id=nid,
                        status=NodeStatus.PENDING,
                        cache_hit=False,
                        attempt=prev_node.attempt,
                    ),
                )
                if self.opts.on_node_status is not None:
                    self.opts.on_node_status(nid, NodeStatus.PENDING, prev_node.attempt)
            else:
                self.node_statuses[nid] = NodeStatus.PENDING
                self.node_attempts[nid] = prev_node.attempt if prev_node is not None else 0

    async def _restore_stage_gates(self) -> None:
        all_db_gates = await asyncio.to_thread(self.store.list_stage_gates, self.active_run_id)
        for gate in all_db_gates:
            sid = gate.stage_id
            if sid not in self.workflow.stages:
                continue
            gate_key = (sid, gate.kind)
            if gate.status == StageGateStatus.APPROVED:
                if gate.kind == StageGateKind.INPUT:
                    self.opened_input_gates.add(sid)
                    self.approved_input_gates.add(sid)
                else:
                    self.opened_approval_gates.add(sid)
                    self.approved_approval_gates.add(sid)
                if gate_key not in self.emitted_gate_resolutions:
                    self.emitted_gate_resolutions.add(gate_key)
                    await asyncio.to_thread(
                        self.event_log.append,
                        "stage_resolved",
                        StageResolvedData(
                            run_id=self.active_run_id,
                            stage_id=sid,
                            kind=gate.kind,
                        ),
                    )
            else:
                self.waiting_gates.add(gate_key)
                if gate.kind == StageGateKind.INPUT:
                    self.opened_input_gates.add(sid)
                else:
                    self.opened_approval_gates.add(sid)
                if not self.opts.non_interactive:
                    gtask = asyncio.create_task(self._wait_for_stage_gate(sid, gate.kind))
                    self.gate_tasks[gtask] = gate_key

    def _get_stage_missing_inputs(self, sid: str) -> list[WorkflowInputSpec]:
        missing: list[WorkflowInputSpec] = []
        for nid in self.stage_nodes.get(sid, []):
            node_spec = self.workflow.nodes[nid]
            op_entry = self.scheduler.registry.get(node_spec.op)
            if op_entry is None:
                continue
            for port in op_entry.inputs:
                if not port.required or port.default is not None:
                    continue
                if port.name in node_spec.inputs:
                    continue
                key_specific = f"{nid}.{port.name}"
                if key_specific in self.opts.run_inputs:
                    val = self.opts.run_inputs[key_specific]
                    if val is not None and (port.type == "str" or val != ""):
                        continue
                missing.append(
                    WorkflowInputSpec(
                        node_id=nid,
                        name=port.name,
                        type=port.type,
                        media=port.media,
                        required=port.required,
                        default=port.default,
                        stage_id=sid,
                    )
                )
        return missing

    def _is_node_stage_gated(self, nid: str) -> bool:
        node_stage = self.workflow.nodes[nid].stage
        target_idx = self.stage_index[node_stage]
        for earlier_sid in self.stage_order[:target_idx]:
            if (earlier_sid, StageGateKind.INPUT) in self.waiting_gates or (
                earlier_sid,
                StageGateKind.APPROVAL,
            ) in self.waiting_gates:
                return True
            if (
                self.workflow.stages[earlier_sid].require_approval
                and earlier_sid not in self.approved_approval_gates
            ):
                return True
            earlier_nodes = self.stage_nodes.get(earlier_sid, [])
            if not all(self.node_statuses.get(n) == NodeStatus.SUCCESS for n in earlier_nodes):
                return True
        if (node_stage, StageGateKind.INPUT) in self.waiting_gates:
            return True
        return bool(
            self._get_stage_missing_inputs(node_stage)
            and node_stage not in self.approved_input_gates
        )

    async def _poll_cancel_requested(self) -> None:
        while not self.cancel_event.is_set():
            if await asyncio.to_thread(self.store.is_cancel_requested, self.active_run_id):
                self.cancel_event.set()
                return
            await asyncio.sleep(self.poll_sleep)

    async def _sync_run_status(self) -> None:
        if self.opts.non_interactive or self.cancel_event.is_set():
            return
        async with self.run_status_lock:
            desired: RunStatus | None = None
            if not self.runnable_nodes and (self.waiting_nodes or self.waiting_gates):
                desired = RunStatus.WAITING_FOR_USER
            elif self.runnable_nodes and self.current_run_status == RunStatus.WAITING_FOR_USER:
                desired = RunStatus.RUNNING
            if desired is not None and desired != self.current_run_status:
                self.current_run_status = desired
                await asyncio.to_thread(
                    self.store.update_run_status,
                    self.active_run_id,
                    desired,
                )
                await asyncio.to_thread(
                    self.event_log.append,
                    "run_status",
                    RunStatusData(run_id=self.active_run_id, status=desired),
                )

    async def _emit_node_status(
        self,
        nid: str,
        status: NodeStatus,
        *,
        attempt: int = 0,
        cache_hit: bool = False,
        cache_key: str | None = None,
        exit_code: int | None = None,
        error: str | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
    ) -> None:
        self.node_statuses[nid] = status
        await asyncio.to_thread(
            self.store.update_node_status,
            self.active_run_id,
            nid,
            status,
            cache_hit=cache_hit,
            cache_key=cache_key,
            attempt=attempt,
            exit_code=exit_code,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
        )
        await asyncio.to_thread(
            self.event_log.append,
            "node_status",
            NodeStatusData(
                run_id=self.active_run_id,
                node_id=nid,
                status=status,
                cache_hit=cache_hit,
                attempt=attempt,
                exit_code=exit_code,
                error=error,
            ),
        )
        if self.opts.on_node_status is not None:
            self.opts.on_node_status(nid, status, attempt)

    async def _await_checkpoint_resolution(
        self,
        nid: str,
        cp: CheckpointManifest,
        *,
        already_passed: bool,
        attempt: int,
    ) -> tuple[bool, bool]:
        """Wait for a checkpoint answer. Returns ``(answered, mark_done_if_not_answered)``."""
        self.runnable_nodes.discard(nid)
        self.waiting_nodes.add(nid)
        await self._sync_run_status()

        answer = await self.scheduler._resolve_checkpoint_answer(
            self.active_run_id,
            nid,
            cp,
            self.opts,
            self.resolved_answers,
            already_passed=already_passed,
            cancel_event=self.cancel_event,
        )
        if answer is None:
            if self.cancel_event.is_set():
                self.waiting_nodes.discard(nid)
                await self._emit_node_status(
                    nid,
                    NodeStatus.CANCELED,
                    attempt=attempt,
                    error="canceled",
                    finished_at=time.time(),
                )
                return False, True
            return False, False

        cp_key = (nid, cp.checkpoint_id)
        if cp_key not in self.emitted_cp_resolutions:
            self.emitted_cp_resolutions.add(cp_key)
            await asyncio.to_thread(
                self.event_log.append,
                "checkpoint_resolved",
                CheckpointResolvedData(
                    run_id=self.active_run_id,
                    node_id=nid,
                    checkpoint_id=cp.checkpoint_id,
                ),
            )
        self.resolved_answers[f"{nid}.{cp.checkpoint_id}"] = answer
        self.waiting_nodes.discard(nid)
        self.runnable_nodes.add(nid)
        await self._sync_run_status()
        return True, False

    async def _try_cache_hit(self, nid: str, node_dir: Path, cache_key: str) -> bool:
        cached_result = await asyncio.to_thread(self.scheduler._lookup_cache, cache_key)
        if cached_result is None:
            return False
        hit_manifest = ResultManifest(
            status="SUCCESS",
            cache_key=cache_key,
            cache_hit=True,
            started_at=cached_result.started_at,
            finished_at=cached_result.finished_at,
            outputs=cached_result.outputs,
        )
        await asyncio.to_thread(write_result_manifest, node_dir, hit_manifest)
        self.completed_outputs[nid] = dict(cached_result.outputs)
        await self._emit_node_status(
            nid,
            NodeStatus.SUCCESS,
            cache_hit=True,
            cache_key=cache_key,
            attempt=0,
            started_at=cached_result.started_at,
            finished_at=cached_result.finished_at,
        )
        return True

    async def _run_node_attempt(self, nid: str, node_dir: Path) -> tuple[bool, bool]:
        """Run one attempt for ``nid``. Returns ``(finished, mark_done)``."""
        spec = self.workflow.nodes[nid]
        async with self.semaphore:
            if self.cancel_event.is_set():
                await self._emit_node_status(
                    nid,
                    NodeStatus.CANCELED,
                    attempt=self.node_attempts[nid],
                    error="canceled",
                    finished_at=time.time(),
                )
                return True, True
            attempt = self.node_attempts[nid] + 1
            self.node_attempts[nid] = attempt
            try:
                inputs_manifest = await asyncio.to_thread(
                    self.scheduler._build_inputs_manifest,
                    self.active_run_id,
                    nid,
                    spec,
                    self.completed_outputs,
                    self.opts,
                    self.resolved_answers,
                )
            except (
                FileNotFoundError,
                IsADirectoryError,
                NotADirectoryError,
                ValueError,
            ) as exc:
                now_ts = time.time()
                await self._emit_node_status(
                    nid,
                    NodeStatus.FAILED,
                    attempt=attempt,
                    exit_code=2,
                    error=str(exc),
                    started_at=now_ts,
                    finished_at=now_ts,
                )
                return True, True

            await asyncio.to_thread(
                atomic_write_text,
                node_dir / "inputs.json",
                inputs_manifest.to_json(),
            )
            op_entry = self.scheduler.registry.get(spec.op)
            is_cacheable = op_entry.cacheable if op_entry is not None else True
            cache_key = self.scheduler._compute_node_cache_key(nid, spec, inputs_manifest)

            if (
                not self.opts.no_cache
                and is_cacheable
                and await self._try_cache_hit(nid, node_dir, cache_key)
            ):
                return True, True

            emitted_running = False

            async def _on_attempt_status(st: NodeStatus) -> None:
                nonlocal emitted_running
                if st == NodeStatus.RUNNING:
                    if emitted_running:
                        return
                    emitted_running = True
                    await self._emit_node_status(
                        nid,
                        NodeStatus.RUNNING,
                        attempt=attempt,
                        started_at=time.time(),
                    )
                elif st == NodeStatus.BUILDING_ENVIRONMENT:
                    await self._emit_node_status(
                        nid,
                        NodeStatus.BUILDING_ENVIRONMENT,
                        attempt=attempt,
                    )

            req = ExecutionRequest(
                run_id=self.active_run_id,
                node_id=nid,
                op=spec.op,
                attempt=attempt,
                node_dir=node_dir,
                inputs=inputs_manifest,
                cancel_event=self.cancel_event,
                on_status=_on_attempt_status,
            )
            result = await self.scheduler.executor.run(req)
            if not emitted_running and result.status != NodeStatus.CANCELED:
                await _on_attempt_status(NodeStatus.RUNNING)

            if result.status == NodeStatus.SUCCESS:
                outs = result.outputs.outputs if result.outputs is not None else {}
                result_manifest = await asyncio.to_thread(
                    self.scheduler._ingest_and_write_result,
                    node_dir,
                    result,
                    outs,
                    cache_key,
                    is_cacheable=is_cacheable,
                )
                self.completed_outputs[nid] = dict(result_manifest.outputs)
                await self._emit_node_status(
                    nid,
                    NodeStatus.SUCCESS,
                    cache_key=cache_key,
                    attempt=attempt,
                    exit_code=result.exit_code,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                )
                return True, True

        # Semaphore is released while waiting for user input so other branches proceed.
        if result.status == NodeStatus.WAITING_FOR_USER and result.checkpoint is not None:
            return await self._handle_node_checkpoint(nid, attempt, result, inputs_manifest)

        await self._emit_node_status(
            nid,
            result.status,
            attempt=attempt,
            exit_code=result.exit_code,
            error=result.error,
            started_at=result.started_at,
            finished_at=result.finished_at,
        )
        return True, True

    async def _handle_node_checkpoint(
        self,
        nid: str,
        attempt: int,
        result: NodeResult,
        inputs_manifest: InputsManifest,
    ) -> tuple[bool, bool]:
        """Persist a new checkpoint, emit its event, and await resolution."""
        cp = result.checkpoint
        assert cp is not None
        await asyncio.to_thread(
            self.store.create_checkpoint,
            self.active_run_id,
            nid,
            cp.checkpoint_id,
            cp.question,
            options=cp.options,
            allow_freeform=cp.allow_freeform,
        )
        await self._emit_node_status(
            nid,
            NodeStatus.WAITING_FOR_USER,
            attempt=attempt,
            exit_code=result.exit_code,
            started_at=result.started_at,
            finished_at=result.finished_at,
        )
        await asyncio.to_thread(
            self.event_log.append,
            "node_checkpoint",
            NodeCheckpointData(
                run_id=self.active_run_id,
                node_id=nid,
                checkpoint_id=cp.checkpoint_id,
                question=cp.question,
                options=cp.options,
                allow_freeform=cp.allow_freeform,
            ),
        )
        answered, mark_done = await self._await_checkpoint_resolution(
            nid,
            cp,
            already_passed=cp.checkpoint_id in inputs_manifest.checkpoint_answers,
            attempt=attempt,
        )
        return (False, False) if answered else (True, mark_done)

    async def _execute_node(self, nid: str) -> tuple[str, bool]:
        node_dir = self.store.node_dir(self.active_run_id, nid)

        pending_cp = self.resuming_waiting_nodes.pop(nid, None)
        if pending_cp is not None:
            cp_manifest = CheckpointManifest(
                checkpoint_id=pending_cp.checkpoint_id,
                question=pending_cp.question,
                options=pending_cp.options,
                allow_freeform=pending_cp.allow_freeform,
            )
            answered, mark_done = await self._await_checkpoint_resolution(
                nid,
                cp_manifest,
                already_passed=False,
                attempt=self.node_attempts[nid],
            )
            if not answered:
                return nid, mark_done

        while True:
            if self.cancel_event.is_set():
                await self._emit_node_status(
                    nid,
                    NodeStatus.CANCELED,
                    attempt=self.node_attempts[nid],
                    error="canceled",
                    finished_at=time.time(),
                )
                return nid, True
            finished, mark_done = await self._run_node_attempt(nid, node_dir)
            if finished:
                return nid, mark_done

    async def _wait_for_stage_gate(
        self,
        stage_id: str,
        kind: StageGateKind,
    ) -> tuple[str, StageGateKind, bool]:
        title = self.workflow.stages[stage_id].title or stage_id
        if kind == StageGateKind.INPUT:
            approved = await self.scheduler._resolve_stage_inputs(
                self.active_run_id,
                stage_id,
                title,
                self._get_stage_missing_inputs(stage_id),
                self.opts,
                cancel_event=self.cancel_event,
            )
        else:
            approved = await self.scheduler._resolve_stage_approval(
                self.active_run_id,
                stage_id,
                title,
                self.opts,
                cancel_event=self.cancel_event,
            )
        if not approved:
            return stage_id, kind, False

        latest_state = await asyncio.to_thread(self.store.get_run_state, self.active_run_id)
        if latest_state is not None:
            self.opts.run_inputs.update(latest_state.run_inputs)

        gate_key = (stage_id, kind)
        if gate_key not in self.emitted_gate_resolutions:
            self.emitted_gate_resolutions.add(gate_key)
            await asyncio.to_thread(
                self.event_log.append,
                "stage_resolved",
                StageResolvedData(run_id=self.active_run_id, stage_id=stage_id, kind=kind),
            )
        return stage_id, kind, True

    async def _open_stage_gate(self, sid: str, kind: StageGateKind, title: str) -> None:
        await asyncio.to_thread(
            self.store.create_stage_gate,
            self.active_run_id,
            sid,
            kind=kind,
        )
        await asyncio.to_thread(
            self.event_log.append,
            "stage_approval",
            StageApprovalData(
                run_id=self.active_run_id,
                stage_id=sid,
                title=title,
                kind=kind,
            ),
        )
        if kind == StageGateKind.INPUT:
            self.opened_input_gates.add(sid)
        else:
            self.opened_approval_gates.add(sid)
        self.waiting_gates.add((sid, kind))
        if not self.opts.non_interactive:
            gtask = asyncio.create_task(self._wait_for_stage_gate(sid, kind))
            self.gate_tasks[gtask] = (sid, kind)

    async def _open_ready_stage_gates(self) -> bool:
        progressed = False
        for sid in self.stage_order:
            stage = self.workflow.stages[sid]
            s_idx = self.stage_index[sid]
            prior_finished = all(
                all(
                    self.node_statuses.get(n) == NodeStatus.SUCCESS
                    for n in self.stage_nodes.get(prev_sid, [])
                )
                and (
                    not self.workflow.stages[prev_sid].require_approval
                    or prev_sid in self.approved_approval_gates
                )
                for prev_sid in self.stage_order[:s_idx]
            )
            if not prior_finished:
                break

            # 1. Check if this stage requires inputs before running its nodes
            if sid not in self.approved_input_gates and self._get_stage_missing_inputs(sid):
                if sid not in self.opened_input_gates:
                    await self._open_stage_gate(sid, StageGateKind.INPUT, stage.title or sid)
                    progressed = True
                break

            # 2. Check if this stage has finished execution and requires approval
            if not stage.require_approval or sid in self.approved_approval_gates:
                continue
            if sid in self.opened_approval_gates:
                break
            nodes_in_stage = self.stage_nodes.get(sid, [])
            if not all(self.node_statuses.get(n) == NodeStatus.SUCCESS for n in nodes_in_stage):
                break

            await self._open_stage_gate(sid, StageGateKind.APPROVAL, stage.title or sid)
            progressed = True
            break
        return progressed

    async def _drain_on_cancel(self) -> bool:
        """Drain active tasks during cancellation. Returns True when all tasks have drained."""
        all_tasks: set[asyncio.Task[Any]] = set(self.running_tasks.keys()) | set(
            self.gate_tasks.keys()
        )
        if not all_tasks:
            return True
        done_cancel, _ = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
        for completed_task in done_cancel:
            if completed_task in self.running_tasks:
                self.running_tasks.pop(completed_task, None)
                finished_nid, _ = await completed_task
                self.pending_discard.append(finished_nid)
            elif completed_task in self.gate_tasks:
                self.gate_tasks.pop(completed_task, None)
                await completed_task
        return False

    async def _dispatch_ready_nodes(self) -> bool:
        """Schedule ready nodes that are not stage-gated. Returns True if immediate progress occurred."""
        progressed_immediately = False
        still_deferred: list[str] = []
        to_launch: list[str] = []
        for nid in self.deferred_ready:
            deps = self.dep_graph[nid]
            if nid in self.precompleted_nodes:
                self.sorter.done(nid)
                progressed_immediately = True
            elif any(
                self.node_statuses.get(dep)
                in (NodeStatus.FAILED, NodeStatus.CANCELED, NodeStatus.BLOCKED)
                for dep in deps
            ):
                await self._emit_node_status(nid, NodeStatus.BLOCKED, attempt=0)
                self.sorter.done(nid)
                progressed_immediately = True
            elif self._is_node_stage_gated(nid):
                still_deferred.append(nid)
            else:
                self.runnable_nodes.add(nid)
                to_launch.append(nid)
        self.deferred_ready = still_deferred

        for done_nid in self.pending_discard:
            self.runnable_nodes.discard(done_nid)
        self.pending_discard.clear()

        if to_launch and not self.cancel_event.is_set():
            await self._sync_run_status()
            for nid in to_launch:
                task = asyncio.create_task(self._execute_node(nid))
                self.running_tasks[task] = nid

        return progressed_immediately

    async def _run_main_loop(self) -> None:
        while True:
            if self.cancel_event.is_set():
                if await self._drain_on_cancel():
                    break
                continue

            if self.sorter.is_active():
                self.deferred_ready.extend(self.sorter.get_ready())

            await self._open_ready_stage_gates()

            if await self._dispatch_ready_nodes():
                continue

            all_tasks: set[asyncio.Task[Any]] = set(self.running_tasks.keys()) | set(
                self.gate_tasks.keys()
            )
            if not all_tasks:
                break

            await self._sync_run_status()

            done, _ = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
            for completed_task in done:
                if completed_task in self.running_tasks:
                    self.running_tasks.pop(completed_task, None)
                    finished_nid, mark_done = await completed_task
                    self.pending_discard.append(finished_nid)
                    if mark_done and not self.cancel_event.is_set():
                        self.sorter.done(finished_nid)
                elif completed_task in self.gate_tasks:
                    self.gate_tasks.pop(completed_task, None)
                    gate_sid, gate_kind, approved = await completed_task
                    if approved:
                        self.waiting_gates.discard((gate_sid, gate_kind))
                        if gate_kind == StageGateKind.INPUT:
                            self.approved_input_gates.add(gate_sid)
                        else:
                            self.approved_approval_gates.add(gate_sid)

    async def _finalize_run(self) -> RunState:
        if self.cancel_event.is_set():
            await asyncio.to_thread(self.store.request_cancel, self.active_run_id)
            cancel_ts = time.time()
            for nid in self.node_ids:
                if self.node_statuses.get(nid) in (
                    NodeStatus.PENDING,
                    NodeStatus.WAITING_FOR_USER,
                    NodeStatus.RUNNING,
                    NodeStatus.BUILDING_ENVIRONMENT,
                ):
                    await self._emit_node_status(
                        nid,
                        NodeStatus.CANCELED,
                        attempt=self.node_attempts[nid],
                        error="canceled",
                        finished_at=cancel_ts,
                    )

        final_status = (
            RunStatus.CANCELED
            if self.cancel_event.is_set()
            else self.scheduler._compute_final_run_status(
                self.node_statuses,
                has_waiting_gate=bool(self.waiting_gates),
            )
        )
        finished_ts = (
            time.time()
            if final_status in (RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELED)
            else None
        )
        run_error: str | None = None
        if final_status == RunStatus.FAILED:
            failed_nodes = [
                nid for nid, st in self.node_statuses.items() if st == NodeStatus.FAILED
            ]
            run_error = f"Failed node(s): {', '.join(failed_nodes)}"

        await asyncio.to_thread(
            self.store.update_run_status,
            self.active_run_id,
            final_status,
            finished_at=finished_ts,
            error=run_error,
        )
        if final_status == RunStatus.WAITING_FOR_USER:
            await asyncio.to_thread(
                self.store.release_ownership,
                self.active_run_id,
                expected_pid=os.getpid(),
            )
        if final_status != self.current_run_status or final_status in (
            RunStatus.SUCCESS,
            RunStatus.FAILED,
            RunStatus.CANCELED,
        ):
            await asyncio.to_thread(
                self.event_log.append,
                "run_status",
                RunStatusData(run_id=self.active_run_id, status=final_status, error=run_error),
            )

        final_state = await asyncio.to_thread(self.store.get_run_state, self.active_run_id)
        assert final_state is not None

        await asyncio.to_thread(
            enforce_cache_budget,
            self.store.workspace_root,
            store=self.store,
            blob_store=self.scheduler.blob_store,
        )
        return final_state


class Scheduler:
    """Executes a validated ``Workflow`` DAG against a ``RunStore`` and an ``Executor``."""

    def __init__(
        self,
        store: RunStore,
        executor: Executor,
        registry: OpRegistry | None = None,
        blob_store: BlobStore | None = None,
    ) -> None:
        self.store = store
        self.executor = executor
        self.registry: OpRegistry = (
            PackRegistry(store.workspace_root) if registry is None else registry
        )
        self.blob_store = blob_store or BlobStore.from_workspace(store.workspace_root)

    async def resume(
        self,
        run_id: str,
        *,
        options: SchedulerOptions | None = None,
    ) -> RunState:
        """Resume an existing failed, canceled, or waiting run, taking ownership."""
        await asyncio.to_thread(self.store.reconcile_dead_owners)
        resolved_id = await asyncio.to_thread(self.store.resolve_run_id, run_id)
        existing_state = await asyncio.to_thread(self.store.claim_run_for_resume, resolved_id)

        snapshot_path = self.store.run_dir(resolved_id) / "workflow.snapshot.yaml"
        if not snapshot_path.is_file():
            raise RunNotFoundError(f"Workflow snapshot missing for run {resolved_id!r}")
        wf_bytes = await asyncio.to_thread(snapshot_path.read_bytes)
        workflow = parse_workflow_yaml(
            wf_bytes,
            default_name=Path(existing_state.workflow_path).stem,
        )

        refresh_fn = getattr(self.registry, "refresh", None)
        if callable(refresh_fn):
            await asyncio.to_thread(refresh_fn)

        base_opts = options or SchedulerOptions()
        merged_inputs = dict(existing_state.run_inputs)
        merged_inputs.update(base_opts.run_inputs)
        merged_opts = SchedulerOptions(
            concurrency=base_opts.concurrency,
            run_inputs=merged_inputs,
            answers=dict(base_opts.answers),
            non_interactive=base_opts.non_interactive,
            no_cache=base_opts.no_cache,
            poll_interval=base_opts.poll_interval,
            cancel_event=base_opts.cancel_event,
            checkpoint_callback=base_opts.checkpoint_callback,
            stage_approval_callback=base_opts.stage_approval_callback,
            stage_inputs_callback=base_opts.stage_inputs_callback,
            on_node_status=base_opts.on_node_status,
        )
        return await self.run(
            workflow,
            workflow_path=existing_state.workflow_path,
            workflow_bytes=wf_bytes,
            run_id=resolved_id,
            resume=True,
            options=merged_opts,
        )

    async def run(
        self,
        workflow: Workflow,
        *,
        workflow_path: str = "workflow.yaml",
        workflow_bytes: bytes | None = None,
        layout_bytes: bytes | None = None,
        run_id: str | None = None,
        resume: bool = False,
        options: SchedulerOptions | None = None,
    ) -> RunState:
        """Schedule and run ``workflow``, writing statuses and events to ``self.store``."""
        opts = options or SchedulerOptions()
        ws_concurrency = load_workspace_config(self.store.workspace_root).concurrency
        concurrency = (
            opts.concurrency or workflow.concurrency or ws_concurrency or (os.cpu_count() or 1)
        )
        if concurrency < 1:
            concurrency = 1

        raw_wf = (
            workflow_bytes
            if workflow_bytes is not None
            else f"version: 1\nname: {workflow.name or 'workflow'}\n".encode()
        )
        node_ids = list(workflow.nodes.keys())
        existing_state: RunState | None = None

        if resume:
            if run_id is None:
                raise ValueError("run_id is required when resume=True")
            existing_state = await asyncio.to_thread(self.store.get_run_state, run_id)
            if existing_state is None:
                raise RunNotFoundError(f"No run matching {run_id!r}")
            if (
                existing_state.status != RunStatus.RUNNING
                or existing_state.owner_pid != os.getpid()
            ):
                existing_state = await asyncio.to_thread(self.store.claim_run_for_resume, run_id)
            active_run_id = run_id
        else:
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
        execution = _RunExecution(
            self,
            workflow,
            active_run_id,
            concurrency,
            opts,
        )
        return await execution.execute(resume=resume, existing_state=existing_state)

    def _build_inputs_manifest(
        self,
        run_id: str,
        node_id: str,
        spec: NodeSpec,
        completed_outputs: Mapping[str, Mapping[str, ResultValue | OutputValue]],
        opts: SchedulerOptions,
        resolved_answers: Mapping[str, str],
    ) -> InputsManifest:
        dst_node_dir = self.store.node_dir(run_id, node_id)
        state = self.store.get_run_state(run_id)
        db_checkpoints = state.checkpoints if state is not None else None
        return materialize_inputs(
            node_id=node_id,
            spec=spec,
            dst_node_dir=dst_node_dir,
            completed_outputs=completed_outputs,
            blob_store=self.blob_store,
            workspace_root=self.store.workspace_root,
            registry=self.registry,
            run_inputs=opts.run_inputs,
            answers=resolved_answers,
            db_checkpoints=db_checkpoints,
        )

    def _compute_node_cache_key(
        self,
        node_id: str,
        spec: NodeSpec,
        inputs: InputsManifest,
    ) -> str:
        op_entry = self.registry.get(spec.op)
        if op_entry is not None:
            source_file = (self.store.workspace_root / op_entry.source).resolve()
            if source_file.is_file():
                pack_dir = None
                if hasattr(self.registry, "discovered_packs"):
                    discovered = self.registry.discovered_packs
                    packs_dict = discovered() if callable(discovered) else discovered
                    if isinstance(packs_dict, dict):
                        pack_dir = packs_dict.get(op_entry.pack)
                return compute_cache_key(
                    op_entrypoint=spec.op,
                    op_source_file=source_file,
                    inputs=inputs,
                    pack_dir=pack_dir,
                )

        file_and_dir = {
            k: v.sha256 if isinstance(v, InputFileValue) else v.tree_sha256
            for k, v in inputs.inputs.items()
            if not isinstance(v, ScalarValue)
        }
        scalars = {k: v.value for k, v in inputs.inputs.items() if isinstance(v, ScalarValue)}
        return compute_cache_key_raw(
            op_entrypoint=spec.op,
            file_sha256="00" * 32,
            uv_lock_sha256="",
            inputs_hash=compute_inputs_hash(file_and_dir),
            params_hash=compute_params_hash(scalars, checkpoint_answers=inputs.checkpoint_answers),
        )

    def _lookup_cache(self, cache_key: str) -> ResultManifest | None:
        raw_json = self.store.get_cache_entry(cache_key)
        if raw_json is None:
            return None
        try:
            manifest = ResultManifest.from_json(raw_json)
        except Exception:
            return None

        # Verify all output blobs exist in CAS. A missing blob is a miss, never an error.
        for out in manifest.outputs.values():
            if isinstance(out, ResultFileValue):
                if not self.blob_store.exists(out.sha256):
                    return None
            elif isinstance(out, ResultDirectoryValue):
                for entry in out.entries:
                    if not self.blob_store.exists(entry.sha256):
                        return None
        return manifest

    def _ingest_and_write_result(
        self,
        node_dir: Path,
        result: NodeResult,
        outs: Mapping[str, OutputValue],
        cache_key: str,
        *,
        is_cacheable: bool = True,
    ) -> ResultManifest:
        result_outputs = ingest_outputs(
            outs,
            node_dir=node_dir,
            blob_store=self.blob_store,
        )
        result_manifest = ResultManifest(
            status="SUCCESS",
            cache_key=cache_key,
            cache_hit=False,
            started_at=result.started_at,
            finished_at=result.finished_at,
            outputs=result_outputs,
        )
        write_result_manifest(node_dir, result_manifest)
        if is_cacheable:
            self.store.put_cache_entry(cache_key, result_manifest.to_json())
        return result_manifest

    async def _record_answer_first_wins(
        self,
        run_id: str,
        node_id: str,
        checkpoint_id: str,
        candidate: str,
    ) -> str:
        won = await asyncio.to_thread(
            self.store.answer_checkpoint,
            run_id,
            node_id,
            checkpoint_id,
            candidate,
        )
        if won:
            return candidate
        existing = await asyncio.to_thread(
            self.store.get_checkpoint,
            run_id,
            node_id,
            checkpoint_id,
        )
        if existing is not None and existing.answer is not None:
            return existing.answer
        return candidate

    async def _resolve_checkpoint_answer(
        self,
        run_id: str,
        node_id: str,
        cp: CheckpointManifest,
        opts: SchedulerOptions,
        resolved_answers: Mapping[str, str],
        *,
        already_passed: bool = False,
        cancel_event: asyncio.Event | None = None,
    ) -> str | None:
        if cancel_event is not None and cancel_event.is_set():
            return None

        key = f"{node_id}.{cp.checkpoint_id}"
        if not already_passed and key in resolved_answers:
            return await self._record_answer_first_wins(
                run_id,
                node_id,
                cp.checkpoint_id,
                resolved_answers[key],
            )

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

        poll_sleep = max(opts.poll_interval, 0.005)

        async def _poll_db_answer() -> str:
            while True:
                await asyncio.sleep(poll_sleep)
                row = await asyncio.to_thread(
                    self.store.get_checkpoint,
                    run_id,
                    node_id,
                    cp.checkpoint_id,
                )
                if row is not None and row.answer is not None:
                    return row.answer

        poll_task: asyncio.Task[str] = asyncio.create_task(_poll_db_answer())
        cb_task: asyncio.Task[str | None] | None = None
        cancel_task: asyncio.Task[bool] | None = (
            asyncio.create_task(cancel_event.wait()) if cancel_event is not None else None
        )

        if opts.checkpoint_callback is not None:
            callback = opts.checkpoint_callback

            async def _invoke_callback() -> str | None:
                maybe_coro = callback(node_id, cp.checkpoint_id, cp)
                if isinstance(maybe_coro, Awaitable):
                    return await maybe_coro
                return maybe_coro

            cb_task = asyncio.create_task(_invoke_callback())

        wait_set: set[asyncio.Task[Any]] = {poll_task}
        if cb_task is not None:
            wait_set.add(cb_task)
        if cancel_task is not None:
            wait_set.add(cancel_task)

        try:
            done, pending = await asyncio.wait(
                wait_set,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p_task in pending:
                p_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await p_task

            if cancel_task is not None and cancel_task in done and not cancel_task.cancelled():
                return None

            if poll_task in done and not poll_task.cancelled():
                return poll_task.result()

            if cb_task is not None and cb_task in done and not cb_task.cancelled():
                cb_ans = cb_task.result()
                if cb_ans is None:
                    latest = await asyncio.to_thread(
                        self.store.get_checkpoint,
                        run_id,
                        node_id,
                        cp.checkpoint_id,
                    )
                    return latest.answer if latest is not None else None
                return await self._record_answer_first_wins(
                    run_id,
                    node_id,
                    cp.checkpoint_id,
                    cb_ans,
                )
            return None
        finally:
            for task in wait_set:
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    async def _wait_and_resolve_gate(
        self,
        run_id: str,
        stage_id: str,
        kind: StageGateKind,
        opts: SchedulerOptions,
        cancel_event: asyncio.Event | None,
        cb_coro: Callable[[], Coroutine[Any, Any, Any]] | None,
        on_cb_result: Callable[[Any], Awaitable[bool]] | None,
    ) -> bool:
        if cancel_event is not None and cancel_event.is_set():
            return False

        existing = await asyncio.to_thread(
            self.store.get_stage_gate,
            run_id,
            stage_id,
            kind=kind,
        )
        if existing is not None and existing.status == StageGateStatus.APPROVED:
            return True

        if opts.non_interactive:
            return False

        poll_sleep = max(opts.poll_interval, 0.005)

        async def _poll_db_gate() -> bool:
            while True:
                await asyncio.sleep(poll_sleep)
                row = await asyncio.to_thread(
                    self.store.get_stage_gate,
                    run_id,
                    stage_id,
                    kind=kind,
                )
                if row is not None and row.status == StageGateStatus.APPROVED:
                    return True

        poll_task: asyncio.Task[bool] = asyncio.create_task(_poll_db_gate())
        cb_task: asyncio.Task[Any] | None = (
            asyncio.create_task(cb_coro()) if cb_coro is not None else None
        )
        cancel_task: asyncio.Task[bool] | None = (
            asyncio.create_task(cancel_event.wait()) if cancel_event is not None else None
        )

        wait_set: set[asyncio.Task[Any]] = {poll_task}
        if cb_task is not None:
            wait_set.add(cb_task)
        if cancel_task is not None:
            wait_set.add(cancel_task)

        try:
            done, pending = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)
            for p_task in pending:
                p_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await p_task

            if cancel_task is not None and cancel_task in done and not cancel_task.cancelled():
                return False
            if poll_task in done and not poll_task.cancelled():
                return poll_task.result()
            if (
                cb_task is not None
                and cb_task in done
                and not cb_task.cancelled()
                and on_cb_result is not None
            ):
                return await on_cb_result(cb_task.result())
            return False
        finally:
            for task in wait_set:
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    async def _resolve_stage_inputs(
        self,
        run_id: str,
        stage_id: str,
        title: str,
        missing_inputs: list[WorkflowInputSpec],
        opts: SchedulerOptions,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> bool:
        cb_coro: Callable[[], Coroutine[Any, Any, Any]] | None = None
        on_cb_result: Callable[[Any], Awaitable[bool]] | None = None
        if opts.stage_inputs_callback is not None:
            callback = opts.stage_inputs_callback

            async def _invoke() -> dict[str, Any] | None:
                maybe_coro = callback(stage_id, title, missing_inputs)
                if isinstance(maybe_coro, Awaitable):
                    return await maybe_coro
                return maybe_coro

            async def _handle(provided: Any) -> bool:
                if provided is not None:
                    if provided:
                        await asyncio.to_thread(self.store.update_run_inputs, run_id, provided)
                    await asyncio.to_thread(
                        self.store.approve_stage_gate,
                        run_id,
                        stage_id,
                        kind=StageGateKind.INPUT,
                    )
                    return True
                latest = await asyncio.to_thread(
                    self.store.get_stage_gate,
                    run_id,
                    stage_id,
                    kind=StageGateKind.INPUT,
                )
                return latest is not None and latest.status == StageGateStatus.APPROVED

            cb_coro = _invoke
            on_cb_result = _handle

        return await self._wait_and_resolve_gate(
            run_id, stage_id, StageGateKind.INPUT, opts, cancel_event, cb_coro, on_cb_result
        )

    async def _resolve_stage_approval(
        self,
        run_id: str,
        stage_id: str,
        title: str,
        opts: SchedulerOptions,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> bool:
        cb_coro: Callable[[], Coroutine[Any, Any, Any]] | None = None
        on_cb_result: Callable[[Any], Awaitable[bool]] | None = None
        if opts.stage_approval_callback is not None:
            callback = opts.stage_approval_callback

            async def _invoke() -> bool:
                maybe_coro = callback(stage_id, title)
                if isinstance(maybe_coro, Awaitable):
                    return bool(await maybe_coro)
                return bool(maybe_coro)

            async def _handle(approved: Any) -> bool:
                if approved:
                    await asyncio.to_thread(
                        self.store.approve_stage_gate,
                        run_id,
                        stage_id,
                        kind=StageGateKind.APPROVAL,
                    )
                    return True
                latest = await asyncio.to_thread(
                    self.store.get_stage_gate,
                    run_id,
                    stage_id,
                    kind=StageGateKind.APPROVAL,
                )
                return latest is not None and latest.status == StageGateStatus.APPROVED

            cb_coro = _invoke
            on_cb_result = _handle

        return await self._wait_and_resolve_gate(
            run_id, stage_id, StageGateKind.APPROVAL, opts, cancel_event, cb_coro, on_cb_result
        )

    @staticmethod
    def _compute_final_run_status(
        node_statuses: Mapping[str, NodeStatus],
        *,
        has_waiting_gate: bool = False,
    ) -> RunStatus:
        statuses = set(node_statuses.values())
        if NodeStatus.CANCELED in statuses:
            return RunStatus.CANCELED
        if NodeStatus.FAILED in statuses:
            return RunStatus.FAILED
        if NodeStatus.WAITING_FOR_USER in statuses or has_waiting_gate:
            return RunStatus.WAITING_FOR_USER
        return RunStatus.SUCCESS
