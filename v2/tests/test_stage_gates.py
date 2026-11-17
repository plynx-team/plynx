"""Tests for Task 4.3: Stage gates (require_approval: true)."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from plynx.api_models import (
    NodeStatus,
    NodeStatusEvent,
    RunStatus,
    RunStatusEvent,
    StageApprovalEvent,
    StageGateStatus,
    StageResolvedEvent,
)
from plynx.engine import (
    FakeExecutor,
    FakeNodeScript,
    LocalExecutor,
    Scheduler,
    SchedulerOptions,
)
from plynx.store import RunStore
from plynx.workflow.models import Workflow


def _two_stage_gated_workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "staged_workflow",
            "stages": {
                "prepare": {"title": "1. Prepare", "require_approval": True},
                "publish": {"title": "2. Publish", "require_approval": False},
            },
            "nodes": {
                "s1_fast": {
                    "op": "standard_io/demo:Echo",
                    "stage": "prepare",
                    "inputs": {"text": "fast"},
                },
                "s1_slow": {
                    "op": "standard_io/demo:Echo",
                    "stage": "prepare",
                    "inputs": {"text": "slow"},
                },
                "s2_dep": {
                    "op": "standard_io/demo:Concat",
                    "stage": "publish",
                    "inputs": {"a": "$s1_fast.text", "b": "$s1_slow.text"},
                },
                "s2_indep": {
                    "op": "standard_io/demo:Echo",
                    "stage": "publish",
                    "inputs": {"text": "independent_stage2"},
                },
            },
        }
    )


def test_stage_gate_pauses_whole_stage_and_blocks_next_stage_until_approved(
    tmp_path: Path,
) -> None:
    """No node of stage N+1 starts before approval; stage_approval and stage_resolved appear."""
    store = RunStore(tmp_path)
    executor = FakeExecutor(
        scripts={
            "s1_slow": FakeNodeScript(delay=0.04),
        }
    )
    scheduler = Scheduler(store, executor)
    wf = _two_stage_gated_workflow()

    async def _run_and_approve() -> str:
        run_task = asyncio.create_task(
            scheduler.run(
                wf,
                options=SchedulerOptions(concurrency=4, no_cache=True, poll_interval=0.01),
            )
        )

        run_id: str | None = None
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            runs = store.list_runs()
            if runs:
                run_id = runs[0].id
                state = store.get_run_state(run_id)
                if (
                    state is not None
                    and "prepare" in state.stage_gates
                    and state.stage_gates["prepare"].status == StageGateStatus.WAITING
                    and state.status == RunStatus.WAITING_FOR_USER
                ):
                    break
            await asyncio.sleep(0.01)

        assert run_id is not None
        mid_state = store.get_run_state(run_id)
        assert mid_state is not None
        assert mid_state.status == RunStatus.WAITING_FOR_USER
        assert mid_state.nodes["s1_fast"].status == NodeStatus.SUCCESS
        assert mid_state.nodes["s1_slow"].status == NodeStatus.SUCCESS
        # Neither dependent nor independent stage 2 node may have started yet.
        assert mid_state.nodes["s2_dep"].status == NodeStatus.PENDING
        assert mid_state.nodes["s2_dep"].started_at is None
        assert mid_state.nodes["s2_indep"].status == NodeStatus.PENDING
        assert mid_state.nodes["s2_indep"].started_at is None

        # Wait briefly so approval timestamp is cleanly separated from stage 1 completion.
        await asyncio.sleep(0.03)
        assert store.approve_stage_gate(run_id, "prepare") is True
        # Second approval is a no-op.
        assert store.approve_stage_gate(run_id, "prepare") is False

        final_state = await run_task
        assert final_state.status == RunStatus.SUCCESS
        return run_id

    run_id = asyncio.run(_run_and_approve())
    final_state = store.get_run_state(run_id)
    assert final_state is not None

    gate = final_state.stage_gates["prepare"]
    assert gate.status == StageGateStatus.APPROVED
    assert gate.decided_at is not None

    for nid in ("s2_dep", "s2_indep"):
        node_state = final_state.nodes[nid]
        assert node_state.status == NodeStatus.SUCCESS
        assert node_state.started_at is not None
        assert node_state.started_at >= gate.decided_at

    events = store.event_log(run_id).read_after(0)
    approval_events = [e for e in events if isinstance(e, StageApprovalEvent)]
    resolved_events = [e for e in events if isinstance(e, StageResolvedEvent)]
    assert len(approval_events) == 1
    assert approval_events[0].data.stage_id == "prepare"
    assert approval_events[0].data.title == "1. Prepare"
    assert len(resolved_events) == 1
    assert resolved_events[0].data.stage_id == "prepare"

    s1_slow_success_seq = next(
        e.seq
        for e in events
        if isinstance(e, NodeStatusEvent)
        and e.data.node_id == "s1_slow"
        and e.data.status == NodeStatus.SUCCESS
    )
    s2_min_running_seq = min(
        e.seq
        for e in events
        if isinstance(e, NodeStatusEvent)
        and e.data.node_id in ("s2_dep", "s2_indep")
        and e.data.status == NodeStatus.RUNNING
    )
    assert s1_slow_success_seq < approval_events[0].seq < resolved_events[0].seq
    assert resolved_events[0].seq < s2_min_running_seq

    run_statuses = [e.data.status for e in events if isinstance(e, RunStatusEvent)]
    assert run_statuses == [
        RunStatus.RUNNING,
        RunStatus.WAITING_FOR_USER,
        RunStatus.RUNNING,
        RunStatus.SUCCESS,
    ]


def test_stage_gate_with_real_local_executor(tmp_path: Path) -> None:
    """Real child processes respect stage gate approval timing."""
    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)
    wf = _two_stage_gated_workflow()

    async def _run_and_approve() -> str:
        run_task = asyncio.create_task(
            scheduler.run(
                wf,
                options=SchedulerOptions(concurrency=2, no_cache=True, poll_interval=0.02),
            )
        )
        run_id: str | None = None
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            runs = store.list_runs()
            if runs:
                run_id = runs[0].id
                gate = store.get_stage_gate(run_id, "prepare")
                if gate is not None and gate.status == StageGateStatus.WAITING:
                    break
            await asyncio.sleep(0.02)

        assert run_id is not None
        await asyncio.sleep(0.02)
        assert store.approve_stage_gate(run_id, "prepare") is True
        final_state = await run_task
        assert final_state.status == RunStatus.SUCCESS
        return run_id

    run_id = asyncio.run(_run_and_approve())
    state = store.get_run_state(run_id)
    assert state is not None
    decided_at = state.stage_gates["prepare"].decided_at
    assert decided_at is not None
    for nid in ("s2_dep", "s2_indep"):
        started_at = state.nodes[nid].started_at
        assert started_at is not None
        assert started_at >= decided_at


def test_stage_gate_cli_non_interactive_and_interactive_stdin(tmp_path: Path) -> None:
    """CLI exits 2 on gated stage in non-interactive mode; piped y/n drives approval."""
    wf_path = tmp_path / "gated.yaml"
    wf_path.write_text(
        """version: 1
