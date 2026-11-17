"""DAG workflow scheduler using ``graphlib.TopologicalSorter`` and ``asyncio``."""

from __future__ import annotations

import asyncio
import contextlib
import graphlib
import os
import time
from collections.abc import Awaitable, Callable, Mapping
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
    NodeCheckpointData,
    NodeStatus,
    NodeStatusData,
    RunState,
    RunStatus,
    RunStatusData,
    StageApprovalData,
    StageGateStatus,
    StageResolvedData,
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
from plynx.engine.executor import ExecutionRequest, Executor, NodeResult
from plynx.registry import OpRegistry, Registry
from plynx.store.run_store import RunStore, atomic_write_text
from plynx.workflow.models import NodeRef, NodeSpec, Workflow

CheckpointCallback = Callable[[str, str, CheckpointManifest], Awaitable[str | None] | str | None]
StageApprovalCallback = Callable[[str, str], Awaitable[bool] | bool]
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
    checkpoint_callback: CheckpointCallback | None = None
    stage_approval_callback: StageApprovalCallback | None = None
    on_node_status: NodeStatusCallback | None = None


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
        self.registry: OpRegistry = Registry(store.workspace_root) if registry is None else registry
        self.blob_store = blob_store or BlobStore.from_workspace(store.workspace_root)

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
        is_fresh_run = existing_state is None or run_id is None
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
        resolved_answers: dict[str, str] = dict(opts.answers)

        await asyncio.to_thread(
            event_log.append,
            "run_status",
            RunStatusData(run_id=active_run_id, status=RunStatus.RUNNING),
        )
        current_run_status = RunStatus.RUNNING
        run_status_lock = asyncio.Lock()

        node_statuses: dict[str, NodeStatus] = {}
        node_attempts: dict[str, int] = dict.fromkeys(node_ids, 0)
        completed_outputs: dict[str, dict[str, ResultValue | OutputValue]] = {}

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

        stage_order = list(workflow.stages.keys())
        stage_index = {sid: idx for idx, sid in enumerate(stage_order)}
        stage_nodes: dict[str, list[str]] = {sid: [] for sid in stage_order}
        for nid, spec in workflow.nodes.items():
            stage_nodes.setdefault(spec.stage, []).append(nid)

        semaphore = asyncio.Semaphore(concurrency)
        running_tasks: dict[asyncio.Task[tuple[str, bool]], str] = {}
        gate_tasks: dict[asyncio.Task[tuple[str, bool]], str] = {}
        runnable_nodes: set[str] = set()
        waiting_nodes: set[str] = set()
        opened_gates: set[str] = set()
        waiting_gates: set[str] = set()
        approved_gates: set[str] = set()
        emitted_cp_resolutions: set[tuple[str, str]] = set()
        emitted_gate_resolutions: set[str] = set()

        def _is_node_stage_gated(nid: str) -> bool:
            target_idx = stage_index[workflow.nodes[nid].stage]
            for earlier_sid in stage_order[:target_idx]:
                if (
                    workflow.stages[earlier_sid].require_approval
                    and earlier_sid not in approved_gates
                ):
                    return True
            return False

        async def _sync_run_status() -> None:
            nonlocal current_run_status
            if opts.non_interactive:
                return
            async with run_status_lock:
                desired: RunStatus | None = None
                if not runnable_nodes and (waiting_nodes or waiting_gates):
                    desired = RunStatus.WAITING_FOR_USER
                elif runnable_nodes and current_run_status == RunStatus.WAITING_FOR_USER:
                    desired = RunStatus.RUNNING
                if desired is not None and desired != current_run_status:
                    current_run_status = desired
                    await asyncio.to_thread(
                        self.store.update_run_status,
                        active_run_id,
                        desired,
                    )
                    await asyncio.to_thread(
                        event_log.append,
                        "run_status",
                        RunStatusData(run_id=active_run_id, status=desired),
                    )

        async def _emit_node_status(
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
            node_statuses[nid] = status
            await asyncio.to_thread(
                self.store.update_node_status,
                active_run_id,
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

            while True:
                async with semaphore:
                    attempt = node_attempts[nid] + 1
                    node_attempts[nid] = attempt
                    inputs_manifest = await asyncio.to_thread(
                        self._build_inputs_manifest,
                        active_run_id,
                        nid,
                        spec,
                        completed_outputs,
                        opts,
                        resolved_answers,
                    )
                    await asyncio.to_thread(
                        atomic_write_text,
                        node_dir / "inputs.json",
                        inputs_manifest.to_json(),
                    )
                    started_ts = time.time()
                    emitted_running = False

                    op_entry = self.registry.get(spec.op)
                    is_cacheable = op_entry.cacheable if op_entry is not None else True
                    cache_key = self._compute_node_cache_key(nid, spec, inputs_manifest)

                    if is_fresh_run and not opts.no_cache and is_cacheable:
                        cached_result = await asyncio.to_thread(
                            self._lookup_cache,
                            cache_key,
                        )
                        if cached_result is not None:
                            hit_manifest = ResultManifest(
                                status="SUCCESS",
                                cache_key=cache_key,
                                cache_hit=True,
                                started_at=cached_result.started_at,
                                finished_at=cached_result.finished_at,
                                outputs=cached_result.outputs,
                            )
                            await asyncio.to_thread(
                                write_result_manifest,
                                node_dir,
                                hit_manifest,
                            )
                            completed_outputs[nid] = dict(cached_result.outputs)
                            await _emit_node_status(
                                nid,
                                NodeStatus.SUCCESS,
                                cache_hit=True,
                                cache_key=cache_key,
                                attempt=0,
                                started_at=cached_result.started_at,
                                finished_at=cached_result.finished_at,
                            )
                            return nid, True

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
                        result_manifest = await asyncio.to_thread(
                            self._ingest_and_write_result,
                            node_dir,
                            result,
                            outs,
                            cache_key,
                            is_cacheable=is_cacheable,
                        )
                        completed_outputs[nid] = dict(result_manifest.outputs)
                        await _emit_node_status(
                            nid,
                            NodeStatus.SUCCESS,
                            cache_key=cache_key,
                            attempt=attempt,
                            exit_code=result.exit_code,
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                        )
                        return nid, True

                # Semaphore is released while waiting for user input so other branches proceed.
                if result.status == NodeStatus.WAITING_FOR_USER and result.checkpoint is not None:
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
                    runnable_nodes.discard(nid)
                    waiting_nodes.add(nid)
                    await _sync_run_status()

                    answer = await self._resolve_checkpoint_answer(
                        active_run_id,
                        nid,
                        cp,
                        opts,
                        resolved_answers,
                        already_passed=cp.checkpoint_id in inputs_manifest.checkpoint_answers,
                    )
                    if answer is None:
                        return nid, False

                    cp_key = (nid, cp.checkpoint_id)
                    if cp_key not in emitted_cp_resolutions:
                        emitted_cp_resolutions.add(cp_key)
                        await asyncio.to_thread(
                            event_log.append,
                            "checkpoint_resolved",
                            CheckpointResolvedData(
                                run_id=active_run_id,
                                node_id=nid,
                                checkpoint_id=cp.checkpoint_id,
                            ),
                        )
                    resolved_answers[f"{nid}.{cp.checkpoint_id}"] = answer
                    waiting_nodes.discard(nid)
                    runnable_nodes.add(nid)
                    await _sync_run_status()
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

        async def _wait_for_stage_gate(stage_id: str) -> tuple[str, bool]:
            title = workflow.stages[stage_id].title or stage_id
            approved = await self._resolve_stage_approval(
                active_run_id,
                stage_id,
                title,
                opts,
            )
            if not approved:
                return stage_id, False

            if stage_id not in emitted_gate_resolutions:
                emitted_gate_resolutions.add(stage_id)
                await asyncio.to_thread(
                    event_log.append,
                    "stage_resolved",
                    StageResolvedData(run_id=active_run_id, stage_id=stage_id),
                )
            return stage_id, True

        async def _open_ready_stage_gates() -> bool:
            progressed = False
            for sid in stage_order:
                stage = workflow.stages[sid]
                if not stage.require_approval:
                    continue
                if sid in approved_gates:
                    continue
                if sid in opened_gates:
                    # Wait for this stage gate before opening any later stage gate.
                    break
                nodes_in_stage = stage_nodes.get(sid, [])
                if not all(node_statuses.get(n) == NodeStatus.SUCCESS for n in nodes_in_stage):
                    break

                await asyncio.to_thread(self.store.create_stage_gate, active_run_id, sid)
                await asyncio.to_thread(
                    event_log.append,
                    "stage_approval",
                    StageApprovalData(
                        run_id=active_run_id,
                        stage_id=sid,
                        title=stage.title or sid,
                    ),
                )
                opened_gates.add(sid)
                waiting_gates.add(sid)
                progressed = True
                if not opts.non_interactive:
                    gtask = asyncio.create_task(_wait_for_stage_gate(sid))
                    gate_tasks[gtask] = sid
                break
            return progressed

        pending_discard: list[str] = []
        deferred_ready: list[str] = []
        while True:
            if sorter.is_active():
                deferred_ready.extend(sorter.get_ready())

            await _open_ready_stage_gates()

            blocked_progressed = False
            still_deferred: list[str] = []
            to_launch: list[str] = []
            for nid in deferred_ready:
                deps = dep_graph[nid]
                if any(
                    node_statuses.get(dep)
                    in (NodeStatus.FAILED, NodeStatus.CANCELED, NodeStatus.BLOCKED)
                    for dep in deps
                ):
                    await _emit_node_status(nid, NodeStatus.BLOCKED, attempt=0)
                    sorter.done(nid)
                    blocked_progressed = True
                elif _is_node_stage_gated(nid):
                    still_deferred.append(nid)
                else:
                    runnable_nodes.add(nid)
                    to_launch.append(nid)
            deferred_ready = still_deferred

            for done_nid in pending_discard:
                runnable_nodes.discard(done_nid)
            pending_discard.clear()

            if to_launch:
                await _sync_run_status()
                for nid in to_launch:
                    task = asyncio.create_task(_execute_node(nid))
                    running_tasks[task] = nid

            if blocked_progressed and not running_tasks and not gate_tasks:
                continue

            all_tasks: set[asyncio.Task[tuple[str, bool]]] = set(running_tasks.keys()) | set(
                gate_tasks.keys()
            )
            if not all_tasks:
                break

            await _sync_run_status()

            done, _ = await asyncio.wait(
                all_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for completed_task in done:
                if completed_task in running_tasks:
                    running_tasks.pop(completed_task, None)
                    finished_nid, mark_done = await completed_task
                    pending_discard.append(finished_nid)
                    if mark_done:
                        sorter.done(finished_nid)
                elif completed_task in gate_tasks:
                    gate_tasks.pop(completed_task, None)
                    gate_sid, approved = await completed_task
                    if approved:
                        waiting_gates.discard(gate_sid)
                        approved_gates.add(gate_sid)

        for done_nid in pending_discard:
            runnable_nodes.discard(done_nid)
        pending_discard.clear()

        final_status = self._compute_final_run_status(
            node_statuses,
            has_waiting_gate=bool(waiting_gates),
        )
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
        if final_status != current_run_status or final_status in (
            RunStatus.SUCCESS,
            RunStatus.FAILED,
            RunStatus.CANCELED,
        ):
            await asyncio.to_thread(
                event_log.append,
                "run_status",
                RunStatusData(run_id=active_run_id, status=final_status, error=run_error),
            )

        final_state = await asyncio.to_thread(self.store.get_run_state, active_run_id)
        assert final_state is not None

        await asyncio.to_thread(
            enforce_cache_budget,
            self.store.workspace_root,
            store=self.store,
            blob_store=self.blob_store,
        )

        return final_state

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
    ) -> str | None:
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

        if opts.checkpoint_callback is None:
            return await _poll_db_answer()

        callback = opts.checkpoint_callback

        async def _invoke_callback() -> str | None:
            maybe_coro = callback(node_id, cp.checkpoint_id, cp)
            if isinstance(maybe_coro, Awaitable):
                return await maybe_coro
            return maybe_coro

        poll_task: asyncio.Task[str] = asyncio.create_task(_poll_db_answer())
        cb_task: asyncio.Task[str | None] = asyncio.create_task(_invoke_callback())
        try:
            done, pending = await asyncio.wait(
                {poll_task, cb_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p_task in pending:
                p_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await p_task

            if poll_task in done and not poll_task.cancelled():
                return poll_task.result()

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
        finally:
            for task in (poll_task, cb_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    async def _resolve_stage_approval(
        self,
        run_id: str,
        stage_id: str,
        title: str,
        opts: SchedulerOptions,
    ) -> bool:
        existing = await asyncio.to_thread(self.store.get_stage_gate, run_id, stage_id)
        if existing is not None and existing.status == StageGateStatus.APPROVED:
            return True

        if opts.non_interactive:
            return False

        poll_sleep = max(opts.poll_interval, 0.005)

        async def _poll_db_gate() -> bool:
            while True:
                await asyncio.sleep(poll_sleep)
                row = await asyncio.to_thread(self.store.get_stage_gate, run_id, stage_id)
                if row is not None and row.status == StageGateStatus.APPROVED:
                    return True

        if opts.stage_approval_callback is None:
            return await _poll_db_gate()

        callback = opts.stage_approval_callback

        async def _invoke_callback() -> bool:
            maybe_coro = callback(stage_id, title)
            if isinstance(maybe_coro, Awaitable):
                return bool(await maybe_coro)
            return bool(maybe_coro)

        poll_task: asyncio.Task[bool] = asyncio.create_task(_poll_db_gate())
        cb_task: asyncio.Task[bool] = asyncio.create_task(_invoke_callback())
        try:
            done, pending = await asyncio.wait(
                {poll_task, cb_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p_task in pending:
                p_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await p_task

            if poll_task in done and not poll_task.cancelled():
                return poll_task.result()

            approved = cb_task.result()
            if approved:
                await asyncio.to_thread(self.store.approve_stage_gate, run_id, stage_id)
                return True

            latest = await asyncio.to_thread(self.store.get_stage_gate, run_id, stage_id)
            return latest is not None and latest.status == StageGateStatus.APPROVED
        finally:
            for task in (poll_task, cb_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

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
