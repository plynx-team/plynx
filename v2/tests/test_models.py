"""Tests for ``plynx.workflow.models`` and ``plynx.api_models``."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from plynx.api_models import (
    CheckpointResolvedEvent,
    NodeCheckpointEvent,
    NodeLogEvent,
    NodeStatus,
    NodeStatusEvent,
    RunEvent,
    RunState,
    RunStatus,
    RunStatusEvent,
    StageApprovalEvent,
    StageGateStatus,
    StageResolvedEvent,
)
from plynx.workflow.models import (
    NodeRef,
    Stage,
    Workflow,
    load_workflow,
    parse_workflow_yaml,
)
from pydantic import TypeAdapter, ValidationError

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"
WORKFLOW_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "workflows"
ARCH_DOC = ROOT / "docs" / "ARCHITECTURE.md"


def test_example_workflow_parses() -> None:
    """The example workflow examples/workflows/foo_or_woo.yaml parses into a Workflow model."""
    wf = load_workflow(EXAMPLE_WORKFLOW)
    assert wf.version == 1
    assert wf.name == "foo_or_woo"
    assert wf.concurrency == 4
    assert list(wf.stages.keys()) == ["ask", "print"]
    assert wf.stages["ask"] == Stage(title="1. Ask", require_approval=False)
    assert wf.stages["print"] == Stage(title="print", require_approval=False)

    assert set(wf.nodes.keys()) == {"pick", "echo", "concat"}
    assert wf.nodes["pick"].op == "standard_io/demo:AskFooOrWoo"
    assert wf.nodes["pick"].title == "Pick one"
    assert wf.nodes["pick"].stage == "ask"
    assert wf.nodes["pick"].inputs == {"prompt": "foo or woo?"}

    assert wf.nodes["echo"].op == "standard_io/demo:Echo"
    assert wf.nodes["echo"].stage == "print"
    assert wf.nodes["echo"].inputs == {"text": NodeRef(from_node="pick", output="choice")}

    assert wf.nodes["concat"].op == "standard_io/text:Concat"


def test_escaped_dollar_and_mapping_reference_fixture() -> None:
    """$$ escapes a literal leading $ and {from_node, output} parses as NodeRef."""
    wf = load_workflow(WORKFLOW_FIXTURES / "escaped_dollar.yaml")
    inputs = wf.nodes["echo"].inputs
    assert inputs["price"] == "$100"
    assert inputs["not_ref"] == "$pick.choice"
    assert inputs["single_dollar"] == "$"
    assert inputs["mapping_ref"] == NodeRef(from_node="pick", output="choice")
    assert wf.stages == {"main": Stage(title="Workflow", require_approval=False)}


@pytest.mark.parametrize(
    ("fixture_name", "expected_substring"),
    [
        ("invalid_unknown_top_key.yaml", "coordinates"),
        ("invalid_unknown_node_key.yaml", "x"),
        ("invalid_bare_dollar.yaml", "$bare_string"),
        ("invalid_node_id.yaml", "BadNode_1"),
    ],
)
def test_invalid_workflow_fixtures_fail_with_clear_messages(
    fixture_name: str,
    expected_substring: str,
) -> None:
    """Fixtures for unknown keys, bare $ strings, and bad node IDs fail with clear messages."""
    with pytest.raises(ValidationError) as exc_info:
        load_workflow(WORKFLOW_FIXTURES / fixture_name)
    assert expected_substring in str(exc_info.value)


@pytest.mark.parametrize(
    "bad_dollar",
    [
        "$",
        "$pick",
        "$pick.",
        "$.choice",
        "$pick.choice.extra",
        "$BadNode.choice",
        "$1node.choice",
        "$pick.1bad",
        "$hello world",
    ],
)
def test_bare_dollar_strings_rejected(bad_dollar: str) -> None:
    """Strings starting with a single $ that are not $<node_id>.<output> fail clearly."""
    with pytest.raises(ValidationError) as exc_info:
        Workflow.model_validate(
            {
                "version": 1,
                "nodes": {
                    "echo": {
                        "op": "standard_io/demo:Echo",
                        "inputs": {"text": bad_dollar},
                    }
                },
            }
        )
    assert "Invalid '$' reference" in str(exc_info.value)


@pytest.mark.parametrize("bad_node_id", ["", "1abc", "_abc", "Upper", "with-dash", "with space"])
def test_bad_node_ids_rejected(bad_node_id: str) -> None:
    """Node IDs not matching ^[a-z][a-z0-9_]*$ fail with a clear error message."""
    with pytest.raises(ValidationError) as exc_info:
        Workflow.model_validate(
            {
                "version": 1,
                "nodes": {
                    bad_node_id: {"op": "standard_io/demo:Echo"},
                },
            }
        )
    assert "Invalid node ID" in str(exc_info.value)


def test_default_name_from_file_stem() -> None:
    """When 'name' is omitted in YAML, load_workflow defaults it to the file stem."""
    wf = parse_workflow_yaml(
        "version: 1\nnodes:\n  step_a:\n    op: standard_io/demo:Echo\n",
        default_name="my_stem",
    )
    assert wf.name == "my_stem"


def test_statuses_match_architecture_md_exactly() -> None:
    """NodeStatus and RunStatus match the Statuses table in ARCHITECTURE.md."""
    arch = ARCH_DOC.read_text(encoding="utf-8")
    sec_start = arch.index("## Statuses (single source)")
    sec_end = arch.index("## Non-goals", sec_start)
    sec = arch[sec_start:sec_end]

    node_line = next(line for line in sec.splitlines() if line.startswith("| Node |"))
    run_line = next(line for line in sec.splitlines() if line.startswith("| Run |"))

    doc_node_statuses = re.findall(r"`([A-Z_]+)`", node_line)
    doc_run_statuses = re.findall(r"`([A-Z_]+)`", run_line)

    assert [s.value for s in NodeStatus] == doc_node_statuses
    assert [s.value for s in RunStatus] == doc_run_statuses


def test_seven_event_types_tagged_union() -> None:
    """All seven event types parse through the RunEvent discriminated union."""
    adapter: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)
    samples: list[tuple[dict[str, object], type[object]]] = [
        (
            {
                "seq": 1,
                "ts": 100.0,
                "type": "run_status",
                "data": {"run_id": "r1", "status": "RUNNING"},
            },
            RunStatusEvent,
        ),
        (
            {
                "seq": 2,
                "ts": 101.0,
                "type": "node_status",
                "data": {
                    "run_id": "r1",
                    "node_id": "pick",
                    "status": "RUNNING",
                    "cache_hit": False,
                    "attempt": 1,
                },
            },
            NodeStatusEvent,
        ),
        (
            {
                "seq": 3,
                "ts": 102.0,
                "type": "node_checkpoint",
                "data": {
                    "run_id": "r1",
                    "node_id": "pick",
                    "checkpoint_id": "cp_0",
                    "question": "foo or woo?",
                    "options": ["foo", "woo"],
                    "allow_freeform": False,
                },
            },
            NodeCheckpointEvent,
        ),
        (
            {
                "seq": 4,
                "ts": 103.0,
                "type": "checkpoint_resolved",
                "data": {"run_id": "r1", "node_id": "pick", "checkpoint_id": "cp_0"},
            },
            CheckpointResolvedEvent,
        ),
        (
            {
                "seq": 5,
                "ts": 104.0,
                "type": "stage_approval",
                "data": {"run_id": "r1", "stage_id": "ask", "title": "1. Ask"},
            },
            StageApprovalEvent,
        ),
        (
            {
                "seq": 6,
                "ts": 105.0,
                "type": "stage_resolved",
                "data": {"run_id": "r1", "stage_id": "ask"},
            },
            StageResolvedEvent,
        ),
        (
            {
                "ts": 106.0,
                "type": "node_log",
                "data": {
                    "run_id": "r1",
                    "node_id": "pick",
                    "stream": "stdout",
                    "offset": 0,
                    "lines": ["hello"],
                },
            },
            NodeLogEvent,
        ),
    ]
    for raw, expected_cls in samples:
        parsed = adapter.validate_python(raw)
        assert isinstance(parsed, expected_cls)


def test_run_state_round_trip() -> None:
    """RunState validates and round-trips with nodes, checkpoints, and stage gates."""
    state = RunState.model_validate(
        {
            "id": "20261116_201500_a1b2c3",
            "workflow_path": "workflows/foo_or_woo.yaml",
            "workflow_sha256": "deadbeef",
            "status": "WAITING_FOR_USER",
            "run_inputs": {},
            "owner_pid": 12345,
            "cancel_requested": False,
            "pinned": False,
            "created_at": 100.0,
            "started_at": 101.0,
            "nodes": {
                "pick": {
                    "node_id": "pick",
                    "status": "WAITING_FOR_USER",
                    "cache_hit": False,
                    "attempt": 1,
                }
            },
            "checkpoints": [
                {
                    "node_id": "pick",
                    "checkpoint_id": "cp_0",
                    "question": "foo or woo?",
                    "options": ["foo", "woo"],
                    "allow_freeform": False,
                    "created_at": 102.0,
                }
            ],
            "stage_gates": {
                "ask": {
                    "stage_id": "ask",
                    "status": "WAITING",
                    "created_at": 103.0,
                }
            },
        }
    )
    assert state.status == RunStatus.WAITING_FOR_USER
    assert state.nodes["pick"].status == NodeStatus.WAITING_FOR_USER
    assert state.stage_gates["ask"].status == StageGateStatus.WAITING
    assert RunState.model_validate_json(state.model_dump_json()) == state
