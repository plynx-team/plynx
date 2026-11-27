"""DAG workflow scheduler using ``graphlib.TopologicalSorter`` and ``asyncio``."""

from __future__ import annotations

import asyncio
import contextlib
import graphlib
import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable, Coroutine, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from plynx_sdk.protocol import (
    AgentProvider,
    CheckpointAnswer,
    CheckpointManifest,
    CheckpointQuestion,
    GraphEditPolicy,
    GraphPatchPayload,
    InputFileValue,
    InputsManifest,
    OutputsManifest,
    OutputValue,
    ProtocolError,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ResultValue,
    ScalarValue,
    ValidatorMode,
    validate_batch_answers,
)
from pydantic import ValidationError
from ruamel.yaml import YAML

from plynx.api_models import (
    CheckpointQuestionState,
    CheckpointResolvedData,
    CheckpointResolvedEvent,
    CheckpointState,
    GraphPatchModel,
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
    is_batch_checkpoint,
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
from plynx.config import load_workspace_config, resolve_max_injected_nodes
from plynx.engine.executor import ExecutionRequest, Executor, NodeResult
from plynx.registry import OpRegistry, PackRegistry
from plynx.store.event_log import EventLog
from plynx.store.run_store import (
    PATCH_APPROVAL_OPTIONS,
    RunNotFoundError,
    RunStore,
    StoreError,
    atomic_write_text,
)
from plynx.workflow.models import (
    NodeRef,
    NodeSpec,
    StageValidatorSpec,
    Workflow,
    execution_node_ids,
    is_stage_validator_node_id,
    parse_workflow_yaml,
    stage_validator_node_id,
)
from plynx.workflow.mutation import (
    SnapshotMutationResult,
    compute_ancestors,
    prepare_and_validate_patch,
    validate_snapshot_mutation,
)

CheckpointCallback = Callable[[str, str, CheckpointManifest], Awaitable[str | None] | str | None]
StageApprovalCallback = Callable[[str, str], Awaitable[bool] | bool]
StageInputsCallback = Callable[
    [str, str, list[WorkflowInputSpec]],
    Awaitable[dict[str, Any] | None] | dict[str, Any] | None,
]
NodeStatusCallback = Callable[[str, NodeStatus, int], None]

_LOG_TAIL_MAX_LINES = 100
_PREVIEW_TEXT_MAX_BYTES = 2048
_TEXT_MEDIA_PREFIXES = ("text/", "application/json", "application/yaml")


def _encode_answer(cp: CheckpointManifest, candidate: CheckpointAnswer) -> str | None:
    """Return the stored (string / JSON) form of ``candidate``, or ``None`` if it does not fit."""
    if cp.is_batch:
        if not isinstance(candidate, dict):
            return None
        try:
            normalized = validate_batch_answers(cp.questions, candidate)
        except ProtocolError:
            return None
        return json.dumps(normalized, ensure_ascii=False)
    return candidate if isinstance(candidate, str) else None


def _read_log_tail(log_path: Path, max_lines: int = _LOG_TAIL_MAX_LINES) -> list[str]:
    if not log_path.is_file():
        return []
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    return lines[-max_lines:]


@dataclass
class SchedulerOptions:
    """Options controlling a single workflow scheduler invocation."""

    concurrency: int | None = None
    run_inputs: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, CheckpointAnswer] = field(default_factory=dict)
    non_interactive: bool = False
    no_cache: bool = False
    agent_provider: AgentProvider | str | None = None
    agent_model: str | None = None
    max_injected_nodes: int | None = None
    poll_interval: float = 0.2
    cancel_event: asyncio.Event | None = None
    checkpoint_callback: CheckpointCallback | None = None
    stage_approval_callback: StageApprovalCallback | None = None
    stage_inputs_callback: StageInputsCallback | None = None
    on_node_status: NodeStatusCallback | None = None


