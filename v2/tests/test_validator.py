"""Tests for ``plynx.registry``, ``plynx.workflow.validator``, and ``plynx validate``."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec
from plynx.cli import main as cli_main
from plynx.registry import FakeRegistry, OpRegistry
from plynx.workflow.models import Workflow
from plynx.workflow.validator import validate_workflow, validate_workflow_file

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"
VALIDATOR_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "validator"


def test_fake_registry_satisfies_protocol() -> None:
    """FakeRegistry implements OpRegistry and supports get/list_ops/register."""
    reg = FakeRegistry()
    assert isinstance(reg, OpRegistry)
    assert reg.get("standard_io/demo:AskFooOrWoo") is not None
    assert reg.get("standard_io/demo:Echo") is not None
    assert reg.get("unknown/mod:Missing") is None
    ids = [op.id for op in reg.list_ops()]
    assert ids == sorted(ids)


def test_cli_validate_example_workflow_exits_0() -> None:
    """plynx validate examples/workflows/foo_or_woo.yaml exits 0."""
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(EXAMPLE_WORKFLOW)])
    assert result.exit_code == 0, result.output
    assert "OK:" in result.output
    assert validate_workflow_file(EXAMPLE_WORKFLOW) == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_node_ids", "expected_keyword"),
    [
        ("unknown_op.yaml", ("bad_op_node",), "unknown op"),
        ("missing_node_ref.yaml", ("echo_missing",), "missing node"),
        ("unknown_output.yaml", ("echo_bad_out",), "unknown output"),
        ("cycle.yaml", ("node_a", "node_b"), "cycle"),
        ("backward_stage_edge.yaml", ("early_node",), "backward stage edge"),
        ("port_type_mismatch.yaml", ("reader",), "port type mismatch"),
    ],
)
def test_cli_validate_error_fixtures_exit_1_and_name_node(
    fixture_name: str,
    expected_node_ids: tuple[str, ...],
    expected_keyword: str,
) -> None:
    """One fixture per error kind exits 1 with the message naming the node."""
    fixture_path = VALIDATOR_FIXTURES / fixture_name
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(fixture_path)])
    assert result.exit_code == 1
    assert expected_keyword in result.output
    assert any(node_id in result.output for node_id in expected_node_ids)

    issues = validate_workflow_file(fixture_path)
    assert issues
    assert any(issue.node_id in expected_node_ids for issue in issues)


def test_file_media_compatibility() -> None:
    """A file port with media accepts the same media or null, and rejects different media."""
    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="test/io:ProduceText",
                pack="test",
                module="io",
                name="ProduceText",
                kind="class",
                title="Produce text",
                outputs=[OutputPortSpec(name="out", type="file", media="text/plain")],
                source="test/io.py",
            ),
            OpEntry(
                id="test/io:ProduceGenericFile",
                pack="test",
                module="io",
                name="ProduceGenericFile",
                kind="class",
                title="Produce generic file",
                outputs=[OutputPortSpec(name="out", type="file", media=None)],
                source="test/io.py",
            ),
            OpEntry(
                id="test/io:ConsumePdf",
                pack="test",
                module="io",
                name="ConsumePdf",
                kind="class",
                title="Consume PDF",
                inputs=[InputPortSpec(name="doc", type="file", media="application/pdf")],
                outputs=[],
                source="test/io.py",
            ),
        ]
    )

    bad_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "prod": {"op": "test/io:ProduceText"},
                "cons": {"op": "test/io:ConsumePdf", "inputs": {"doc": "$prod.out"}},
            },
        }
    )
    bad_issues = validate_workflow(bad_wf, reg)
    assert len(bad_issues) == 1
    assert bad_issues[0].node_id == "cons"
    assert "media mismatch" in bad_issues[0].message

    ok_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "prod": {"op": "test/io:ProduceGenericFile"},
                "cons": {"op": "test/io:ConsumePdf", "inputs": {"doc": "$prod.out"}},
            },
        }
    )
    assert validate_workflow(ok_wf, reg) == []