name: cli_gated
stages:
  step1:
    title: "Step 1"
    require_approval: true
  step2:
    title: "Step 2"
nodes:
  a:
    op: standard_io/demo:Echo
    stage: step1
    inputs:
      text: hello
  b:
    op: standard_io/demo:Echo
    stage: step2
    inputs:
      text: $a.text
""",
        encoding="utf-8",
    )

    clean_env = dict(os.environ)
    clean_env.pop("CI", None)

    # Non-interactive pauses with exit 2.
    paused = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "run", "--non-interactive", "--no-cache", str(wf_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )
    assert paused.returncode == 2, f"stdout={paused.stdout}\nstderr={paused.stderr}"

    # Interactive decline ('n') pauses with exit 2.
    declined = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "run", "--no-cache", str(wf_path)],
        cwd=tmp_path,
        input="n\n",
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )
    assert declined.returncode == 2, f"stdout={declined.stdout}\nstderr={declined.stderr}"
    assert "Approve & continue?" in declined.stdout

    # Interactive approve ('y') finishes with exit 0.
    approved = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "run", "--no-cache", str(wf_path)],
        cwd=tmp_path,
        input="y\n",
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )
    assert approved.returncode == 0, f"stdout={approved.stdout}\nstderr={approved.stderr}"

    store = RunStore(tmp_path)
    latest = store.get_run_state(store.list_runs()[0].id)
    assert latest is not None
    assert latest.status == RunStatus.SUCCESS
    assert latest.stage_gates["step1"].status == StageGateStatus.APPROVED
    assert latest.nodes["b"].started_at is not None
    assert latest.stage_gates["step1"].decided_at is not None
    assert latest.nodes["b"].started_at >= latest.stage_gates["step1"].decided_at


def test_failed_node_in_gated_stage_never_opens_gate_or_starts_next_stage(
    tmp_path: Path,
) -> None:
    """If a node in a gated stage fails, the stage gate never opens and next stage never runs."""
    store = RunStore(tmp_path)
    executor = FakeExecutor(scripts={"s1_slow": FakeNodeScript(fail=True, error="failed s1")})
    scheduler = Scheduler(store, executor)

    state = asyncio.run(
        scheduler.run(
            _two_stage_gated_workflow(),
            options=SchedulerOptions(no_cache=True),
        )
    )
    assert state.status == RunStatus.FAILED
    assert state.stage_gates == {}
    assert state.nodes["s1_fast"].status == NodeStatus.SUCCESS
    assert state.nodes["s1_slow"].status == NodeStatus.FAILED
    assert state.nodes["s2_dep"].status == NodeStatus.BLOCKED
    assert state.nodes["s2_indep"].status == NodeStatus.PENDING
    assert state.nodes["s2_indep"].started_at is None
