"""Tests for Task 4.1: Checkpoints in the engine."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from plynx.api_models import (
    CheckpointResolvedEvent,
    NodeCheckpointEvent,
    NodeStatus,
    NodeStatusEvent,
    RunStatus,
    RunStatusEvent,
)
from plynx.engine import (
    ExecutionRequest,
    FakeExecutor,
    FakeNodeScript,
    LocalExecutor,
    NodeResult,
    Scheduler,
    SchedulerOptions,
)
from plynx.engine.fake_executor import scalar_outputs
from plynx.store import RunStore
from plynx.workflow.models import Workflow
from plynx_sdk.protocol import CheckpointManifest, InputsManifest, ResultManifest, ScalarValue


def _diamond_with_checkpoint_workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "diamond_cp",
            "nodes": {
                "root": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "seed"},
                },
                "left": {
                    "op": "standard_io/demo:AskFooOrWoo",
                    "inputs": {"prompt": "$root.text"},
                },
                "right": {
                    "op": "standard_io/demo:Concat",
                    "inputs": {"a": "$root.text", "b": "_right"},
                },
                "join": {
                    "op": "standard_io/demo:Concat",
                    "inputs": {"a": "$left.choice", "b": "$right.text"},
                },
            },
        }
    )


def test_diamond_independent_branch_finishes_while_checkpoint_open(tmp_path: Path) -> None:
    """In a diamond (even at concurrency=1), the other branch finishes while checkpoint is open."""
    store = RunStore(tmp_path)
    executor = FakeExecutor(
        scripts={
            "right": FakeNodeScript(delay=0.04),
        }
    )
    scheduler = Scheduler(store, executor)
    wf = _diamond_with_checkpoint_workflow()

    async def _run_and_answer() -> str:
        run_task = asyncio.create_task(
            scheduler.run(
                wf,
                options=SchedulerOptions(concurrency=1, no_cache=True, poll_interval=0.01),
            )
        )

        # Wait until checkpoint is open AND the independent branch 'right' has completed
        # while the checkpoint is still unanswered.
        run_id: str | None = None
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            runs = store.list_runs()
            if runs:
                run_id = runs[0].id
                state = store.get_run_state(run_id)
                if (
                    state is not None
                    and state.nodes["left"].status == NodeStatus.WAITING_FOR_USER
                    and state.nodes["right"].status == NodeStatus.SUCCESS
                    and state.status == RunStatus.WAITING_FOR_USER
                ):
                    break
            await asyncio.sleep(0.01)

        assert run_id is not None
        mid_state = store.get_run_state(run_id)
        assert mid_state is not None
        assert mid_state.status == RunStatus.WAITING_FOR_USER
        assert mid_state.nodes["root"].status == NodeStatus.SUCCESS
        assert mid_state.nodes["left"].status == NodeStatus.WAITING_FOR_USER
        assert mid_state.nodes["right"].status == NodeStatus.SUCCESS
        assert mid_state.nodes["join"].status == NodeStatus.PENDING
        assert len(mid_state.checkpoints) == 1
        assert mid_state.checkpoints[0].node_id == "left"
        assert mid_state.checkpoints[0].checkpoint_id == "cp_0"
        assert mid_state.checkpoints[0].answer is None

        # First answer wins; a duplicate answer returns False and must not double-resolve.
        assert store.answer_checkpoint(run_id, "left", "cp_0", "woo") is True
        assert store.answer_checkpoint(run_id, "left", "cp_0", "foo") is False

        final_state = await run_task
        assert final_state.status == RunStatus.SUCCESS
        assert final_state.nodes["left"].status == NodeStatus.SUCCESS
        assert final_state.nodes["left"].attempt == 2
        assert final_state.nodes["right"].status == NodeStatus.SUCCESS
        assert final_state.nodes["join"].status == NodeStatus.SUCCESS
        return run_id

    run_id = asyncio.run(_run_and_answer())

    join_result = ResultManifest.from_json(
        (store.node_dir(run_id, "join") / "result.json").read_text(encoding="utf-8")
    )
    assert join_result.outputs["text"] == ScalarValue(value="wooseed_right")

    events = store.event_log(run_id).read_after(0)
    cp_events = [e for e in events if isinstance(e, NodeCheckpointEvent)]
    resolved_events = [e for e in events if isinstance(e, CheckpointResolvedEvent)]
    assert len(cp_events) == 1
    assert cp_events[0].data.node_id == "left"
    assert cp_events[0].data.checkpoint_id == "cp_0"
    assert len(resolved_events) == 1
    assert resolved_events[0].data.node_id == "left"
    assert resolved_events[0].data.checkpoint_id == "cp_0"

    # Verify right reached SUCCESS before checkpoint_resolved, and join started after it.
    right_success_seq = next(
        e.seq
        for e in events
        if isinstance(e, NodeStatusEvent)
        and e.data.node_id == "right"
        and e.data.status == NodeStatus.SUCCESS
    )
    join_running_seq = next(
        e.seq
        for e in events
        if isinstance(e, NodeStatusEvent)
        and e.data.node_id == "join"
        and e.data.status == NodeStatus.RUNNING
    )
    resolved_seq = resolved_events[0].seq
    assert right_success_seq < resolved_seq < join_running_seq

    run_statuses = [e.data.status for e in events if isinstance(e, RunStatusEvent)]
    assert run_statuses == [
        RunStatus.RUNNING,
        RunStatus.WAITING_FOR_USER,
        RunStatus.RUNNING,
        RunStatus.SUCCESS,
    ]


def test_diamond_checkpoint_with_real_local_executor(tmp_path: Path) -> None:
    """Real child processes: exit 10 opens checkpoint, other branch finishes, answer replays."""
    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)
    wf = _diamond_with_checkpoint_workflow()

    async def _run_and_answer() -> str:
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
                state = store.get_run_state(run_id)
                if (
                    state is not None
                    and state.nodes["left"].status == NodeStatus.WAITING_FOR_USER
                    and state.nodes["right"].status == NodeStatus.SUCCESS
                ):
                    break
            await asyncio.sleep(0.02)

        assert run_id is not None
        mid_state = store.get_run_state(run_id)
        assert mid_state is not None
        assert mid_state.nodes["left"].status == NodeStatus.WAITING_FOR_USER
        assert mid_state.nodes["right"].status == NodeStatus.SUCCESS
        assert mid_state.nodes["join"].status == NodeStatus.PENDING

        assert store.answer_checkpoint(run_id, "left", "cp_0", "foo") is True

        final_state = await run_task
        assert final_state.status == RunStatus.SUCCESS
        return run_id

    run_id = asyncio.run(_run_and_answer())

    join_result = ResultManifest.from_json(
        (store.node_dir(run_id, "join") / "result.json").read_text(encoding="utf-8")
    )
    assert join_result.outputs["text"] == ScalarValue(value="fooseed_right")

    events = store.event_log(run_id).read_after(0)
    resolved_events = [e for e in events if isinstance(e, CheckpointResolvedEvent)]
    assert len(resolved_events) == 1


def test_diamond_non_interactive_finishes_other_branch_and_pauses(tmp_path: Path) -> None:
    """In non-interactive mode, independent branch finishes while checkpoint branch pauses."""
    store = RunStore(tmp_path)
    executor = FakeExecutor(scripts={"right": FakeNodeScript(delay=0.02)})
    scheduler = Scheduler(store, executor)

    state = asyncio.run(
        scheduler.run(
            _diamond_with_checkpoint_workflow(),
            options=SchedulerOptions(non_interactive=True, no_cache=True),
        )
    )
    assert state.status == RunStatus.WAITING_FOR_USER
    assert state.nodes["root"].status == NodeStatus.SUCCESS
    assert state.nodes["left"].status == NodeStatus.WAITING_FOR_USER
    assert state.nodes["right"].status == NodeStatus.SUCCESS
    assert state.nodes["join"].status == NodeStatus.PENDING

    events = store.event_log(state.id).read_after(0)
    assert len([e for e in events if isinstance(e, NodeCheckpointEvent)]) == 1
    assert len([e for e in events if isinstance(e, CheckpointResolvedEvent)]) == 0


def test_external_db_answer_wins_over_slow_callback(tmp_path: Path) -> None:
    """If an external client answers in SQLite before callback completes, DB answer wins."""
    store = RunStore(tmp_path)
    executor = FakeExecutor()
    scheduler = Scheduler(store, executor)
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "race_cp",
            "nodes": {
                "pick": {
                    "op": "standard_io/demo:AskFooOrWoo",
                    "inputs": {"prompt": "foo or woo?"},
                },
                "echo": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$pick.choice"},
                },
            },
        }
    )

    async def _slow_callback(
        _node_id: str,
        _cp_id: str,
        _cp: CheckpointManifest,
    ) -> str:
        await asyncio.sleep(5.0)
        return "foo"

    async def _run() -> str:
        task = asyncio.create_task(
            scheduler.run(
                wf,
                options=SchedulerOptions(
                    no_cache=True,
                    poll_interval=0.01,
                    checkpoint_callback=_slow_callback,
                ),
            )
        )
        run_id: str | None = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            runs = store.list_runs()
            if runs:
                run_id = runs[0].id
                if store.get_checkpoint(run_id, "pick", "cp_0") is not None:
                    assert store.answer_checkpoint(run_id, "pick", "cp_0", "woo") is True
                    break
            await asyncio.sleep(0.01)

        state = await task
        assert state.status == RunStatus.SUCCESS
        assert run_id is not None
        return run_id

    run_id = asyncio.run(_run())
    echo_inputs = InputsManifest.from_json(
        (store.node_dir(run_id, "echo") / "inputs.json").read_text(encoding="utf-8")
    )
    assert echo_inputs.inputs["text"] == ScalarValue(value="woo")
    events = store.event_log(run_id).read_after(0)
    assert len([e for e in events if isinstance(e, CheckpointResolvedEvent)]) == 1


def test_sequential_multiple_checkpoints_in_single_node(tmp_path: Path) -> None:
    """A node with two sequential checkpoints (cp_0 then cp_1) replays cleanly."""

    class _TwoCheckpointExecutor(FakeExecutor):
        async def run(self, request: ExecutionRequest) -> NodeResult:
            if "cp_0" not in request.inputs.checkpoint_answers:
                self.scripts[request.node_id] = FakeNodeScript(
                    checkpoint=CheckpointManifest(
                        checkpoint_id="cp_0",
                        question="First?",
                        options=["a", "b"],
                    )
                )
            elif "cp_1" not in request.inputs.checkpoint_answers:
                self.scripts[request.node_id] = FakeNodeScript(
                    checkpoint=CheckpointManifest(
                        checkpoint_id="cp_1",
                        question="Second?",
                        options=["1", "2"],
                    )
                )
            else:
                self.scripts[request.node_id] = FakeNodeScript(
                    outputs=lambda ins: scalar_outputs(
                        text=f"{ins.checkpoint_answers['cp_0']}-{ins.checkpoint_answers['cp_1']}"
                    )
                )
            return await super().run(request)

    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "two_cps",
            "nodes": {
                "ask": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "ignored"},
                }
            },
        }
    )
    store = RunStore(tmp_path)
    scheduler = Scheduler(store, _TwoCheckpointExecutor())

    def _answer(_nid: str, cp_id: str, _cp: CheckpointManifest) -> str:
        return "a" if cp_id == "cp_0" else "2"

    state = asyncio.run(
        scheduler.run(
            wf,
            options=SchedulerOptions(
                no_cache=True,
                poll_interval=0.01,
                checkpoint_callback=_answer,
            ),
        )
    )
    assert state.status == RunStatus.SUCCESS
    assert state.nodes["ask"].attempt == 3
    res = ResultManifest.from_json(
        (store.node_dir(state.id, "ask") / "result.json").read_text(encoding="utf-8")
    )
    assert res.outputs["text"] == ScalarValue(value="a-2")

    events = store.event_log(state.id).read_after(0)
    resolved_ids = [e.data.checkpoint_id for e in events if isinstance(e, CheckpointResolvedEvent)]
    assert resolved_ids == ["cp_0", "cp_1"]
