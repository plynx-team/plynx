"""Tests for ``plynx.engine`` (``Executor``, ``FakeExecutor``, and ``Scheduler``)."""

from __future__ import annotations

import asyncio
import itertools
from pathlib import Path

import pytest
from plynx.api_models import NodeStatus, NodeStatusEvent, RunStatus, RunStatusEvent
from plynx.engine import (
    ExecutionRequest,
    Executor,
    FakeExecutor,
    FakeNodeScript,
    Scheduler,
    SchedulerOptions,
)
from plynx.engine.fake_executor import scalar_outputs
from plynx.store import RunStore
from plynx.workflow.models import Workflow
from plynx_sdk.protocol import CheckpointManifest, InputsManifest, ScalarValue


def _diamond_workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "diamond",
            "nodes": {
                "root": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "seed"},
                },
                "left": {
                    "op": "standard_io/demo:Concat",
                    "inputs": {"a": "$root.text", "b": "_L"},
                },
                "right": {
                    "op": "standard_io/demo:Concat",
                    "inputs": {"a": "$root.text", "b": "_R"},
                },
                "join": {
                    "op": "standard_io/demo:Concat",
                    "inputs": {"a": "$left.text", "b": "$right.text"},
                },
            },
        }
    )


def test_executor_launch_raises_not_implemented(tmp_path: Path) -> None:
    """Executor.launch raises NotImplementedError in v2.0.0."""
    executor = FakeExecutor()
    assert isinstance(executor, Executor)
    req = ExecutionRequest(
        run_id="r1",
        node_id="n1",
        op="standard_io/demo:Echo",
        attempt=1,
        node_dir=tmp_path,
        inputs=InputsManifest(),
    )
    with pytest.raises(NotImplementedError):
        asyncio.run(executor.launch(req))


def test_four_node_diamond_runs_and_events_in_valid_order(tmp_path: Path) -> None:
    """A 4-node diamond runs to SUCCESS and emits PENDING -> RUNNING -> SUCCESS per node."""
    store = RunStore(tmp_path)
    executor = FakeExecutor(default_delay=0.01)
    scheduler = Scheduler(store, executor)

    state = asyncio.run(scheduler.run(_diamond_workflow()))
    assert state.status == RunStatus.SUCCESS
    for nid in ("root", "left", "right", "join"):
        assert state.nodes[nid].status == NodeStatus.SUCCESS
        assert state.nodes[nid].attempt == 1

    join_rec = next(r for r in executor.executions if r.node_id == "join")
    assert join_rec.inputs.inputs["a"] == ScalarValue(value="seed_L")
    assert join_rec.inputs.inputs["b"] == ScalarValue(value="seed_R")

    events = store.event_log(state.id).read_after(0)
    assert [ev.seq for ev in events] == list(range(1, len(events) + 1))
    assert isinstance(events[0], RunStatusEvent)
    assert events[0].data.status == RunStatus.RUNNING
    assert isinstance(events[-1], RunStatusEvent)
    assert events[-1].data.status == RunStatus.SUCCESS

    per_node: dict[str, list[NodeStatus]] = {nid: [] for nid in ("root", "left", "right", "join")}
    for ev in events:
        if isinstance(ev, NodeStatusEvent):
            per_node[ev.data.node_id].append(ev.data.status)

    for nid, statuses in per_node.items():
        assert statuses == [
            NodeStatus.PENDING,
            NodeStatus.RUNNING,
            NodeStatus.SUCCESS,
        ], f"Unexpected status sequence for {nid}: {statuses}"


