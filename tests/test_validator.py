"""Tests for ``plynx.registry``, ``plynx.workflow.validator``, and ``plynx validate``."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec
from plynx.cli import main as cli_main
from plynx.registry import OpRegistry
from plynx.workflow.models import Workflow, load_workflow
from plynx.workflow.validator import validate_workflow, validate_workflow_file

from tests.fakes import FakeRegistry

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


def test_ports_subtype_compatibility() -> None:
    """Int to float is accepted; incompatible types are rejected."""
    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="test/math:ProduceInt",
                pack="test",
                module="math",
                name="ProduceInt",
                kind="class",
                title="Produce int",
                outputs=[OutputPortSpec(name="n", type="int")],
                source="test/math.py",
            ),
            OpEntry(
                id="test/math:ConsumeFloat",
                pack="test",
                module="math",
                name="ConsumeFloat",
                kind="class",
                title="Consume float",
                inputs=[InputPortSpec(name="val", type="float")],
                outputs=[],
                source="test/math.py",
            ),
            OpEntry(
                id="test/math:ConsumeInt",
                pack="test",
                module="math",
                name="ConsumeInt",
                kind="class",
                title="Consume int",
                inputs=[InputPortSpec(name="val", type="int")],
                outputs=[],
                source="test/math.py",
            ),
            OpEntry(
                id="test/math:ProduceStr",
                pack="test",
                module="math",
                name="ProduceStr",
                kind="class",
                title="Produce str",
                outputs=[OutputPortSpec(name="s", type="str")],
                source="test/math.py",
            ),
        ]
    )

    # int -> float is valid subtype
    ok_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "prod": {"op": "test/math:ProduceInt"},
                "cons": {"op": "test/math:ConsumeFloat", "inputs": {"val": "$prod.n"}},
            },
        }
    )
    assert validate_workflow(ok_wf, reg) == []

    # str -> int is invalid
    bad_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "prod": {"op": "test/math:ProduceStr"},
                "cons": {"op": "test/math:ConsumeInt", "inputs": {"val": "$prod.s"}},
            },
        }
    )
    issues = validate_workflow(bad_wf, reg)
    assert len(issues) == 1
    assert "port type mismatch: expected 'int', got 'str'" in issues[0].message


def test_literal_options_and_range_constraints() -> None:
    """Literal choices and Range bounds are validated when input is a constant."""
    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="test/demo:ConfigOp",
                pack="test",
                module="demo",
                name="ConfigOp",
                kind="class",
                title="Config Op",
                inputs=[
                    InputPortSpec(
                        name="mode",
                        type="str",
                        options=["fast", "accurate"],
                        required=True,
                    ),
                    InputPortSpec(
                        name="count",
                        type="int",
                        min=1,
                        max=10,
                        required=True,
                    ),
                    InputPortSpec(
                        name="optional_note",
                        type="str",
                        required=False,
                        default=None,
                    ),
                ],
                outputs=[],
                source="test/demo.py",
            ),
        ]
    )

    # Valid literal options and range
    ok_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "cfg": {
                    "op": "test/demo:ConfigOp",
                    "inputs": {"mode": "fast", "count": 5, "optional_note": None},
                },
            },
        }
    )
    assert validate_workflow(ok_wf, reg) == []

    # Invalid option choice
    bad_mode_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "cfg": {
                    "op": "test/demo:ConfigOp",
                    "inputs": {"mode": "turbo", "count": 5},
                },
            },
        }
    )
    issues = validate_workflow(bad_mode_wf, reg)
    assert any("not in allowed options" in issue.message for issue in issues)

    # Below range min
    bad_min_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "cfg": {
                    "op": "test/demo:ConfigOp",
                    "inputs": {"mode": "fast", "count": 0},
                },
            },
        }
    )
    issues = validate_workflow(bad_min_wf, reg)
    assert any("less than minimum 1" in issue.message for issue in issues)

    # Above range max
    bad_max_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "cfg": {
                    "op": "test/demo:ConfigOp",
                    "inputs": {"mode": "fast", "count": 99},
                },
            },
        }
    )
    issues = validate_workflow(bad_max_wf, reg)
    assert any("greater than maximum 10" in issue.message for issue in issues)

    # Required port set to null is rejected
    null_req_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "cfg": {
                    "op": "test/demo:ConfigOp",
                    "inputs": {"mode": None, "count": 5},
                },
            },
        }
    )
    issues = validate_workflow(null_req_wf, reg)
    assert any("cannot be null" in issue.message for issue in issues)


def test_unbound_run_inputs_and_get_unbound_run_inputs() -> None:
    """Missing required input with no default is surfaced as unbound warning and in helper."""
    from plynx.workflow.validator import get_unbound_run_inputs

    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="test/op:Echo",
                pack="test",
                module="op",
                name="Echo",
                kind="class",
                title="Echo",
                inputs=[
                    InputPortSpec(name="text", type="str", required=True, default=None),
                    InputPortSpec(name="opt", type="str", required=False, default="def"),
                ],
                outputs=[],
                source="test/op.py",
            ),
        ]
    )

    wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "echo_node": {"op": "test/op:Echo", "inputs": {}},
            },
        }
    )

    # Statically: surfaces as warning
    issues = validate_workflow(wf, reg)
    warnings = [i for i in issues if i.severity == "warning"]
    assert len(warnings) == 1
    assert "unbound run input 'text'" in warnings[0].message
    assert warnings[0].node_id == "echo_node"

    # get_unbound_run_inputs returns structured list for UI
    unbound = get_unbound_run_inputs(wf, reg)
    assert len(unbound) == 1
    assert unbound[0].node_id == "echo_node"
    assert unbound[0].name == "text"
    assert unbound[0].type == "str"
    assert unbound[0].required is True
    assert unbound[0].default is None

    # When supplied via run_inputs, the warning is suppressed
    issues_with_inputs = validate_workflow(wf, reg, run_inputs={"echo_node.text": "hello"})
    assert not any(i.severity == "warning" for i in issues_with_inputs)


def test_missing_uv_lock_warning(tmp_path: Path) -> None:
    """A warning is emitted if a discovered pack used in the workflow lacks uv.lock."""
    pack_dir = tmp_path / "custom_pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pyproject.toml").write_text("[project]\nname='custom_pack'\n", encoding="utf-8")
    # Note: no uv.lock created

    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="custom_pack/op:Run",
                pack="custom_pack",
                module="op",
                name="Run",
                kind="class",
                title="Run",
                inputs=[],
                outputs=[],
                source="custom_pack/op.py",
            )
        ],
        discovered_packs={"custom_pack": pack_dir},
    )

    wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "n1": {"op": "custom_pack/op:Run", "inputs": {}},
            },
        }
    )

    issues = validate_workflow(wf, reg)
    uv_warnings = [i for i in issues if i.severity == "warning" and "uv.lock" in i.message]
    assert len(uv_warnings) == 1
    assert "Pack 'custom_pack' is missing 'uv.lock'" in uv_warnings[0].message

    # Now create uv.lock -> warning disappears
    (pack_dir / "uv.lock").write_text("", encoding="utf-8")
    issues_after = validate_workflow(wf, reg)
    uv_warnings_after = [i for i in issues_after if "uv.lock" in i.message]
    assert len(uv_warnings_after) == 0


def test_direct_builtin_pack_standard_io_has_no_uv_lock_warning() -> None:
    """Built-in stdlib-only standard_io does not require uv.lock and emits no warning."""
    from plynx.registry import PackRegistry

    reg = PackRegistry(ROOT)
    wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "echo": {"op": "standard_io/demo:Echo", "inputs": {"text": "hello"}},
            },
        }
    )
    issues = validate_workflow(wf, reg)
    assert issues == []


def test_validate_diamond_against_real_registry() -> None:
    """Diamond workflow validates cleanly against the real Registry."""
    from plynx.registry import PackRegistry

    reg = PackRegistry(ROOT)
    diamond_wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "diamond",
            "nodes": {
                "root": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "seed"},
                },
                "left": {
                    "op": "standard_io/text:Concat",
                    "inputs": {"a": "$root.text", "b": "_L"},
                },
                "right": {
                    "op": "standard_io/text:Concat",
                    "inputs": {"a": "$root.text", "b": "_R"},
                },
                "join": {
                    "op": "standard_io/text:Concat",
                    "inputs": {"a": "$left.text", "b": "$right.text"},
                },
            },
        }
    )
    issues = validate_workflow(diamond_wf, reg)
    assert issues == []


def test_get_workflow_inputs_endpoint(tmp_path: Path) -> None:
    """GET /workflows/{path}/inputs returns unbound run inputs."""
    import asyncio

    import httpx
    from plynx.server import create_app

    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "unbound.yaml"
    wf_path.write_text(
        """version: 1
