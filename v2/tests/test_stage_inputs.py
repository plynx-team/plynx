"""Tests for deferred stage inputs at stage completion."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from plynx.api_models import NodeStatus, RunStatus, StageGateStatus
from plynx.engine import FakeExecutor, Scheduler, SchedulerOptions
from plynx.server.app import create_app
from plynx.store import RunStore
from plynx.workflow.models import Workflow


def _two_stage_input_workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "deferred_input_workflow",
            "stages": {
                "prepare": {"title": "1. Prepare", "require_approval": False},
                "process": {"title": "2. Process", "require_approval": False},
            },
            "nodes": {
                "s1_echo": {
                    "op": "standard_io/demo:Echo",
                    "stage": "prepare",
                    "inputs": {"text": "hello_"},
                },
                "s2_concat": {
                    "op": "standard_io/demo:Concat",
                    "stage": "process",
                    "inputs": {"b": "world"},
                },
            },
        }
    )


def test_stage_inputs_deferred_until_previous_stage_completes(tmp_path: Path) -> None:
    """Stage 2 with unbound required input pauses execution until user provides input."""
    store = RunStore(tmp_path)
    executor = FakeExecutor()
    scheduler = Scheduler(store, executor)
    wf = _two_stage_input_workflow()

    async def _run_and_provide_input() -> str:
        run_task = asyncio.create_task(
            scheduler.run(
                wf,
                options=SchedulerOptions(concurrency=2, no_cache=True, poll_interval=0.01),
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
                    and "process" in state.stage_gates
                    and state.stage_gates["process"].status == StageGateStatus.WAITING
                    and state.status == RunStatus.WAITING_FOR_USER
                ):
                    break
            await asyncio.sleep(0.01)

        assert run_id is not None
        mid_state = store.get_run_state(run_id)
        assert mid_state is not None
        assert mid_state.status == RunStatus.WAITING_FOR_USER
        # Stage 1 finished successfully
        assert mid_state.nodes["s1_echo"].status == NodeStatus.SUCCESS
        # Stage 2 node has not started because input 'a' is missing
        assert mid_state.nodes["s2_concat"].status == NodeStatus.PENDING

        # Now user provides the input for stage 2 and approves the gate
        store.update_run_inputs(run_id, {"s2_concat.a": "hello_"})
        assert store.approve_stage_gate(run_id, "process") is True

        final_state = await run_task
        assert final_state.status == RunStatus.SUCCESS
        assert final_state.nodes["s2_concat"].status == NodeStatus.SUCCESS
        return run_id

    run_id = asyncio.run(_run_and_provide_input())
    final_state = store.get_run_state(run_id)
    assert final_state is not None
    assert final_state.status == RunStatus.SUCCESS
    assert final_state.run_inputs.get("s2_concat.a") == "hello_"


def test_stage_inputs_via_rest_api(tmp_path: Path) -> None:
    """POST /runs/{id}/stages/{stage_id}/inputs injects inputs and unblocks stage."""
    # Write workflow file to workspace
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf_file = wf_dir / "test_pipe.yaml"
    wf_file.write_text(
        """version: 1
name: pipe
stages:
  stage1:
    title: "Stage 1"
  stage2:
    title: "Stage 2"
nodes:
  n1:
    op: standard_io/demo:Echo
    stage: stage1
    inputs:
      text: hello_
  n2:
    op: standard_io/demo:Concat
    stage: stage2
    inputs:
      b: world
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path, executor_factory=lambda _: FakeExecutor())

    async def _test() -> None:
        import httpx

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Start run with empty inputs (stage 2 input deferred)
            res = await client.post("/runs", json={"workflow_path": "workflows/test_pipe.yaml", "inputs": {}})
            assert res.status_code == 201
            run_id = res.json()["run_id"]

            # 2. Wait until Stage 1 completes and Stage 2 is waiting for input
            deadline = time.monotonic() + 10.0
            waiting = False
            while time.monotonic() < deadline:
                st_res = await client.get(f"/runs/{run_id}")
                assert st_res.status_code == 200
                state = st_res.json()
                if (
                    state["status"] == "WAITING_FOR_USER"
                    and "stage2" in state["stage_gates"]
                    and state["stage_gates"]["stage2"]["status"] == "WAITING"
                ):
                    waiting = True
                    break
                await asyncio.sleep(0.02)

            assert waiting is True

            # 3. Submit inputs for stage 2 via POST /stages/{stage_id}/inputs
            inp_res = await client.post(
                f"/runs/{run_id}/stages/stage2/inputs",
                json={"inputs": {"n2.a": "hello_"}},
            )
            assert inp_res.status_code == 200

            # 4. Wait for run to finish with SUCCESS
            deadline = time.monotonic() + 10.0
            success = False
            while time.monotonic() < deadline:
                st_res = await client.get(f"/runs/{run_id}")
                state = st_res.json()
                if state["status"] == "SUCCESS":
                    success = True
                    break
                await asyncio.sleep(0.02)

            assert success is True

    asyncio.run(_test())