@dataclass
class _PendingGraphPatch:
    """Queued dynamic graph patch awaiting worker quiescence, validation, and confirmation."""

    node_id: str
    node_dir: Path
    attempt: int
    result: NodeResult
    cache_key: str
    is_cacheable: bool
    patch: GraphPatchPayload
    policy: GraphEditPolicy
    existing_checkpoint: CheckpointState | None = None


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
        self.resolved_answers: dict[str, CheckpointAnswer] = dict(opts.answers)
        self.current_run_status = RunStatus.RUNNING
        self.run_status_lock = asyncio.Lock()

        self.node_ids: list[str] = []
        self.node_statuses: dict[str, NodeStatus] = {}
        self.node_attempts: dict[str, int] = {}
        self.node_warnings: dict[str, list[str]] = {}
        self.node_cache_hits: dict[str, bool] = {}
        self.node_errors: dict[str, str | None] = {}
        self.completed_outputs: dict[str, dict[str, ResultValue | OutputValue]] = {}
        self.precompleted_nodes: set[str] = set()
        self.superseded_nodes: set[str] = set()
        self.resuming_waiting_nodes: dict[str, CheckpointState] = {}
        self.validator_handled_nodes: dict[str, set[str]] = {}

        self.stage_order: list[str] = []
        self.stage_index: dict[str, int] = {}
        self.stage_regular_nodes: dict[str, list[str]] = {}
        self.stage_nodes: dict[str, list[str]] = {}
        self.validator_specs: dict[str, StageValidatorSpec] = {}
        self.validator_stage_by_nid: dict[str, str] = {}
        self.dep_graph: dict[str, set[str]] = {}
        self.sorter: graphlib.TopologicalSorter[str] = graphlib.TopologicalSorter()

        self._rebuild_dag_topology(workflow)

        ws_cfg = load_workspace_config(scheduler.store.workspace_root)
        raw_cli_max = (
            opts.max_injected_nodes
            if opts.max_injected_nodes is not None
            else opts.run_inputs.get("__max_injected_nodes__")
        )
        parsed_cli_max = (
            int(raw_cli_max)
            if isinstance(raw_cli_max, int) and not isinstance(raw_cli_max, bool)
            else None
        )
        self.max_injected_nodes = resolve_max_injected_nodes(
            workspace_config=ws_cfg,
            workflow_max=workflow.effective_max_injected_nodes(),
            cli_max=parsed_cli_max,
        )
        self.baseline_node_ids = self._load_baseline_node_ids()

        self.semaphore = asyncio.Semaphore(concurrency)
        self.agent_semaphore = asyncio.Semaphore(max(ws_cfg.agent_concurrency, 1))
        self.running_tasks: dict[asyncio.Task[tuple[str, bool]], str] = {}
        self.gate_tasks: dict[
            asyncio.Task[tuple[str, StageGateKind, bool]],
            tuple[str, StageGateKind],
        ] = {}
        self.pending_patches: dict[str, _PendingGraphPatch] = {}
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

    def _load_baseline_node_ids(self) -> set[str]:
        base_file = self.store.run_dir(self.active_run_id) / ".workflow.baseline.yaml"
        if base_file.is_file():
            try:
                base_wf = parse_workflow_yaml(base_file.read_bytes())
                return set(base_wf.nodes.keys())
            except Exception:
                pass
        return {
            nid
            for nid, spec in self.workflow.nodes.items()
            if not (spec.meta is not None and spec.meta.injected_by)
        }

    def _rebuild_dag_topology(self, workflow: Workflow) -> None:
        self.workflow = workflow
        self.stage_order = list(workflow.stages.keys())
        self.stage_index = {sid: idx for idx, sid in enumerate(self.stage_order)}
        self.stage_regular_nodes = {sid: [] for sid in self.stage_order}
        for nid, spec in workflow.nodes.items():
            self.stage_regular_nodes.setdefault(spec.stage, []).append(nid)
            if spec.meta is not None and spec.meta.superseded_by:
                self.superseded_nodes.add(nid)

        self.validator_specs = {}
        self.validator_stage_by_nid = {}
        self.stage_nodes = {
            sid: list(self.stage_regular_nodes.get(sid, [])) for sid in self.stage_order
        }
        for sid, stage in workflow.stages.items():
            if stage.validator is not None:
                val_nid = stage_validator_node_id(sid)
                self.validator_specs[val_nid] = stage.validator
                self.validator_stage_by_nid[val_nid] = sid
                self.stage_nodes.setdefault(sid, []).append(val_nid)

        self.node_ids = execution_node_ids(workflow)
        for nid in self.node_ids:
            self.node_attempts.setdefault(nid, 0)

        self.dep_graph = {nid: set() for nid in self.node_ids}
        for nid, spec in workflow.nodes.items():
            for val in spec.inputs.values():
                if isinstance(val, NodeRef) and val.from_node in workflow.nodes:
                    self.dep_graph[nid].add(val.from_node)
            s_idx = self.stage_index[spec.stage]
            for earlier_sid in self.stage_order[:s_idx]:
                if workflow.stages[earlier_sid].validator is not None:
                    self.dep_graph[nid].add(stage_validator_node_id(earlier_sid))

        for val_nid, sid in self.validator_stage_by_nid.items():
            val_spec = self.validator_specs[val_nid]
            self.dep_graph[val_nid].update(self.stage_regular_nodes.get(sid, []))
            for val in val_spec.inputs.values():
                if isinstance(val, NodeRef) and val.from_node in workflow.nodes:
                    self.dep_graph[val_nid].add(val.from_node)
            s_idx = self.stage_index[sid]
            for earlier_sid in self.stage_order[:s_idx]:
                if workflow.stages[earlier_sid].validator is not None:
                    self.dep_graph[val_nid].add(stage_validator_node_id(earlier_sid))

        self.sorter = graphlib.TopologicalSorter(self.dep_graph)
        self.sorter.prepare()

    def _spec_for_node(self, nid: str) -> NodeSpec:
        if nid in self.workflow.nodes:
            return self.workflow.nodes[nid]
        val_spec = self.validator_specs[nid]
        sid = self.validator_stage_by_nid[nid]
        return NodeSpec(
            op=val_spec.op,
            title=f"Stage Validator ({sid})",
            stage=sid,
            allow_graph_edits=val_spec.allow_graph_edits,
            inputs=dict(val_spec.inputs),
        )

    def _effective_graph_edit_policy(self, nid: str, spec: NodeSpec) -> GraphEditPolicy:
        if nid in self.validator_specs:
            return self.validator_specs[nid].allow_graph_edits
        if spec.allow_graph_edits is not None:
            return spec.allow_graph_edits
        op_entry = self.scheduler.registry.get(spec.op)
        if op_entry is not None and op_entry.allow_graph_edits is not None:
            return op_entry.allow_graph_edits
        return GraphEditPolicy.FORBIDDEN

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
            if nid in self.superseded_nodes:
                if prev_node is not None:
                    self.node_statuses[nid] = prev_node.status
                    self.node_attempts[nid] = prev_node.attempt
                    self.node_errors[nid] = prev_node.error
                else:
                    self.node_statuses[nid] = NodeStatus.FAILED
                self.precompleted_nodes.add(nid)
                continue

            if prev_node is not None and prev_node.status == NodeStatus.SUCCESS:
                res_path = self.store.node_dir(self.active_run_id, nid) / "result.json"
                if res_path.is_file():
                    try:
                        raw_res = await asyncio.to_thread(res_path.read_bytes)
                        res_manifest = ResultManifest.from_json(raw_res)
                        self.completed_outputs[nid] = dict(res_manifest.outputs)
                        self.node_statuses[nid] = NodeStatus.SUCCESS
                        self.node_attempts[nid] = prev_node.attempt
                        self.node_cache_hits[nid] = prev_node.cache_hit
                        self.node_warnings[nid] = list(res_manifest.warnings or prev_node.warnings)
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
                # Keep failed stage nodes in FAILED state if their stage validator is WAITING_FOR_USER
                # on a repair patch confirmation!
                node_stage = self._spec_for_node(nid).stage
                val_nid = (
                    stage_validator_node_id(node_stage)
                    if self.workflow.stages[node_stage].validator is not None
                    else None
                )
                val_prev = existing_state.nodes.get(val_nid) if val_nid is not None else None
                if (
                    prev_node.status in (NodeStatus.FAILED, NodeStatus.BLOCKED)
                    and val_nid is not None
                    and nid != val_nid
                    and val_prev is not None
                    and val_prev.status == NodeStatus.WAITING_FOR_USER
                ):
                    self.node_statuses[nid] = prev_node.status
                    self.node_attempts[nid] = prev_node.attempt
                    self.node_errors[nid] = prev_node.error
                    self.precompleted_nodes.add(nid)
                    continue

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

    def _active_stage_nodes(self, sid: str) -> list[str]:
        return [n for n in self.stage_nodes.get(sid, []) if n not in self.superseded_nodes]

    def _get_stage_missing_inputs(self, sid: str) -> list[WorkflowInputSpec]:
        missing: list[WorkflowInputSpec] = []
        for nid in self._active_stage_nodes(sid):
            node_spec = self._spec_for_node(nid)
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

    def _has_unrepaired_earlier_stage_failure(self, nid: str) -> bool:
        node_stage = self._spec_for_node(nid).stage
        target_idx = self.stage_index[node_stage]
        for earlier_sid in self.stage_order[:target_idx]:
            if self.workflow.stages[earlier_sid].validator is None:
                continue
            for earlier_nid in self._active_stage_nodes(earlier_sid):
                if self.node_statuses.get(earlier_nid) in (
                    NodeStatus.FAILED,
                    NodeStatus.CANCELED,
                    NodeStatus.BLOCKED,
                ):
                    return True
        return False

    def _is_node_stage_gated(self, nid: str) -> bool:
        node_stage = self._spec_for_node(nid).stage
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
            earlier_nodes = self._active_stage_nodes(earlier_sid)
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
        warnings: Sequence[str] | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
    ) -> None:
        self.node_statuses[nid] = status
        self.node_cache_hits[nid] = cache_hit
        self.node_errors[nid] = error
        warnings_list = list(warnings) if warnings is not None else None
        if warnings_list is not None:
            self.node_warnings[nid] = list(warnings_list)
        elif status in (NodeStatus.PENDING, NodeStatus.RUNNING):
            self.node_warnings[nid] = []

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
            warnings=warnings_list,
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
                warnings=warnings_list or [],
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
        self.resolved_answers[f"{nid}.{cp.checkpoint_id}"] = (
            json.loads(answer) if cp.is_batch else answer
        )
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
            warnings=list(cached_result.warnings),
        )
        await asyncio.to_thread(write_result_manifest, node_dir, hit_manifest)
        self.completed_outputs[nid] = dict(cached_result.outputs)
        await self._emit_node_status(
            nid,
            NodeStatus.SUCCESS,
            cache_hit=True,
            cache_key=cache_key,
            attempt=0,
            warnings=hit_manifest.warnings,
            started_at=cached_result.started_at,
            finished_at=cached_result.finished_at,
        )
        return True

    def _evaluate_stage_validator_skip(self, val_nid: str) -> tuple[bool, bool, str]:
        """Return ``(should_skip, skip_as_cache_hit, summary_message)``."""
        sid = self.validator_stage_by_nid[val_nid]
        val_spec = self.validator_specs[val_nid]
        handled = self.validator_handled_nodes.get(sid, set())
        active_regular = [
            n for n in self.stage_regular_nodes.get(sid, []) if n not in self.superseded_nodes
        ]
        unhandled = [n for n in active_regular if n not in handled]

        # Rule 1: 100% CAS cache hit across all stage nodes with zero warnings -> skip as cache hit
        if (
            active_regular
            and all(self.node_statuses.get(n) == NodeStatus.SUCCESS for n in active_regular)
            and all(self.node_cache_hits.get(n, False) for n in active_regular)
            and all(not self.node_warnings.get(n) for n in active_regular)
        ):
            return True, True, "Skipped: all stage nodes hit cache with no warnings."

        target_nodes = unhandled if handled else active_regular
        any_failed = any(self.node_statuses.get(n) == NodeStatus.FAILED for n in target_nodes)
        any_warn = any(bool(self.node_warnings.get(n)) for n in target_nodes)

        if val_spec.mode == ValidatorMode.ON_ANOMALY:
            if not any_failed and not any_warn:
                return True, False, "Passed: no stage anomalies or warnings."
            return False, False, ""

        if val_spec.mode == ValidatorMode.ON_FAILURE:
            if not any_failed:
                return True, False, "Passed: no stage failures."
            return False, False, ""

        # ValidatorMode.ALWAYS: skip only if re-checking an already-validated stage with no new nodes
        if handled and not unhandled:
            return True, False, "Passed: stage already validated."
        return False, False, ""

    def _write_stage_context_sync(self, val_nid: str, node_dir: Path) -> None:
        sid = self.validator_stage_by_nid[val_nid]
        val_spec = self.validator_specs[val_nid]
        logs_dir = self.store.run_dir(self.active_run_id) / "logs"
        snap_path = self.store.run_dir(self.active_run_id) / "workflow.snapshot.yaml"
        snap_text = (
            snap_path.read_text(encoding="utf-8", errors="replace") if snap_path.is_file() else ""
        )

        nodes_ctx: dict[str, Any] = {}
        for s_nid in self.stage_regular_nodes.get(sid, []):
            if s_nid in self.superseded_nodes:
                continue
            s_dir = self.store.node_dir(self.active_run_id, s_nid)
            outputs_info: dict[str, Any] = {}
            res_file = s_dir / "result.json"
            if res_file.is_file():
                try:
                    res_man = ResultManifest.from_json(res_file.read_bytes())
                    for p_name, out_val in res_man.outputs.items():
                        entry_dict = out_val.to_dict()
                        if isinstance(out_val, ResultFileValue):
                            media = out_val.media or ""
                            if any(media.startswith(pref) for pref in _TEXT_MEDIA_PREFIXES):
                                blob_p = self.scheduler.blob_store.blob_path(out_val.sha256)
                                if blob_p.is_file():
                                    try:
                                        with blob_p.open("rb") as fh:
                                            raw_preview = fh.read(_PREVIEW_TEXT_MAX_BYTES)
                                        entry_dict["preview"] = raw_preview.decode(
                                            "utf-8", errors="replace"
                                        )
                                    except OSError:
                                        pass
                        outputs_info[p_name] = entry_dict
                except Exception:
                    pass

            nodes_ctx[s_nid] = {
                "op": self.workflow.nodes[s_nid].op,
                "status": self.node_statuses.get(s_nid, NodeStatus.PENDING).value,
                "cache_hit": self.node_cache_hits.get(s_nid, False),
                "attempt": self.node_attempts.get(s_nid, 0),
                "error": self.node_errors.get(s_nid),
                "warnings": list(self.node_warnings.get(s_nid, [])),
                "outputs": outputs_info,
                "stdout_tail": _read_log_tail(logs_dir / f"{s_nid}.stdout.log"),
                "stderr_tail": _read_log_tail(logs_dir / f"{s_nid}.stderr.log"),
            }

        ops_list = [
            op.model_dump(mode="json") for op in self.scheduler.registry.list_ops() if op.valid
        ]
        ctx_payload = {
            "schema": 1,
            "run_id": self.active_run_id,
            "stage_id": sid,
            "stage_title": self.workflow.stages[sid].title or sid,
            "mode": val_spec.mode.value,
            "allow_graph_edits": val_spec.allow_graph_edits.value,
            "max_injected_nodes": self.max_injected_nodes,
            "nodes": nodes_ctx,
            "workflow_snapshot_yaml": snap_text,
            "registered_ops": ops_list,
        }
        atomic_write_text(
            node_dir / "stage_context.json",
            json.dumps(ctx_payload, indent=2, ensure_ascii=False) + "\n",
        )

    def _append_gate_log_sync(self, nid: str, message: str) -> None:
        logs_dir = self.store.run_dir(self.active_run_id) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"{nid}.stdout.log"
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"[gate] {message}\n")

    async def _run_node_attempt(self, nid: str, node_dir: Path) -> tuple[bool, bool]:
        """Run one attempt for ``nid``. Returns ``(finished, mark_done)``."""
        is_validator = nid in self.validator_specs
        if is_validator:
            should_skip, skip_cache_hit, skip_msg = self._evaluate_stage_validator_skip(nid)
            if should_skip:
                sid = self.validator_stage_by_nid[nid]
                val_mode = self.validator_specs[nid].mode.value
                await asyncio.to_thread(
                    self._append_gate_log_sync,
                    nid,
                    f"Stage '{sid}' validator skipped (mode={val_mode}): {skip_msg}",
                )
                now_ts = time.time()
                skip_manifest = ResultManifest(
                    status="SUCCESS",
                    cache_key="stage-validator-skipped",
                    cache_hit=skip_cache_hit,
                    started_at=now_ts,
                    finished_at=now_ts,
                    outputs={"summary": ScalarValue(value=skip_msg)},
                    warnings=[],
                )
                await asyncio.to_thread(write_result_manifest, node_dir, skip_manifest)
                self.completed_outputs[nid] = dict(skip_manifest.outputs)
                await self._emit_node_status(
                    nid,
                    NodeStatus.SUCCESS,
                    cache_hit=skip_cache_hit,
                    cache_key=skip_manifest.cache_key,
                    attempt=self.node_attempts[nid],
                    started_at=now_ts,
                    finished_at=now_ts,
                )
                return True, True

        spec = self._spec_for_node(nid)
        op_entry = self.scheduler.registry.get(spec.op)
        is_agent_op = bool(
            is_validator or (op_entry is not None and op_entry.agent_role is not None)
        )
        agent_guard: contextlib.AbstractAsyncContextManager[Any] = (
            self.agent_semaphore if is_agent_op else contextlib.nullcontext()
        )
        async with self.semaphore, agent_guard:
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

            if is_validator:
                sid = self.validator_stage_by_nid[nid]
                vspec = self.validator_specs[nid]
                await asyncio.to_thread(
                    self._append_gate_log_sync,
                    nid,
                    f"Stage '{sid}' validator triggered (mode={vspec.mode.value}, "
                    f"allow_graph_edits={vspec.allow_graph_edits.value}, attempt={attempt})",
                )
                await asyncio.to_thread(self._write_stage_context_sync, nid, node_dir)

            try:
                inputs_manifest = await asyncio.to_thread(
                    self.scheduler._build_inputs_manifest,
                    self.active_run_id,
                    nid,
                    spec,
                    self.completed_outputs,
                    self.opts,
                    self.resolved_answers,
                    self.workflow,
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
            is_cacheable = (
                False if is_validator else (op_entry.cacheable if op_entry is not None else True)
            )
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
                patch_path = node_dir / "graph_patch.json"
                if patch_path.is_file():
                    effective_policy = self._effective_graph_edit_policy(nid, spec)
                    if effective_policy == GraphEditPolicy.FORBIDDEN:
                        with contextlib.suppress(OSError):
                            await asyncio.to_thread(patch_path.unlink)
                        await self._emit_node_status(
                            nid,
                            NodeStatus.FAILED,
                            attempt=attempt,
                            exit_code=2,
                            error=(
                                f"Node '{nid}' proposed a graph_patch while "
                                "allow_graph_edits is 'forbidden'"
                            ),
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                        )
                        return True, True
                    try:
                        raw_patch_bytes = await asyncio.to_thread(patch_path.read_bytes)
                        parsed_patch = GraphPatchPayload.from_json(raw_patch_bytes)
                    except (ProtocolError, OSError) as exc:
                        await self._emit_node_status(
                            nid,
                            NodeStatus.FAILED,
                            attempt=attempt,
                            exit_code=2,
                            error=f"Invalid graph_patch.json: {exc}",
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                        )
                        return True, True

                    self.pending_patches[nid] = _PendingGraphPatch(
                        node_id=nid,
                        node_dir=node_dir,
                        attempt=attempt,
                        result=result,
                        cache_key=cache_key,
                        is_cacheable=False,
                        patch=parsed_patch,
                        policy=effective_policy,
                    )
                    return True, False

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
                    warnings=result_manifest.warnings,
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
        question_states = [CheckpointQuestionState(**asdict(q)) for q in cp.questions]
        await asyncio.to_thread(
            self.store.create_checkpoint,
            self.active_run_id,
            nid,
            cp.checkpoint_id,
            cp.display_question(),
            options=cp.options,
            allow_freeform=cp.allow_freeform,
            questions=question_states,
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
                question=cp.display_question(),
                options=cp.options,
                allow_freeform=cp.allow_freeform,
                questions=question_states,
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
            patch_path = node_dir / "graph_patch.json"
            outputs_path = node_dir / "outputs.json"
            if (
                pending_cp.options == PATCH_APPROVAL_OPTIONS
                and patch_path.is_file()
                and outputs_path.is_file()
            ):
                try:
                    raw_patch = await asyncio.to_thread(patch_path.read_bytes)
                    raw_outs = await asyncio.to_thread(outputs_path.read_bytes)
                    parsed_patch = GraphPatchPayload.from_json(raw_patch)
                    outs_manifest = OutputsManifest.from_json(raw_outs)
                    spec = self._spec_for_node(nid)
                    self.pending_patches[nid] = _PendingGraphPatch(
                        node_id=nid,
                        node_dir=node_dir,
                        attempt=self.node_attempts[nid] or 1,
                        result=NodeResult(
                            status=NodeStatus.SUCCESS,
                            exit_code=0,
                            started_at=outs_manifest.started_at,
                            finished_at=outs_manifest.finished_at,
                            outputs=outs_manifest,
                        ),
                        cache_key="graph-patch",
                        is_cacheable=False,
                        patch=parsed_patch,
                        policy=self._effective_graph_edit_policy(nid, spec),
                        existing_checkpoint=pending_cp,
                    )
                    return nid, False
                except Exception:
                    pass

            is_batch = is_batch_checkpoint(pending_cp.questions)
            cp_manifest = CheckpointManifest(
                checkpoint_id=pending_cp.checkpoint_id,
                question="" if is_batch else pending_cp.question,
                options=None if is_batch else pending_cp.options,
                allow_freeform=pending_cp.allow_freeform,
                questions=[CheckpointQuestion(**q.model_dump()) for q in pending_cp.questions],
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

    async def _next_patch_checkpoint_id(self, nid: str) -> str:
        state = await asyncio.to_thread(self.store.get_run_state, self.active_run_id)
        if state is None:
            return "cp_0"
        existing = [c for c in state.checkpoints if c.node_id == nid]
        return f"cp_{len(existing)}"

    async def _archive_patch_file(self, node_dir: Path, suffix: str) -> None:
        src = node_dir / "graph_patch.json"
        dst = node_dir / f"graph_patch.{suffix}.json"
        if src.is_file():
            await asyncio.to_thread(os.replace, src, dst)

    async def _process_pending_patches(self) -> bool:
        """Quiesce active workers, validate proposed patches, confirm if required, and reload DAG."""
        if not self.pending_patches:
            return False

        # Step 1: Quiesce all running child subprocesses before touching workflow/TopologicalSorter
        while self.running_tasks:
            done_running, _ = await asyncio.wait(
                self.running_tasks.keys(),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for completed_task in done_running:
                self.running_tasks.pop(completed_task, None)
                finished_nid, mark_done = await completed_task
                self.pending_discard.append(finished_nid)
                if mark_done and not self.cancel_event.is_set():
                    self.sorter.done(finished_nid)
            if self.cancel_event.is_set():
                return False

        patch_nid = next(iter(self.pending_patches.keys()))
        pending = self.pending_patches.pop(patch_nid)
        for done_nid in self.pending_discard:
            self.runnable_nodes.discard(done_nid)
        self.pending_discard.clear()

        snap_path = self.store.run_dir(self.active_run_id) / "workflow.snapshot.yaml"
        raw_yaml_bytes = await asyncio.to_thread(snap_path.read_bytes)
        default_stage = self._spec_for_node(patch_nid).stage

        # Step 2: Validate the proposed snapshot mutation against all 4 guardrails
        mutation_res, candidate_bytes, candidate_wf = await asyncio.to_thread(
            prepare_and_validate_patch,
            raw_yaml_bytes=raw_yaml_bytes,
            old_snapshot=self.workflow,
            patch=pending.patch,
            injected_by=patch_nid,
            default_stage=default_stage,
            registry=self.scheduler.registry,
            node_statuses=self.node_statuses,
            max_injected_nodes=self.max_injected_nodes,
            baseline_node_ids=self.baseline_node_ids,
            run_inputs=self.opts.run_inputs,
        )

        if not mutation_res.valid or candidate_bytes is None or candidate_wf is None:
            await self._archive_patch_file(pending.node_dir, "rejected")
            err_msg = "; ".join(
                issue.message for issue in mutation_res.issues if issue.severity == "error"
            )
            await self._emit_node_status(
                patch_nid,
                NodeStatus.FAILED,
                attempt=pending.attempt,
                exit_code=1,
                error=f"Invalid graph patch: {err_msg}",
                started_at=pending.result.started_at,
                finished_at=time.time(),
            )
            self.sorter.done(patch_nid)
            return True

        # Step 3: Human confirmation gate when allow_graph_edits == GraphEditPolicy.CONFIRM
        if pending.policy == GraphEditPolicy.CONFIRM:
            if pending.existing_checkpoint is not None:
                cp_id = pending.existing_checkpoint.checkpoint_id
                cp_manifest = CheckpointManifest(
                    checkpoint_id=cp_id,
                    question=pending.existing_checkpoint.question,
                    options=list(PATCH_APPROVAL_OPTIONS),
                    allow_freeform=False,
                )
            else:
                cp_id = await self._next_patch_checkpoint_id(patch_nid)
                add_summary = (
                    ", ".join(
                        f"{nid} ({spec.get('op', '')})"
                        for nid, spec in pending.patch.add_nodes.items()
                    )
                    or "none"
                )
                rewire_summary = (
                    ", ".join(
                        f"{nid}.{port}"
                        for nid, ports in pending.patch.rewire_inputs.items()
                        for port in ports
                    )
                    or "none"
                )
                q_text = (
                    f"Proposed graph patch: {pending.patch.reason} "
                    f"[add: {add_summary}; rewire: {rewire_summary}]"
                )
                cp_manifest = CheckpointManifest(
                    checkpoint_id=cp_id,
                    question=q_text,
                    options=list(PATCH_APPROVAL_OPTIONS),
                    allow_freeform=False,
                )
                question_states = [
                    CheckpointQuestionState(**asdict(q)) for q in cp_manifest.questions
                ]
                await asyncio.to_thread(
                    atomic_write_text,
                    pending.node_dir / "checkpoint.json",
                    cp_manifest.to_json(),
                )
                await asyncio.to_thread(
                    self.store.create_checkpoint,
                    self.active_run_id,
                    patch_nid,
                    cp_id,
                    cp_manifest.display_question(),
                    options=cp_manifest.options,
                    allow_freeform=False,
                    questions=question_states,
                )
                await asyncio.to_thread(
                    self._append_gate_log_sync,
                    patch_nid,
                    f"Proposed graph patch validated; awaiting user confirmation: {pending.patch.reason}",
                )
                await self._emit_node_status(
                    patch_nid,
                    NodeStatus.WAITING_FOR_USER,
                    attempt=pending.attempt,
                    exit_code=10,
                    started_at=pending.result.started_at,
                    finished_at=pending.result.finished_at,
                )
                await asyncio.to_thread(
                    self.event_log.append,
                    "node_checkpoint",
                    NodeCheckpointData(
                        run_id=self.active_run_id,
                        node_id=patch_nid,
                        checkpoint_id=cp_id,
                        question=cp_manifest.display_question(),
                        options=cp_manifest.options,
                        allow_freeform=False,
                        questions=question_states,
                        graph_patch=GraphPatchModel(
                            reason=pending.patch.reason,
                            add_nodes=dict(pending.patch.add_nodes),
                            rewire_inputs=dict(pending.patch.rewire_inputs),
                        ),
                    ),
                )

            answered, mark_done = await self._await_checkpoint_resolution(
                patch_nid,
                cp_manifest,
                already_passed=False,
                attempt=pending.attempt,
            )
            if not answered:
                self.runnable_nodes.discard(patch_nid)
                if mark_done:
                    self.sorter.done(patch_nid)
                return False

            chosen = self.resolved_answers.get(f"{patch_nid}.{cp_id}")
            if chosen == "Reject":
                await asyncio.to_thread(
                    self._append_gate_log_sync,
                    patch_nid,
                    "Graph patch rejected by user.",
                )
                await self._archive_patch_file(pending.node_dir, "rejected")
                outs = pending.result.outputs.outputs if pending.result.outputs else {}
                res_manifest = await asyncio.to_thread(
                    self.scheduler._ingest_and_write_result,
                    pending.node_dir,
                    pending.result,
                    outs,
                    pending.cache_key,
                    is_cacheable=False,
                )
                reject_warnings = [*res_manifest.warnings, "Graph patch rejected by user."]
                self.completed_outputs[patch_nid] = dict(res_manifest.outputs)
                self.runnable_nodes.discard(patch_nid)

                val_stage = self.validator_stage_by_nid.get(patch_nid)
                stage_has_unrepaired_failure = bool(
                    val_stage is not None
                    and any(
                        n not in self.superseded_nodes
                        and self.node_statuses.get(n) in (NodeStatus.FAILED, NodeStatus.BLOCKED)
                        for n in self.stage_regular_nodes.get(val_stage, [])
                    )
                )
                if stage_has_unrepaired_failure:
                    await self._emit_node_status(
                        patch_nid,
                        NodeStatus.FAILED,
                        attempt=pending.attempt,
                        exit_code=1,
                        error="Graph patch rejected while stage had failed node(s).",
                        warnings=reject_warnings,
                        started_at=pending.result.started_at,
                        finished_at=time.time(),
                    )
                else:
                    await self._emit_node_status(
                        patch_nid,
                        NodeStatus.SUCCESS,
                        cache_key=pending.cache_key,
                        attempt=pending.attempt,
                        exit_code=0,
                        warnings=reject_warnings,
                        started_at=pending.result.started_at,
                        finished_at=time.time(),
                    )
                self.sorter.done(patch_nid)
                return True

        # Step 4: Apply accepted patch to workflow.snapshot.yaml and dynamically reload the DAG
        await asyncio.to_thread(
            self._append_gate_log_sync,
            patch_nid,
            f"Applying graph patch (added={list(pending.patch.add_nodes.keys())}, "
            f"rewired={list(pending.patch.rewire_inputs.keys())}) and reloading DAG.",
        )
        await self._apply_patch_and_reload(
            patch_nid=patch_nid,
            pending=pending,
            mutation_res=mutation_res,
            candidate_bytes=candidate_bytes,
            candidate_wf=candidate_wf,
        )
        return True

    async def _apply_patch_and_reload(
        self,
        *,
        patch_nid: str,
        pending: _PendingGraphPatch,
        mutation_res: SnapshotMutationResult,
        candidate_bytes: bytes,
        candidate_wf: Workflow,
    ) -> None:
        await self._archive_patch_file(pending.node_dir, "applied")
        outs = pending.result.outputs.outputs if pending.result.outputs else {}
        res_manifest = await asyncio.to_thread(
            self.scheduler._ingest_and_write_result,
            pending.node_dir,
            pending.result,
            outs,
            pending.cache_key,
            is_cacheable=False,
        )
        self.completed_outputs[patch_nid] = dict(res_manifest.outputs)
        self.runnable_nodes.discard(patch_nid)
        await self._emit_node_status(
            patch_nid,
            NodeStatus.SUCCESS,
            cache_key=pending.cache_key,
            attempt=pending.attempt,
            exit_code=0,
            warnings=res_manifest.warnings,
            started_at=pending.result.started_at,
            finished_at=time.time(),
        )

        if patch_nid in self.validator_stage_by_nid:
            val_stage = self.validator_stage_by_nid[patch_nid]
            succeeded_in_stage = {
                n
                for n in self.stage_regular_nodes.get(val_stage, [])
                if self.node_statuses.get(n) == NodeStatus.SUCCESS
            }
            self.validator_handled_nodes.setdefault(val_stage, set()).update(succeeded_in_stage)

        await asyncio.to_thread(
            self.store.update_workflow_snapshot,
            self.active_run_id,
            candidate_bytes,
        )
        all_exec_ids = execution_node_ids(candidate_wf)
        await asyncio.to_thread(self.store.add_node_runs, self.active_run_id, all_exec_ids)

        for sup_nid in mutation_res.superseded_failed_node_ids:
            self.superseded_nodes.add(sup_nid)

        for added_nid in mutation_res.added_node_ids:
            self.node_attempts[added_nid] = 0
            await self._emit_node_status(added_nid, NodeStatus.PENDING, attempt=0)

        for rw_nid in mutation_res.rewired_node_ids:
            if self.node_statuses.get(rw_nid) in (
                NodeStatus.FAILED,
                NodeStatus.BLOCKED,
                NodeStatus.CANCELED,
            ):
                await asyncio.to_thread(self.store.reset_node_for_retry, self.active_run_id, rw_nid)
                await self._emit_node_status(
                    rw_nid,
                    NodeStatus.PENDING,
                    attempt=self.node_attempts.get(rw_nid, 0),
                )

        self._rebuild_dag_topology(candidate_wf)
        ancestors_map = compute_ancestors(candidate_wf)

        # Unblock any previously BLOCKED nodes whose upstream failure was repaired or superseded
        for nid in self.node_ids:
            if nid in self.superseded_nodes or self.node_statuses.get(nid) != NodeStatus.BLOCKED:
                continue
            upstream_ids = ancestors_map.get(nid, set())
            has_active_failure = any(
                u not in self.superseded_nodes
                and self.node_statuses.get(u) in (NodeStatus.FAILED, NodeStatus.CANCELED)
                for u in upstream_ids
            )
            if not has_active_failure:
                await asyncio.to_thread(self.store.reset_node_for_retry, self.active_run_id, nid)
                await self._emit_node_status(
                    nid,
                    NodeStatus.PENDING,
                    attempt=self.node_attempts.get(nid, 0),
                )

        # If a stage gained new or retried PENDING regular nodes, reset its stage validator to PENDING
        # so it sequences after those nodes (and skips in 0ms if no new anomalies occur).
        for val_nid, sid in self.validator_stage_by_nid.items():
            has_pending_in_stage = any(
                n not in self.superseded_nodes and self.node_statuses.get(n) == NodeStatus.PENDING
                for n in self.stage_regular_nodes.get(sid, [])
            )
            if has_pending_in_stage and self.node_statuses.get(val_nid) == NodeStatus.SUCCESS:
                await asyncio.to_thread(
                    self.store.reset_node_for_retry, self.active_run_id, val_nid
                )
                await self._emit_node_status(
                    val_nid,
                    NodeStatus.PENDING,
                    attempt=self.node_attempts.get(val_nid, 0),
                )

        for nid in self.node_ids:
            if nid not in self.node_statuses:
                self.node_attempts[nid] = 0
                await self._emit_node_status(nid, NodeStatus.PENDING, attempt=0)

        self.precompleted_nodes = {
            nid
            for nid in self.node_ids
            if self.node_statuses.get(nid) == NodeStatus.SUCCESS or nid in self.superseded_nodes
        }
        self.deferred_ready.clear()
        self.runnable_nodes.clear()
        self.pending_discard.clear()

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
                    for n in self._active_stage_nodes(prev_sid)
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
            nodes_in_stage = self._active_stage_nodes(sid)
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

    def _should_block_ready_node(self, nid: str) -> bool:
        deps = self.dep_graph[nid]
        if any(self.node_statuses.get(dep) == NodeStatus.CANCELED for dep in deps):
            return True

        if nid in self.validator_specs:
            # Stage validator intercepts failures in its own stage (ON_ANOMALY / ON_FAILURE / ALWAYS),
            # blocking only if an *earlier* stage failed or a direct cross-stage NodeRef failed.
            sid = self.validator_stage_by_nid[nid]
            own_stage_nodes = set(self.stage_regular_nodes.get(sid, []))
            val_input_refs = {
                val.from_node
                for val in self.validator_specs[nid].inputs.values()
                if isinstance(val, NodeRef)
            }
            for dep in deps:
                if dep in self.superseded_nodes:
                    continue
                dep_st = self.node_statuses.get(dep)
                if dep_st not in (NodeStatus.FAILED, NodeStatus.BLOCKED):
                    continue
                if dep not in own_stage_nodes or dep in val_input_refs:
                    return True
            return self._has_unrepaired_earlier_stage_failure(nid)

        if any(
            dep not in self.superseded_nodes
            and self.node_statuses.get(dep)
            in (NodeStatus.FAILED, NodeStatus.CANCELED, NodeStatus.BLOCKED)
            for dep in deps
        ):
            return True
        return self._has_unrepaired_earlier_stage_failure(nid)

    async def _dispatch_ready_nodes(self) -> bool:
        """Schedule ready nodes that are not stage-gated. Returns True if immediate progress occurred."""
        if self.pending_patches:
            return False

        progressed_immediately = False
        still_deferred: list[str] = []
        to_launch: list[str] = []
        for nid in self.deferred_ready:
            if nid in self.precompleted_nodes:
                self.sorter.done(nid)
                progressed_immediately = True
            elif self._should_block_ready_node(nid):
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

            if self.pending_patches:
                if await self._process_pending_patches():
                    continue
                if not self.running_tasks and not self.gate_tasks:
                    break

            if not self.pending_patches and self.sorter.is_active():
                self.deferred_ready.extend(self.sorter.get_ready())

            if not self.pending_patches:
                await self._open_ready_stage_gates()
                if await self._dispatch_ready_nodes():
                    continue

            all_tasks: set[asyncio.Task[Any]] = set(self.running_tasks.keys()) | set(
                self.gate_tasks.keys()
            )
            if not all_tasks:
                if self.pending_patches:
                    continue
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
                if nid in self.superseded_nodes:
                    continue
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

        stages_awaiting_validator = {
            sid
            for val_nid, sid in self.validator_stage_by_nid.items()
            if self.node_statuses.get(val_nid) == NodeStatus.WAITING_FOR_USER
        }
        active_statuses = {
            nid: st
            for nid, st in self.node_statuses.items()
            if nid not in self.superseded_nodes
            and not (
                st in (NodeStatus.FAILED, NodeStatus.BLOCKED)
                and nid not in self.validator_specs
                and self._spec_for_node(nid).stage in stages_awaiting_validator
            )
        }
        final_status = (
            RunStatus.CANCELED
            if self.cancel_event.is_set()
            else self.scheduler._compute_final_run_status(
                active_statuses,
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
            failed_nodes = [nid for nid, st in active_statuses.items() if st == NodeStatus.FAILED]
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

    async def validate_and_prepare_resume_snapshot(
        self,
        run_id: str,
        existing_state: RunState,
        *,
        max_injected_nodes: int | None = None,
    ) -> tuple[Workflow, bytes]:
        """Validate outer-agent edits to ``workflow.snapshot.yaml`` (if any) before resuming."""
        rdir = self.store.run_dir(run_id)
        snapshot_path = rdir / "workflow.snapshot.yaml"
        if not snapshot_path.is_file():
            raise RunNotFoundError(f"Workflow snapshot missing for run {run_id!r}")

        wf_bytes = await asyncio.to_thread(snapshot_path.read_bytes)
        default_name = Path(existing_state.workflow_path).stem
        try:
            new_wf = parse_workflow_yaml(wf_bytes, default_name=default_name)
        except (ValidationError, ValueError) as exc:
            raise StoreError(f"Invalid workflow.snapshot.yaml: {exc}") from exc

        accepted_path = rdir / ".workflow.accepted.yaml"
        if accepted_path.is_file():
            accepted_bytes = await asyncio.to_thread(accepted_path.read_bytes)
            if hashlib.sha256(wf_bytes).hexdigest() != hashlib.sha256(accepted_bytes).hexdigest():
                old_wf = parse_workflow_yaml(accepted_bytes, default_name=default_name)
                base_path = rdir / ".workflow.baseline.yaml"
                baseline_ids: set[str] | None = None
                if base_path.is_file():
                    with contextlib.suppress(Exception):
                        base_wf = parse_workflow_yaml(
                            await asyncio.to_thread(base_path.read_bytes),
                            default_name=default_name,
                        )
                        baseline_ids = set(base_wf.nodes.keys())

                ws_cfg = await asyncio.to_thread(load_workspace_config, self.store.workspace_root)
                stored_max = existing_state.run_inputs.get("__max_injected_nodes__")
                cli_max = (
                    max_injected_nodes
                    if max_injected_nodes is not None
                    else (
                        int(stored_max)
                        if isinstance(stored_max, int) and not isinstance(stored_max, bool)
                        else None
                    )
                )
                eff_max = resolve_max_injected_nodes(
                    workspace_config=ws_cfg,
                    workflow_max=new_wf.effective_max_injected_nodes(),
                    cli_max=cli_max,
                )
                node_statuses = {
                    nid: st.status
                    for nid, st in existing_state.nodes.items()
                    if not is_stage_validator_node_id(nid)
                }
                mutation_res = await asyncio.to_thread(
                    validate_snapshot_mutation,
                    old_wf,
                    new_wf,
                    self.registry,
                    node_statuses,
                    max_injected_nodes=eff_max,
                    baseline_node_ids=baseline_ids,
                    run_inputs=existing_state.run_inputs,
                )
                if not mutation_res.valid:
                    err_text = "; ".join(
                        i.message for i in mutation_res.issues if i.severity == "error"
                    )
                    raise StoreError(f"Invalid workflow.snapshot.yaml mutation: {err_text}")

                if mutation_res.superseded_failed_node_ids:
                    yaml_rt = YAML()
                    yaml_rt.preserve_quotes = True
                    doc_data = yaml_rt.load(StringIO(wf_bytes.decode("utf-8")))
                    if isinstance(doc_data, Mapping) and isinstance(doc_data.get("nodes"), Mapping):
                        for sup_nid in mutation_res.superseded_failed_node_ids:
                            if sup_nid in doc_data["nodes"]:
                                entry = doc_data["nodes"][sup_nid]
                                if "meta" not in entry or not isinstance(entry["meta"], Mapping):
                                    entry["meta"] = {}
                                entry["meta"]["superseded_by"] = "outer_agent"
                        buf = StringIO()
                        yaml_rt.dump(doc_data, buf)
                        wf_bytes = buf.getvalue().encode("utf-8")
                        new_wf = parse_workflow_yaml(wf_bytes, default_name=default_name)

                await asyncio.to_thread(
                    self.store.add_node_runs,
                    run_id,
                    execution_node_ids(new_wf),
                )
                event_log = self.store.event_log(run_id)
                for added_nid in mutation_res.added_node_ids:
                    await asyncio.to_thread(
                        event_log.append,
                        "node_status",
                        NodeStatusData(
                            run_id=run_id,
                            node_id=added_nid,
                            status=NodeStatus.PENDING,
                            cache_hit=False,
                            attempt=0,
                        ),
                    )
                await asyncio.to_thread(self.store.update_workflow_snapshot, run_id, wf_bytes)
                return new_wf, wf_bytes

        await asyncio.to_thread(self.store.add_node_runs, run_id, execution_node_ids(new_wf))
        return new_wf, wf_bytes

    async def resume(
        self,
        run_id: str,
        *,
        options: SchedulerOptions | None = None,
    ) -> RunState:
        """Resume an existing failed, canceled, or waiting run, taking ownership."""
        await asyncio.to_thread(self.store.reconcile_dead_owners)
        resolved_id = await asyncio.to_thread(self.store.resolve_run_id, run_id)
        pre_claim = await asyncio.to_thread(self.store.get_run_state, resolved_id)
        prev_status = pre_claim.status if pre_claim is not None else RunStatus.WAITING_FOR_USER
        existing_state = await asyncio.to_thread(self.store.claim_run_for_resume, resolved_id)

        refresh_fn = getattr(self.registry, "refresh", None)
        if callable(refresh_fn):
            await asyncio.to_thread(refresh_fn)

        base_opts = options or SchedulerOptions()
        try:
            workflow, wf_bytes = await self.validate_and_prepare_resume_snapshot(
                resolved_id,
                existing_state,
                max_injected_nodes=base_opts.max_injected_nodes,
            )
        except StoreError:
            await asyncio.to_thread(
                self.store.release_ownership,
                resolved_id,
                expected_pid=os.getpid(),
            )
            await asyncio.to_thread(
                self.store.update_run_status,
                resolved_id,
                prev_status,
            )
            raise

        merged_inputs = dict(existing_state.run_inputs)
        merged_inputs.update(base_opts.run_inputs)
        if base_opts.agent_provider is not None:
            prov_str = (
                base_opts.agent_provider.value
                if isinstance(base_opts.agent_provider, AgentProvider)
                else str(base_opts.agent_provider)
            )
            merged_inputs["__agent_provider__"] = prov_str
        if base_opts.agent_model is not None:
            merged_inputs["__agent_model__"] = base_opts.agent_model
        if base_opts.max_injected_nodes is not None:
            merged_inputs["__max_injected_nodes__"] = base_opts.max_injected_nodes
        if (
            base_opts.agent_provider is not None
            or base_opts.agent_model is not None
            or base_opts.max_injected_nodes is not None
        ):
            await asyncio.to_thread(
                self.store.update_run_inputs,
                resolved_id,
                merged_inputs,
            )
        merged_opts = SchedulerOptions(
            concurrency=base_opts.concurrency,
            run_inputs=merged_inputs,
            answers=dict(base_opts.answers),
            non_interactive=base_opts.non_interactive,
            no_cache=base_opts.no_cache,
            agent_provider=base_opts.agent_provider,
            agent_model=base_opts.agent_model,
            max_injected_nodes=base_opts.max_injected_nodes,
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
        effective_run_inputs = dict(opts.run_inputs)
        if opts.agent_provider is not None:
            prov_str = (
                opts.agent_provider.value
                if isinstance(opts.agent_provider, AgentProvider)
                else str(opts.agent_provider)
            )
            effective_run_inputs["__agent_provider__"] = prov_str
        if opts.agent_model is not None:
            effective_run_inputs["__agent_model__"] = opts.agent_model
        if opts.max_injected_nodes is not None:
            effective_run_inputs["__max_injected_nodes__"] = opts.max_injected_nodes
        if effective_run_inputs != opts.run_inputs:
            opts = SchedulerOptions(
                concurrency=opts.concurrency,
                run_inputs=effective_run_inputs,
                answers=dict(opts.answers),
                non_interactive=opts.non_interactive,
                no_cache=opts.no_cache,
                agent_provider=opts.agent_provider,
                agent_model=opts.agent_model,
                max_injected_nodes=opts.max_injected_nodes,
                poll_interval=opts.poll_interval,
                cancel_event=opts.cancel_event,
                checkpoint_callback=opts.checkpoint_callback,
                stage_approval_callback=opts.stage_approval_callback,
                stage_inputs_callback=opts.stage_inputs_callback,
                on_node_status=opts.on_node_status,
            )
        ws_concurrency = load_workspace_config(self.store.workspace_root).concurrency
        concurrency = (
            opts.concurrency or workflow.concurrency or ws_concurrency or (os.cpu_count() or 1)
        )
        if concurrency < 1:
            concurrency = 1

        if workflow_bytes is not None:
            raw_wf = workflow_bytes
        else:
            from plynx.server.routes.workflows import dump_workflow_yaml

            raw_wf = dump_workflow_yaml(workflow)

        node_ids = execution_node_ids(workflow)
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
                await asyncio.to_thread(self.store.add_node_runs, active_run_id, node_ids)
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
        resolved_answers: Mapping[str, CheckpointAnswer],
        workflow: Workflow | None = None,
    ) -> InputsManifest:
        dst_node_dir = self.store.node_dir(run_id, node_id)
        state = self.store.get_run_state(run_id)
        db_checkpoints = state.checkpoints if state is not None else None
        wf_prov = workflow.agent.provider if workflow is not None and workflow.agent else None
        wf_model = workflow.agent.model if workflow is not None and workflow.agent else None
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
            workflow_agent_provider=wf_prov,
            workflow_agent_model=wf_model,
            cli_agent_provider=opts.agent_provider,
            cli_agent_model=opts.agent_model,
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
            params_hash=compute_params_hash(
                scalars,
                checkpoint_answers=inputs.checkpoint_answers,
                allow_graph_edits=inputs.allow_graph_edits,
            ),
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
            warnings=list(result.outputs.warnings) if result.outputs is not None else [],
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
        resolved_answers: Mapping[str, CheckpointAnswer],
        *,
        already_passed: bool = False,
        cancel_event: asyncio.Event | None = None,
    ) -> str | None:
        if cancel_event is not None and cancel_event.is_set():
            return None

        key = f"{node_id}.{cp.checkpoint_id}"
        if not already_passed and key in resolved_answers:
            encoded = _encode_answer(cp, resolved_answers[key])
            if encoded is not None:
                return await self._record_answer_first_wins(
                    run_id,
                    node_id,
                    cp.checkpoint_id,
                    encoded,
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
