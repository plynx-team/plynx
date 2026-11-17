"""Tests for Task 1.7: ``standard_io`` pack demo ops and end-to-end execution."""

from __future__ import annotations

import asyncio
from pathlib import Path

from plynx.api_models import NodeStatus, RunStatus
from plynx.engine import LocalExecutor, Scheduler, SchedulerOptions
from plynx.store import RunStore
from plynx.workflow.models import Workflow, load_workflow
from plynx_sdk.protocol import OutputsManifest, ResultManifest, ScalarValue

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"


def test_foo_or_woo_runs_end_to_end_with_real_child_processes(tmp_path: Path) -> None:
    """examples/workflows/foo_or_woo.yaml runs end to end with real child processes and uv.lock."""
    assert (ROOT / "uv.lock").is_file()

    wf = load_workflow(EXAMPLE_WORKFLOW)
    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)

    state = asyncio.run(
        scheduler.run(
            wf,
            workflow_path="examples/workflows/foo_or_woo.yaml",
            workflow_bytes=EXAMPLE_WORKFLOW.read_bytes(),
            options=SchedulerOptions(answers={"pick.cp_0": "woo"}),
        )
    )
    assert state.status == RunStatus.SUCCESS
    assert state.nodes["pick"].status == NodeStatus.SUCCESS
    assert state.nodes["echo"].status == NodeStatus.SUCCESS

    pick_outputs = OutputsManifest.from_json(
        (store.node_dir(state.id, "pick") / "outputs.json").read_text(encoding="utf-8")
    )
    assert pick_outputs.outputs == {"choice": ScalarValue(value="woo")}

    echo_result = ResultManifest.from_json(
        (store.node_dir(state.id, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert echo_result.outputs == {"text": ScalarValue(value="woo")}


def test_all_standard_io_demo_ops_pipeline(tmp_path: Path) -> None:
    """Pipeline chaining AskFooOrWoo, Concat, WriteText, ReadText, and Echo succeeds."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "all_demo_ops",
            "nodes": {
                "ask": {
                    "op": "standard_io/demo:AskFooOrWoo",
                    "inputs": {"prompt": "Choose one"},
                },
                "join": {
                    "op": "standard_io/demo:Concat",
                    "inputs": {"a": "$ask.choice", "b": "_suffix"},
                },
                "write": {
                    "op": "standard_io/demo:WriteText",
                    "inputs": {"text": "$join.text", "filename": "greeting.txt"},
                },
                "read": {
                    "op": "standard_io/demo:ReadText",
                    "inputs": {"path": "$write.file"},
                },
                "echo": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$read.text"},
                },
            },
        }
    )

    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)

    state = asyncio.run(
        scheduler.run(
            wf,
            options=SchedulerOptions(answers={"ask.cp_0": "foo"}),
        )
    )
    assert state.status == RunStatus.SUCCESS
    for nid in ("ask", "join", "write", "read", "echo"):
        assert state.nodes[nid].status == NodeStatus.SUCCESS

    write_dir = store.node_dir(state.id, "write")
    written_file = write_dir / "workdir" / "greeting.txt"
    assert written_file.is_file()
    assert written_file.read_text(encoding="utf-8") == "foo_suffix"

    echo_result = ResultManifest.from_json(
        (store.node_dir(state.id, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert echo_result.outputs == {"text": ScalarValue(value="foo_suffix")}