name: unbound
nodes:
  echo_node:
    op: standard_io/demo:Echo
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path)

    async def _check() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/workflows/workflows/unbound.yaml/inputs")
            assert resp.status_code == 200
            inputs = resp.json()
            assert len(inputs) == 1
            assert inputs[0]["node_id"] == "echo_node"
            assert inputs[0]["name"] == "text"
            assert inputs[0]["required"] is True

    asyncio.run(_check())


def test_all_curated_showcase_workflows_validate() -> None:
    """Verify all workflows in examples/workflows/ validate with zero errors."""
    from plynx.registry.pack_registry import PackRegistry

    reg = PackRegistry(ROOT)
    workflows_dir = ROOT / "examples" / "workflows"
    assert workflows_dir.is_dir()

    curated = [
        "bach_prelude_c_major.yaml",
        "data_bundle_pipeline.yaml",
        "foo_or_woo.yaml",
        "generative_art_studio.yaml",
        "interactive_wizard_staged.yaml",
        "midi_groove_studio.yaml",
        "podcast_producer_macos.yaml",
    ]

    for name in curated:
        wf_path = workflows_dir / name
        assert wf_path.is_file(), f"Missing expected workflow: {name}"
        wf = load_workflow(wf_path)
        issues = validate_workflow(wf, reg)
        errors = [issue for issue in issues if issue.severity == "error"]
        assert not errors, f"Workflow {name} had validation errors: {errors}"