def test_failing_node_blocks_only_dependents_while_other_branch_finishes(
    tmp_path: Path,
) -> None:
    """A failing node marks its downstream dependents BLOCKED while independent branches finish."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "partial_fail",
            "nodes": {
                "root": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "hi"},
                },
                "bad_branch": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$root.text"},
                },
                "blocked_child": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$bad_branch.text"},
                },
                "blocked_grandchild": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$blocked_child.text"},
                },
                "good_branch": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$root.text"},
                },
                "good_child": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$good_branch.text"},
                },
            },
        }
    )
    store = RunStore(tmp_path)
    executor = FakeExecutor(
        scripts={
            "bad_branch": FakeNodeScript(fail=True, error="boom"),
            "good_branch": FakeNodeScript(delay=0.02),
        }
    )
    scheduler = Scheduler(store, executor)

    state = asyncio.run(scheduler.run(wf, options=SchedulerOptions(no_cache=True)))
    assert state.status == RunStatus.FAILED
    assert state.nodes["root"].status == NodeStatus.SUCCESS
    assert state.nodes["bad_branch"].status == NodeStatus.FAILED
    assert state.nodes["bad_branch"].error == "boom"
    assert state.nodes["blocked_child"].status == NodeStatus.BLOCKED
    assert state.nodes["blocked_grandchild"].status == NodeStatus.BLOCKED
    assert state.nodes["good_branch"].status == NodeStatus.SUCCESS
    assert state.nodes["good_child"].status == NodeStatus.SUCCESS

    executed_nodes = {rec.node_id for rec in executor.executions}
    assert "blocked_child" not in executed_nodes
    assert "blocked_grandchild" not in executed_nodes

    events = store.event_log(state.id).read_after(0)
    blocked_statuses = [
        ev.data.status
        for ev in events
        if isinstance(ev, NodeStatusEvent) and ev.data.node_id == "blocked_child"
    ]
    assert blocked_statuses == [NodeStatus.PENDING, NodeStatus.BLOCKED]


def test_concurrency_one_never_overlaps_two_nodes(tmp_path: Path) -> None:
    """With concurrency=1, at most one node runs at a time and execution spans never overlap."""
    store = RunStore(tmp_path)
    executor = FakeExecutor(default_delay=0.025)
    scheduler = Scheduler(store, executor)

    state = asyncio.run(
        scheduler.run(
            _diamond_workflow(),
            options=SchedulerOptions(concurrency=1),
        )
    )
    assert state.status == RunStatus.SUCCESS
    assert executor.max_active_count == 1
    assert len(executor.executions) == 4

    spans = sorted(executor.executions, key=lambda r: r.started_at)
    for prev, curr in itertools.pairwise(spans):
        assert prev.finished_at <= curr.started_at, (
            f"Nodes {prev.node_id} and {curr.node_id} overlapped under concurrency=1"
        )


def test_checkpoint_pause_and_replay_in_scheduler(tmp_path: Path) -> None:
    """FakeExecutor checkpoint pauses in non-interactive mode and replays when answered."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "cp_test",
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
    store = RunStore(tmp_path)
    executor_pause = FakeExecutor()
    scheduler_pause = Scheduler(store, executor_pause)

    paused_state = asyncio.run(
        scheduler_pause.run(
            wf,
            options=SchedulerOptions(non_interactive=True),
        )
    )
    assert paused_state.status == RunStatus.WAITING_FOR_USER
    assert paused_state.nodes["pick"].status == NodeStatus.WAITING_FOR_USER
    assert paused_state.nodes["echo"].status == NodeStatus.PENDING
    assert len(paused_state.checkpoints) == 1
    assert paused_state.checkpoints[0].checkpoint_id == "cp_0"

    executor_ans = FakeExecutor(
        scripts={
            "pick": FakeNodeScript(
                checkpoint=CheckpointManifest(
                    checkpoint_id="cp_0",
                    question="foo or woo?",
                    options=["foo", "woo"],
                ),
                outputs=lambda ins: scalar_outputs(choice=ins.checkpoint_answers["cp_0"]),
            )
        }
    )
    scheduler_ans = Scheduler(store, executor_ans)
    done_state = asyncio.run(
        scheduler_ans.run(
            wf,
            options=SchedulerOptions(answers={"pick.cp_0": "woo"}),
        )
    )
    assert done_state.status == RunStatus.SUCCESS
    assert done_state.nodes["pick"].status == NodeStatus.SUCCESS
    assert done_state.nodes["echo"].status == NodeStatus.SUCCESS
    echo_rec = next(r for r in executor_ans.executions if r.node_id == "echo")
    assert echo_rec.inputs.inputs["text"] == ScalarValue(value="woo")