def test_validator_side_effects_write_checks() -> None:
    """Validator errors on cached WRITE ops and warns on unguarded or post-gate-unapproved WRITE nodes."""
    from plynx_sdk.protocol import SideEffect

    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="ext/ops:PurePrep",
                pack="ext",
                module="ops",
                name="PurePrep",
                kind="class",
                title="Pure Prep",
                cacheable=True,
                side_effects=SideEffect.NONE,
                inputs=[InputPortSpec(name="raw", type="str", required=False, default="hi")],
                outputs=[OutputPortSpec(name="text", type="str")],
                source="ext/ops.py",
            ),
            OpEntry(
                id="ext/ops:AgentDraft",
                pack="ext",
                module="ops",
                name="AgentDraft",
                kind="class",
                agent_role="agent",
                title="Agent Draft",
                cacheable=True,
                side_effects=SideEffect.READ,
                inputs=[InputPortSpec(name="topic", type="str")],
                outputs=[OutputPortSpec(name="body", type="str")],
                source="ext/ops.py",
            ),
            OpEntry(
                id="ext/ops:SendEmail",
                pack="ext",
                module="ops",
                name="SendEmail",
                kind="class",
                title="Send Email",
                cacheable=False,
                side_effects=SideEffect.WRITE,
                inputs=[InputPortSpec(name="body", type="str")],
                outputs=[OutputPortSpec(name="sent", type="bool")],
                source="ext/ops.py",
            ),
            OpEntry(
                id="ext/ops:BrokenCachedWrite",
                pack="ext",
                module="ops",
                name="BrokenCachedWrite",
                kind="class",
                title="Broken Cached Write",
                cacheable=True,
                side_effects=SideEffect.WRITE,
                inputs=[],
                outputs=[OutputPortSpec(name="ok", type="bool")],
                source="ext/ops.py",
            ),
        ]
    )

    # 1. Contradictory WRITE + cacheable=True -> severity='error'
    bad_cached_wf = Workflow.model_validate(
        {
            "version": 1,
            "stages": {
                "s1": {"require_approval": True},
                "s2": {"require_approval": False},
            },
            "nodes": {
                "prep": {"op": "ext/ops:PurePrep", "stage": "s1"},
                "bad": {"op": "ext/ops:BrokenCachedWrite", "stage": "s2"},
            },
        }
    )
    bad_issues = validate_workflow(bad_cached_wf, reg)
    assert any(
        i.severity == "error" and i.node_id == "bad" and "cacheable=False" in i.message
        for i in bad_issues
    )

    # 2. Unguarded single-stage WRITE -> severity='warning' (not error)
    unguarded_wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "prep": {"op": "ext/ops:PurePrep"},
                "send": {"op": "ext/ops:SendEmail", "inputs": {"body": "$prep.text"}},
            },
        }
    )
    unguarded_issues = validate_workflow(unguarded_wf, reg)
    assert not [i for i in unguarded_issues if i.severity == "error"]
    assert any(
        i.severity == "warning" and i.node_id == "send" and "require_approval: true" in i.message
        for i in unguarded_issues
    )

    # 3. Properly guarded WRITE (even with a pure SideEffect.NONE formatter in the final stage) -> zero warnings
    guarded_wf = Workflow.model_validate(
        {
            "version": 1,
            "stages": {
                "draft": {"require_approval": True},
                "deliver": {"require_approval": False},
            },
            "nodes": {
                "draft_msg": {
                    "op": "ext/ops:AgentDraft",
                    "stage": "draft",
                    "inputs": {"topic": "Q3 update"},
                },
                "format_msg": {
                    "op": "ext/ops:PurePrep",
                    "stage": "deliver",
                    "inputs": {"raw": "$draft_msg.body"},
                },
                "send": {
                    "op": "ext/ops:SendEmail",
                    "stage": "deliver",
                    "inputs": {"body": "$format_msg.text"},
                },
            },
        }
    )
    assert validate_workflow(guarded_wf, reg) == []

    # 4. Early Stage 1 approval followed by unapproved Stage 2 AgentDraft feeding Stage 3 SendEmail -> warning
    stale_gate_wf = Workflow.model_validate(
        {
            "version": 1,
            "stages": {
                "intake": {"require_approval": True},
                "draft": {"require_approval": False},
                "deliver": {"require_approval": False},
            },
            "nodes": {
                "prep": {"op": "ext/ops:PurePrep", "stage": "intake"},
                "draft_msg": {
                    "op": "ext/ops:AgentDraft",
                    "stage": "draft",
                    "inputs": {"topic": "$prep.text"},
                },
                "send": {
                    "op": "ext/ops:SendEmail",
                    "stage": "deliver",
                    "inputs": {"body": "$draft_msg.body"},
                },
            },
        }
    )
    stale_issues = validate_workflow(stale_gate_wf, reg)
    assert any(
        i.severity == "warning" and i.node_id == "send" and "'draft_msg'" in i.message
        for i in stale_issues
    )
