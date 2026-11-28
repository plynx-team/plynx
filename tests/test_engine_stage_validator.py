"""Tests for Phase 4 (FEAT-AGT-3):
- StageValidatorSpec & NodeSpec.allow_graph_edits static validation
- Bounded snapshot mutation guardrails (PENDING-only, Lineage Preservation, max_injected_nodes, ruamel round-trip)
- 2-tier Stage Validator scheduling (0ms happy-path skip, 100% cache-hit skip, warning trigger, failure interception)
- GraphEditPolicy (FORBIDDEN, CONFIRM with Approve/Reject, AUTO) on StageValidatorOp and AgentOp
- Failed-node repair (both retry-via-rewire and fallback bypass via meta.superseded_by)
- Outer coding agent workflow.snapshot.yaml edit + `plynx resume` validation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.api_models import NodeStatus, RunStatus
from plynx.cli import main as cli_main
from plynx.registry import PackRegistry
from plynx.store import RunStore
from plynx.workflow.models import (
    NodeSpec,
    Workflow,
    parse_workflow_yaml,
    stage_validator_node_id,
)
from plynx.workflow.mutation import (
    prepare_and_validate_patch,
    validate_snapshot_mutation,
)
from plynx.workflow.validator import validate_workflow
from plynx_sdk.protocol import (
    GraphEditPolicy,
    GraphPatchPayload,
    ResultManifest,
    ScalarValue,
)


def _create_phase4_pack(workspace: Path) -> Path:
    """Create a stdlib-only custom pack for Phase 4 Stage Validator & mutation tests."""
    pack_dir = workspace / "custom_packs" / "phase4_ops"
    src_dir = pack_dir / "src" / "phase4_ops"
    src_dir.mkdir(parents=True, exist_ok=True)
    sdk_root = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk"
    (pack_dir / "pyproject.toml").write_text(
        '[project]\nname = "phase4-ops"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["plynx-sdk"]\n\n'
        "[tool.uv.sources]\n"
        f'plynx-sdk = {{ path = "{sdk_root.as_posix()}", editable = true }}\n\n'
        "[build-system]\n"
        'requires = ["uv_build>=0.9.0,<0.10"]\n'
        'build-backend = "uv_build"\n\n'
        "[tool.uv.build-backend]\n"
        'module-name = "phase4_ops"\n',
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(
        "from typing import Any, TypedDict\n"
        "from plynx_sdk import (\n"
        "    AgentOp,\n"
        "    AgentProviderLiteral,\n"
        "    GraphEditPolicy,\n"
        "    MarkdownFile,\n"
        "    Op,\n"
        "    SideEffect,\n"
        "    StageValidatorOp,\n"
        ")\n\n"
        "class IngestDoc(Op):\n"
        '    """Emit text and optionally warn or fail."""\n'
        '    TITLE = "Ingest Doc"\n\n'
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(\n"
        "        self,\n"
        "        raw_text: str,\n"
        "        emit_warning: str = '',\n"
        "        fail_unless_clean: bool = False,\n"
        "    ) -> Outputs:\n"
        "        print(f'ingesting: {raw_text}')\n"
        "        if fail_unless_clean and 'BAD' in raw_text:\n"
        "            raise RuntimeError('Corrupt token BAD encountered')\n"
        "        if emit_warning:\n"
        "            self.warn(emit_warning)\n"
        "        return {'text': raw_text}\n\n"
        "class TranslateFr(Op):\n"
        '    """Translate French marker to English."""\n'
        '    TITLE = "Translate French"\n\n'
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(self, text: str) -> Outputs:\n"
        "        return {'text': text.replace('Bonjour', 'Hello')}\n\n"
        "class SanitizeText(Op):\n"
        '    """Strip BAD marker from raw text."""\n'
        '    TITLE = "Sanitize Text"\n\n'
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(self, text: str) -> Outputs:\n"
        "        return {'text': text.replace('BAD:', '').strip()}\n\n"
        "class FallbackExtract(Op):\n"
        '    """Fallback extractor consuming raw upstream output."""\n'
        '    TITLE = "Fallback Extract"\n\n'
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(self, text: str) -> Outputs:\n"
        "        return {'text': f'FALLBACK({text})'}\n\n"
        "class SummarizeText(Op):\n"
        '    """Downstream consumer producing final summary."""\n'
        '    TITLE = "Summarize Text"\n\n'
        "    class Outputs(TypedDict):\n"
        "        summary: str\n\n"
        "    def run(self, text: str) -> Outputs:\n"
        "        return {'summary': f'SUMMARY: {text}'}\n\n"
        "class MergePair(Op):\n"
        '    """N-to-1 aggregator op."""\n'
        '    TITLE = "Merge Pair"\n\n'
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(self, left: str, right: str) -> Outputs:\n"
        "        return {'text': f'{left}+{right}'}\n\n"
        "class VariadicCollector(Op):\n"
        '    """Variadic op accepting extra inputs."""\n'
        '    TITLE = "Variadic Collector"\n'
        "    ALLOW_EXTRA_INPUTS = True\n\n"
        "    class Outputs(TypedDict):\n"
        "        joined: str\n\n"
        "    def run(self, primary: str, **extra: Any) -> Outputs:\n"
        "        parts = [primary] + [str(v) for _, v in sorted(extra.items())]\n"
        "        return {'joined': '|'.join(parts)}\n\n"
        "class DemoSupervisor(StageValidatorOp):\n"
        '    """Stage supervisor driven by mock responses."""\n'
        '    TITLE = "Demo Stage Supervisor"\n\n'
        "class ExternalNotifyOp(Op):\n"
        '    """External write operation that must never auto-run via allow_graph_edits=auto."""\n'
        '    TITLE = "External Notify"\n'
        "    SIDE_EFFECTS = SideEffect.WRITE\n\n"
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(self, text: str) -> Outputs:\n"
        "        return {'text': f'SENT:{text}'}\n\n"
        "class PlannerAgent(AgentOp):\n"
        '    """Regular AgentOp that can propose graph edits when enabled."""\n'
        '    TITLE = "Planner Agent"\n'
        "    ALLOW_GRAPH_EDITS = GraphEditPolicy.FORBIDDEN\n\n"
        "    class Outputs(TypedDict):\n"
        "        text: str\n\n"
        "    def run(\n"
        "        self,\n"
        "        text: str,\n"
        "        prompt_file: MarkdownFile | None = None,\n"
        "        prompt: str = '',\n"
        "        provider: AgentProviderLiteral = 'default',\n"
        "        model: str = '',\n"
        "        **extra: Any,\n"
        "    ) -> Outputs:\n"
        "        res = self.run_agent(prompt=prompt or text, provider=provider, model=model)\n"
        "        return {'text': str(res.get('text', text))}\n",
        encoding="utf-8",
    )
    return pack_dir


def _init_workspace(tmp_path: Path) -> PackRegistry:
    _create_phase4_pack(tmp_path)
    (tmp_path / ".plynx").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workflows").mkdir(parents=True, exist_ok=True)
    (tmp_path / "plynx.yaml").write_text(
        "workflows: workflows\npacks:\n  - custom_packs\nagent:\n  provider: mock\n",
        encoding="utf-8",
    )
    return PackRegistry(tmp_path)


def test_static_validation_stage_validator_and_node_allow_graph_edits(tmp_path: Path) -> None:
    """Validate stage.validator rules, extractor defaults, and node.allow_graph_edits restrictions."""
    registry = _init_workspace(tmp_path)

    sup_entry = registry.get("phase4_ops/ops:DemoSupervisor")
    assert sup_entry is not None and sup_entry.valid is True
    assert sup_entry.agent_role == "validator"
    assert sup_entry.allow_graph_edits == GraphEditPolicy.CONFIRM

    agent_entry = registry.get("phase4_ops/ops:PlannerAgent")
    assert agent_entry is not None and agent_entry.valid is True
    assert agent_entry.agent_role == "agent"
    assert agent_entry.allow_graph_edits == GraphEditPolicy.FORBIDDEN

    # 1. Valid workflow with stage validator + AgentOp allow_graph_edits
    valid_wf = parse_workflow_yaml(
        b"version: 1\n"
        b"name: valid_p4\n"
        b"stages:\n"
        b"  s1:\n"
        b"    title: Stage 1\n"
        b"    validator:\n"
        b"      op: phase4_ops/ops:DemoSupervisor\n"
        b"      mode: on_anomaly\n"
        b"      allow_graph_edits: confirm\n"
        b"      inputs:\n"
        b"        prompt: Check anomalies\n"
        b"  s2:\n"
        b"    title: Stage 2\n"
        b"nodes:\n"
        b"  plan:\n"
        b"    op: phase4_ops/ops:PlannerAgent\n"
        b"    stage: s1\n"
        b"    allow_graph_edits: auto\n"
        b"    inputs:\n"
        b"      text: hello\n"
        b"  sum:\n"
        b"    op: phase4_ops/ops:SummarizeText\n"
        b"    stage: s2\n"
        b"    inputs:\n"
        b"      text: $plan.text\n"
    )
    issues_ok = validate_workflow(valid_wf, registry)
    errors_ok = [i for i in issues_ok if i.severity == "error"]
    assert errors_ok == []

    # 2. Reject deterministic Op used as stage.validator
    bad_val_wf = parse_workflow_yaml(
        b"version: 1\n"
        b"name: bad_val\n"
        b"stages:\n"
        b"  s1:\n"
        b"    validator:\n"
        b"      op: phase4_ops/ops:TranslateFr\n"
        b"nodes:\n"
        b"  ingest:\n"
        b"    op: phase4_ops/ops:IngestDoc\n"
        b"    stage: s1\n"
        b"    inputs:\n"
        b"      raw_text: hi\n"
    )
    issues_bad_val = validate_workflow(bad_val_wf, registry)
    assert any(i.severity == "error" and "StageValidatorOp" in i.message for i in issues_bad_val)

    # 3. Reject allow_graph_edits on non-AgentOp node
    bad_node_policy_wf = parse_workflow_yaml(
        b"version: 1\n"
        b"name: bad_policy\n"
        b"nodes:\n"
        b"  ingest:\n"
        b"    op: phase4_ops/ops:IngestDoc\n"
        b"    allow_graph_edits: auto\n"
        b"    inputs:\n"
        b"      raw_text: hi\n"
    )
    issues_bad_policy = validate_workflow(bad_node_policy_wf, registry)
    assert any(
        i.severity == "error" and "allow_graph_edits" in i.message for i in issues_bad_policy
    )


def test_patch_guardrails_lineage_immutability_budget_and_yaml_comments(tmp_path: Path) -> None:
    """Verify all 4 snapshot mutation guardrails and ruamel.yaml comment preservation."""
    registry = _init_workspace(tmp_path)

    raw_yaml = (
        b"# Top-level workflow comment\n"
        b"version: 1\n"
        b"name: guardrail_test\n"
        b"stages:\n"
        b"  s1:\n"
        b"    title: Ingest\n"
        b"  s2:\n"
        b"    title: Summarize\n"
        b"nodes:\n"
        b"  # Keep this node comment intact\n"
        b"  u1:\n"
        b"    op: phase4_ops/ops:IngestDoc\n"
        b"    stage: s1\n"
        b"    inputs:\n"
        b"      raw_text: Bonjour\n"
        b"  u2:\n"
        b"    op: phase4_ops/ops:IngestDoc\n"
        b"    stage: s1\n"
        b"    inputs:\n"
        b"      raw_text: Monde\n"
        b"  v_sum:\n"
        b"    op: phase4_ops/ops:SummarizeText\n"
        b"    stage: s2\n"
        b"    inputs:\n"
        b"      text: $u1.text\n"
        b"  v_var:\n"
        b"    op: phase4_ops/ops:VariadicCollector\n"
        b"    stage: s2\n"
        b"    inputs:\n"
        b"      primary: $u1.text\n"
    )

    old_wf = parse_workflow_yaml(raw_yaml)
    statuses = {
        "u1": NodeStatus.SUCCESS,
        "u2": NodeStatus.SUCCESS,
        "v_sum": NodeStatus.PENDING,
        "v_var": NodeStatus.PENDING,
    }

    # 1. Valid 1-to-1 splice + ruamel comment preservation + provenance meta
    patch_1to1 = GraphPatchPayload(
        reason="Translate French upstream text",
        add_nodes={
            "tr_1": {
                "op": "phase4_ops/ops:TranslateFr",
                "stage": "s1",
                "inputs": {"text": "$u1.text"},
            }
        },
        rewire_inputs={"v_sum": {"text": "$tr_1.text"}},
    )
    res1, new_bytes, new_wf = prepare_and_validate_patch(
        raw_yaml_bytes=raw_yaml,
        old_snapshot=old_wf,
        patch=patch_1to1,
        injected_by="__stage_validator__s1",
        default_stage="s1",
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=2,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res1.valid is True, res1.issues
    assert res1.added_node_ids == ["tr_1"]
    assert new_bytes is not None and new_wf is not None
    new_text = new_bytes.decode("utf-8")
    assert "# Top-level workflow comment" in new_text
    assert "# Keep this node comment intact" in new_text
    assert new_wf.nodes["tr_1"].meta is not None
    assert new_wf.nodes["tr_1"].meta.injected_by == "__stage_validator__s1"
    assert new_wf.nodes["tr_1"].meta.reason == "Translate French upstream text"

    # 2. Valid N-to-1 aggregator splice (u1, u2 -> agg -> v_sum)
    patch_nto1 = GraphPatchPayload(
        reason="Merge u1 and u2 before summarizing",
        add_nodes={
            "agg": {
                "op": "phase4_ops/ops:MergePair",
                "stage": "s1",
                "inputs": {"left": "$u1.text", "right": "$u2.text"},
            }
        },
        rewire_inputs={"v_sum": {"text": "$agg.text"}},
    )
    res_agg, _, _ = prepare_and_validate_patch(
        raw_yaml_bytes=raw_yaml,
        old_snapshot=old_wf,
        patch=patch_nto1,
        injected_by="__stage_validator__s1",
        default_stage="s1",
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=2,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res_agg.valid is True, res_agg.issues
    assert res_agg.added_node_ids == ["agg"]

    # 3. Valid variadic ALLOW_EXTRA_INPUTS splice on PENDING v_var
    patch_variadic = GraphPatchPayload(
        reason="Attach translated track to variadic collector",
        add_nodes={
            "extra_tr": {
                "op": "phase4_ops/ops:TranslateFr",
                "stage": "s1",
                "inputs": {"text": "$u2.text"},
            }
        },
        rewire_inputs={"v_var": {"secondary": "$extra_tr.text"}},
    )
    res_var, _, _ = prepare_and_validate_patch(
        raw_yaml_bytes=raw_yaml,
        old_snapshot=old_wf,
        patch=patch_variadic,
        injected_by="__stage_validator__s1",
        default_stage="s1",
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=2,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res_var.valid is True, res_var.issues
    assert res_var.added_node_ids == ["extra_tr"]

    # 4. Reject modifying a SUCCESS node
    bad_immutable = GraphPatchPayload(
        reason="Illegal edit to completed u1",
        add_nodes={
            "tr_bad": {
                "op": "phase4_ops/ops:TranslateFr",
                "stage": "s1",
                "inputs": {"text": "hi"},
            }
        },
        rewire_inputs={"u1": {"raw_text": "$tr_bad.text"}},
    )
    res_imm, _, _ = prepare_and_validate_patch(
        raw_yaml_bytes=raw_yaml,
        old_snapshot=old_wf,
        patch=bad_immutable,
        injected_by="__stage_validator__s1",
        default_stage="s1",
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=3,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res_imm.valid is False
    assert any("SUCCESS" in i.message for i in res_imm.issues)

    # 5. Reject Lineage Preservation violation (orphaning u1)
    bad_lineage = GraphPatchPayload(
        reason="Orphan u1 illegally",
        add_nodes={
            "orphan": {
                "op": "phase4_ops/ops:IngestDoc",
                "stage": "s1",
                "inputs": {"raw_text": "brand new unrelated input"},
            }
        },
        rewire_inputs={"v_sum": {"text": "$orphan.text"}},
    )
    res_lin, _, _ = prepare_and_validate_patch(
        raw_yaml_bytes=raw_yaml,
        old_snapshot=old_wf,
        patch=bad_lineage,
        injected_by="__stage_validator__s1",
        default_stage="s1",
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=3,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res_lin.valid is False
    assert any("Lineage violation" in i.message for i in res_lin.issues)

    # 6. Reject exceeding cumulative max_injected_nodes
    patch_over_budget = GraphPatchPayload(
        reason="Inject two nodes when max is 1",
        add_nodes={
            "step_a": {
                "op": "phase4_ops/ops:TranslateFr",
                "stage": "s1",
                "inputs": {"text": "$u1.text"},
            },
            "step_b": {
                "op": "phase4_ops/ops:TranslateFr",
                "stage": "s1",
                "inputs": {"text": "$step_a.text"},
            },
        },
        rewire_inputs={"v_sum": {"text": "$step_b.text"}},
    )
    res_budget, _, _ = prepare_and_validate_patch(
        raw_yaml_bytes=raw_yaml,
        old_snapshot=old_wf,
        patch=patch_over_budget,
        injected_by="__stage_validator__s1",
        default_stage="s1",
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=1,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res_budget.valid is False
    assert any("max_injected_nodes" in i.message for i in res_budget.issues)

    # 7. Reject deleting an existing node in direct snapshot mutation
    deleted_wf = Workflow(
        version=old_wf.version,
        name=old_wf.name,
        stages=dict(old_wf.stages),
        nodes={k: v for k, v in old_wf.nodes.items() if k != "v_var"},
    )
    res_del = validate_snapshot_mutation(
        old_snapshot=old_wf,
        new_snapshot=deleted_wf,
        registry=registry,
        node_statuses=statuses,
        max_injected_nodes=3,
        baseline_node_ids=set(old_wf.nodes.keys()),
    )
    assert res_del.valid is False
    assert any("delete" in i.message.lower() for i in res_del.issues)


def test_happy_path_skip_and_100_percent_cache_hit_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ON_ANOMALY skips in 0ms on clean stage; 100% cache hit skips even ALWAYS validator."""
    _init_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Set an INVALID mock payload so any actual subprocess spawn of DemoSupervisor would fail immediately!
    bad_mock = tmp_path / "should_never_run.json"
    bad_mock.write_text(json.dumps({"status": "BOOM_SHOULD_NOT_RUN"}), encoding="utf-8")
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(bad_mock))

    wf_on_anomaly = tmp_path / "workflows" / "happy_skip.yaml"
    wf_on_anomaly.write_text(
        "version: 1\n"
        "name: happy_skip\n"
        "stages:\n"
        "  s1:\n"
        "    title: Ingest\n"
        "    validator:\n"
        "      op: phase4_ops/ops:DemoSupervisor\n"
        "      mode: on_anomaly\n"
        "  s2:\n"
        "    title: Summarize\n"
        "nodes:\n"
        "  ingest:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: Clean English text\n"
        "  sum:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $ingest.text\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    res1 = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_on_anomaly)])
    assert res1.exit_code == 0, res1.output

    store = RunStore(tmp_path)
    run1_id = store.list_runs(limit=1)[0].id
    state1 = store.get_run_state(run1_id)
    assert state1 is not None
    val_id = stage_validator_node_id("s1")
    assert state1.nodes[val_id].status == NodeStatus.SUCCESS
    assert state1.nodes[val_id].attempt == 0

    # Run once more now that `uv.lock` exists so `ingest` is stored in CAS with the locked hash
    res1_warm = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_on_anomaly)])
    assert res1_warm.exit_code == 0, res1_warm.output

    # Switch validator mode to `always`: on next run `ingest` is 100% CAS cache hit,
    # so validator must be skipped with cache_hit=True without invoking `bad_mock`!
    wf_always_cached = tmp_path / "workflows" / "always_cached.yaml"
    wf_always_cached.write_text(
        wf_on_anomaly.read_text(encoding="utf-8").replace("mode: on_anomaly", "mode: always"),
        encoding="utf-8",
    )
    res2 = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_always_cached)])
    assert res2.exit_code == 0, res2.output
    run2_id = store.list_runs(limit=1)[0].id
    state2 = store.get_run_state(run2_id)
    assert state2 is not None
    assert state2.nodes["ingest"].cache_hit is True
    assert state2.nodes[val_id].status == NodeStatus.SUCCESS
    assert state2.nodes[val_id].cache_hit is True
    assert state2.nodes[val_id].attempt == 0


def test_warning_anomaly_confirm_approve_and_reject_flows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warning triggers validator, writes stage_context.json, pauses on CONFIRM, and handles Approve vs Reject."""
    _init_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)

    val_id = stage_validator_node_id("s1")
    mock_file = tmp_path / "mock_validator.json"
    mock_file.write_text(
        json.dumps(
            {
                val_id: {
                    "status": "propose_patch",
                    "session_id": "sup_sess_1",
                    "graph_patch": {
                        "reason": "Detected French input; splicing TranslateFr before summarize.",
                        "add_nodes": {
                            "translate_fr": {
                                "op": "phase4_ops/ops:TranslateFr",
                                "title": "Translate French",
                                "stage": "s1",
                                "inputs": {"text": "$ingest.text"},
                            }
                        },
                        "rewire_inputs": {"summarize": {"text": "$translate_fr.text"}},
                    },
                    "outputs": {"summary": "Proposed French translation splice."},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(mock_file))

    wf_yaml_text = (
        "# Original workflow file must remain untouched\n"
        "version: 1\n"
        "name: fr_pipeline\n"
        "stages:\n"
        "  s1:\n"
        "    title: 1. Ingest\n"
        "    validator:\n"
        "      op: phase4_ops/ops:DemoSupervisor\n"
        "      mode: on_anomaly\n"
        "      allow_graph_edits: confirm\n"
        "  s2:\n"
        "    title: 2. Summarize\n"
        "nodes:\n"
        "  ingest:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: Bonjour tout le monde\n"
        "      emit_warning: Detected French language (lang=fr)\n"
        "  summarize:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $ingest.text\n"
    )
    wf_file = tmp_path / "workflows" / "fr_pipeline.yaml"
    wf_file.write_text(wf_yaml_text, encoding="utf-8")

    runner = CliRunner()
    # Run 1: pauses for CONFIRM checkpoint (exit code 2)
    r_pause = runner.invoke(cli_main, ["run", "--non-interactive", "--no-cache", str(wf_file)])
    assert r_pause.exit_code == 2, r_pause.output

    store = RunStore(tmp_path)
    run_id = store.list_runs(limit=1)[0].id
    paused_state = store.get_run_state(run_id)
    assert paused_state is not None
    assert paused_state.status == RunStatus.WAITING_FOR_USER
    assert paused_state.nodes[val_id].status == NodeStatus.WAITING_FOR_USER

    # Verify stage_context.json contents
    ctx_path = store.node_dir(run_id, val_id) / "stage_context.json"
    assert ctx_path.is_file()
    stage_ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
    assert stage_ctx["stage_id"] == "s1"
    assert stage_ctx["allow_graph_edits"] == "confirm"
    assert stage_ctx["nodes"]["ingest"]["status"] == "SUCCESS"
    assert "Detected French language (lang=fr)" in stage_ctx["nodes"]["ingest"]["warnings"]
    assert stage_ctx["nodes"]["ingest"]["outputs"]["text"]["value"] == "Bonjour tout le monde"
    assert any("ingesting: Bonjour" in ln for ln in stage_ctx["nodes"]["ingest"]["stdout_tail"])
    assert any(op["id"] == "phase4_ops/ops:TranslateFr" for op in stage_ctx["registered_ops"])

    # Verify checkpoint carries options=["Approve Patch", "Reject"] and structured graph_patch
    open_cps = [
        cp for cp in paused_state.checkpoints if cp.node_id == val_id and cp.answered_at is None
    ]
    assert len(open_cps) == 1
    cp = open_cps[0]
    assert cp.options == ["Approve Patch", "Reject"]
    assert cp.graph_patch is not None
    assert "translate_fr" in cp.graph_patch.add_nodes

    # Original workflow YAML on disk is untouched
    assert wf_file.read_text(encoding="utf-8") == wf_yaml_text

    # Resume with "Approve Patch" -> applies splice to snapshot, runs translate_fr + summarize (without re-running ingest!)
    r_approve = runner.invoke(
        cli_main,
        [
            "resume",
            run_id,
            "--non-interactive",
            "--answer",
            f"{val_id}.{cp.checkpoint_id}=Approve Patch",
        ],
    )
    assert r_approve.exit_code == 0, r_approve.output

    # Original workflow YAML STILL untouched!
    assert wf_file.read_text(encoding="utf-8") == wf_yaml_text

    final_state = store.get_run_state(run_id)
    assert final_state is not None
    assert final_state.status == RunStatus.SUCCESS
    assert final_state.nodes["ingest"].attempt == 1  # Not re-executed!
    assert final_state.nodes["translate_fr"].status == NodeStatus.SUCCESS
    assert final_state.nodes["summarize"].status == NodeStatus.SUCCESS
    assert final_state.workflow_snapshot is not None
    injected_spec: NodeSpec = final_state.workflow_snapshot.nodes["translate_fr"]
    assert injected_spec.meta is not None
    assert injected_spec.meta.injected_by == val_id

    sum_res = ResultManifest.from_json(
        (store.node_dir(run_id, "summarize") / "result.json").read_bytes()
    )
    sum_val = sum_res.outputs["summary"]
    assert isinstance(sum_val, ScalarValue)
    assert sum_val.value == "SUMMARY: Hello tout le monde"

    # Run 2: Test answering "Reject" on warning-only stage -> declines patch and continues run to SUCCESS!
    r_pause2 = runner.invoke(cli_main, ["run", "--non-interactive", "--no-cache", str(wf_file)])
    assert r_pause2.exit_code == 2
    run2_id = store.list_runs(limit=1)[0].id
    state2_paused = store.get_run_state(run2_id)
    assert state2_paused is not None
    cp2 = next(
        c for c in state2_paused.checkpoints if c.node_id == val_id and c.answered_at is None
    )

    r_reject = runner.invoke(
        cli_main,
        [
            "resume",
            run2_id,
            "--non-interactive",
            "--answer",
            f"{val_id}.{cp2.checkpoint_id}=Reject",
        ],
    )
    assert r_reject.exit_code == 0, r_reject.output
    state2_final = store.get_run_state(run2_id)
    assert state2_final is not None
    assert state2_final.status == RunStatus.SUCCESS
    assert "translate_fr" not in state2_final.nodes
    sum2_res = ResultManifest.from_json(
        (store.node_dir(run2_id, "summarize") / "result.json").read_bytes()
    )
    sum2_val = sum2_res.outputs["summary"]
    assert isinstance(sum2_val, ScalarValue)
    assert sum2_val.value == "SUMMARY: Bonjour tout le monde"


def test_failure_interception_both_fallback_bypass_and_retry_rewire_plus_reject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test failed-node interception: (a) fallback bypass, (b) retry via input rewire, and (c) Reject -> FAILED."""
    _init_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    val_id = stage_validator_node_id("s1")
    runner = CliRunner()
    store = RunStore(tmp_path)

    # --- Case A: Bypass FAILED node `parse` with `fallback_parse` (allow_graph_edits: auto) ---
    wf_bypass = tmp_path / "workflows" / "bypass_repair.yaml"
    wf_bypass.write_text(
        "version: 1\n"
        "name: bypass_repair\n"
        "stages:\n"
        "  s1:\n"
        "    title: Parse\n"
        "    validator:\n"
        "      op: phase4_ops/ops:DemoSupervisor\n"
        "      mode: on_failure\n"
        "      allow_graph_edits: auto\n"
        "  s2:\n"
        "    title: Summarize\n"
        "nodes:\n"
        "  raw_src:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: 'BAD: raw payload'\n"
        "  parse:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: $raw_src.text\n"
        "      fail_unless_clean: true\n"
        "  summarize:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $parse.text\n",
        encoding="utf-8",
    )

    mock_bypass = tmp_path / "mock_bypass.json"
    mock_bypass.write_text(
        json.dumps(
            {
                val_id: {
                    "status": "propose_patch",
                    "session_id": "bypass_1",
                    "graph_patch": {
                        "reason": "parse failed on BAD token; bypassing with FallbackExtract.",
                        "add_nodes": {
                            "fallback_parse": {
                                "op": "phase4_ops/ops:FallbackExtract",
                                "stage": "s1",
                                "inputs": {"text": "$raw_src.text"},
                            }
                        },
                        "rewire_inputs": {"summarize": {"text": "$fallback_parse.text"}},
                    },
                    "outputs": {"summary": "Bypassed failed parse node with fallback_parse."},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(mock_bypass))

    res_a = runner.invoke(cli_main, ["run", "--non-interactive", "--no-cache", str(wf_bypass)])
    assert res_a.exit_code == 0, res_a.output
    run_a = store.list_runs(limit=1)[0].id
    state_a = store.get_run_state(run_a)
    assert state_a is not None
    assert state_a.status == RunStatus.SUCCESS
    assert state_a.nodes["parse"].status == NodeStatus.FAILED
    assert state_a.nodes["fallback_parse"].status == NodeStatus.SUCCESS
    assert state_a.nodes["summarize"].status == NodeStatus.SUCCESS
    assert state_a.workflow_snapshot is not None
    assert state_a.workflow_snapshot.nodes["parse"].meta is not None
    assert state_a.workflow_snapshot.nodes["parse"].meta.superseded_by == "fallback_parse"

    # --- Case B: Rewire FAILED node `parse`'s input through `sanitize` so `parse` retries to SUCCESS ---
    mock_retry = tmp_path / "mock_retry.json"
    mock_retry.write_text(
        json.dumps(
            {
                val_id: {
                    "status": "propose_patch",
                    "session_id": "retry_1",
                    "graph_patch": {
                        "reason": "Sanitize raw_src before retrying parse.",
                        "add_nodes": {
                            "sanitize": {
                                "op": "phase4_ops/ops:SanitizeText",
                                "stage": "s1",
                                "inputs": {"text": "$raw_src.text"},
                            }
                        },
                        "rewire_inputs": {"parse": {"raw_text": "$sanitize.text"}},
                    },
                    "outputs": {"summary": "Spliced sanitize before parse for retry."},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(mock_retry))

    res_b = runner.invoke(cli_main, ["run", "--non-interactive", "--no-cache", str(wf_bypass)])
    assert res_b.exit_code == 0, res_b.output
    run_b = store.list_runs(limit=1)[0].id
    state_b = store.get_run_state(run_b)
    assert state_b is not None
    assert state_b.status == RunStatus.SUCCESS
    assert state_b.nodes["sanitize"].status == NodeStatus.SUCCESS
    assert state_b.nodes["parse"].status == NodeStatus.SUCCESS
    assert state_b.nodes["summarize"].status == NodeStatus.SUCCESS

    # --- Case C: CONFIRM policy on failed stage + user answers "Reject" -> run ends FAILED and Stage 2 is BLOCKED ---
    wf_confirm_fail = tmp_path / "workflows" / "confirm_fail.yaml"
    wf_confirm_fail.write_text(
        wf_bypass.read_text(encoding="utf-8").replace(
            "allow_graph_edits: auto", "allow_graph_edits: confirm"
        ),
        encoding="utf-8",
    )
    res_c1 = runner.invoke(
        cli_main, ["run", "--non-interactive", "--no-cache", str(wf_confirm_fail)]
    )
    assert res_c1.exit_code == 2
    run_c = store.list_runs(limit=1)[0].id
    state_c_paused = store.get_run_state(run_c)
    assert state_c_paused is not None
    cp_c = next(
        c for c in state_c_paused.checkpoints if c.node_id == val_id and c.answered_at is None
    )

    res_c2 = runner.invoke(
        cli_main,
        [
            "resume",
            run_c,
            "--non-interactive",
            "--answer",
            f"{val_id}.{cp_c.checkpoint_id}=Reject",
        ],
    )
    assert res_c2.exit_code == 1
    state_c_final = store.get_run_state(run_c)
    assert state_c_final is not None
    assert state_c_final.status == RunStatus.FAILED
    assert state_c_final.nodes[val_id].status == NodeStatus.FAILED
    assert state_c_final.nodes["summarize"].status == NodeStatus.BLOCKED


def test_regular_agent_op_graph_edits_and_outer_agent_snapshot_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test regular AgentOp with allow_graph_edits: auto AND outer coding agent editing workflow.snapshot.yaml."""
    _init_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    store = RunStore(tmp_path)

    # 1. Regular AgentOp with `allow_graph_edits: auto` proposing a downstream splice
    wf_agent_auto = tmp_path / "workflows" / "agent_auto.yaml"
    wf_agent_auto.write_text(
        "version: 1\n"
        "name: agent_auto\n"
        "stages:\n"
        "  s1:\n"
        "    title: Plan\n"
        "  s2:\n"
        "    title: Summarize\n"
        "nodes:\n"
        "  planner:\n"
        "    op: phase4_ops/ops:PlannerAgent\n"
        "    stage: s1\n"
        "    allow_graph_edits: auto\n"
        "    inputs:\n"
        "      text: Bonjour agent\n"
        "  summarize:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $planner.text\n",
        encoding="utf-8",
    )
    mock_planner = tmp_path / "mock_planner.json"
    mock_planner.write_text(
        json.dumps(
            {
                "planner": {
                    "status": "propose_patch",
                    "session_id": "plan_1",
                    "graph_patch": {
                        "reason": "Translate planner output before summarize",
                        "add_nodes": {
                            "agent_tr": {
                                "op": "phase4_ops/ops:TranslateFr",
                                "stage": "s2",
                                "inputs": {"text": "$planner.text"},
                            }
                        },
                        "rewire_inputs": {"summarize": {"text": "$agent_tr.text"}},
                    },
                    "outputs": {"text": "Bonjour agent"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(mock_planner))

    res_auto = runner.invoke(
        cli_main, ["run", "--non-interactive", "--no-cache", str(wf_agent_auto)]
    )
    assert res_auto.exit_code == 0, res_auto.output
    run_auto_id = store.list_runs(limit=1)[0].id
    state_auto = store.get_run_state(run_auto_id)
    assert state_auto is not None
    assert state_auto.status == RunStatus.SUCCESS
    assert state_auto.nodes["agent_tr"].status == NodeStatus.SUCCESS
    assert state_auto.nodes["summarize"].status == NodeStatus.SUCCESS

    # 2. Outer coding agent flow (4.5): run pauses at Stage 1 approval gate -> outer agent edits
    # `.plynx/runs/<run_id>/workflow.snapshot.yaml` -> `plynx resume` validates & executes added node!
    wf_outer = tmp_path / "workflows" / "outer_agent.yaml"
    wf_outer.write_text(
        "version: 1\n"
        "name: outer_agent\n"
        "stages:\n"
        "  s1:\n"
        "    title: Ingest\n"
        "    require_approval: true\n"
        "  s2:\n"
        "    title: Summarize\n"
        "nodes:\n"
        "  ingest:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: Bonjour outer\n"
        "  summarize:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $ingest.text\n",
        encoding="utf-8",
    )
    r_gate = runner.invoke(cli_main, ["run", "--non-interactive", "--no-cache", str(wf_outer)])
    assert r_gate.exit_code == 2, r_gate.output
    outer_run_id = store.list_runs(limit=1)[0].id
    store.approve_stage_gate(outer_run_id, "s1")
    snap_path = store.run_dir(outer_run_id) / "workflow.snapshot.yaml"

    # First try an ILLEGAL outer edit (mutating completed `ingest` node) -> `plynx resume` must reject!
    illegal_yaml = snap_path.read_text(encoding="utf-8").replace("Bonjour outer", "TAMPERED")
    snap_path.write_text(illegal_yaml, encoding="utf-8")
    r_bad_resume = runner.invoke(
        cli_main,
        ["resume", outer_run_id, "--non-interactive"],
    )
    assert r_bad_resume.exit_code != 0

    # Now write a VALID outer-agent splice into `workflow.snapshot.yaml` -> `plynx resume` succeeds!
    snap_path.write_text(
        "version: 1\n"
        "name: outer_agent\n"
        "stages:\n"
        "  s1:\n"
        "    title: Ingest\n"
        "    require_approval: true\n"
        "  s2:\n"
        "    title: Summarize\n"
        "nodes:\n"
        "  ingest:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: Bonjour outer\n"
        "  outer_tr:\n"
        "    op: phase4_ops/ops:TranslateFr\n"
        "    stage: s2\n"
        "    meta:\n"
        "      injected_by: outer_claude_code\n"
        "      reason: Outer agent spliced French translation\n"
        "    inputs:\n"
        "      text: $ingest.text\n"
        "  summarize:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $outer_tr.text\n",
        encoding="utf-8",
    )
    r_good_resume = runner.invoke(
        cli_main,
        ["resume", outer_run_id, "--non-interactive"],
    )
    assert r_good_resume.exit_code == 0, r_good_resume.output
    outer_final = store.get_run_state(outer_run_id)
    assert outer_final is not None
    assert outer_final.status == RunStatus.SUCCESS
    assert outer_final.nodes["outer_tr"].status == NodeStatus.SUCCESS
    assert outer_final.nodes["summarize"].status == NodeStatus.SUCCESS


def test_auto_graph_edits_downgrades_to_confirm_when_splicing_write_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """allow_graph_edits: auto pauses for human confirmation when a patch injects a SideEffect.WRITE op."""
    _init_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    val_id = stage_validator_node_id("s1")
    runner = CliRunner()
    store = RunStore(tmp_path)

    wf_write_patch = tmp_path / "workflows" / "auto_write_guard.yaml"
    wf_write_patch.write_text(
        "version: 1\n"
        "name: auto_write_guard\n"
        "stages:\n"
        "  s1:\n"
        "    title: Ingest\n"
        "    validator:\n"
        "      op: phase4_ops/ops:DemoSupervisor\n"
        "      mode: on_anomaly\n"
        "      allow_graph_edits: auto\n"
        "  s2:\n"
        "    title: Summarize\n"
        "nodes:\n"
        "  ingest:\n"
        "    op: phase4_ops/ops:IngestDoc\n"
        "    stage: s1\n"
        "    inputs:\n"
        "      raw_text: Alert payload\n"
        "      emit_warning: Needs external notification\n"
        "  summarize:\n"
        "    op: phase4_ops/ops:SummarizeText\n"
        "    stage: s2\n"
        "    inputs:\n"
        "      text: $ingest.text\n",
        encoding="utf-8",
    )

    mock_write_patch = tmp_path / "mock_write_patch.json"
    mock_write_patch.write_text(
        json.dumps(
            {
                val_id: {
                    "status": "propose_patch",
                    "session_id": "write_guard_1",
                    "graph_patch": {
                        "reason": "Send external alert before summarizing.",
                        "add_nodes": {
                            "notify_ext": {
                                "op": "phase4_ops/ops:ExternalNotifyOp",
                                "stage": "s2",
                                "inputs": {"text": "$ingest.text"},
                            }
                        },
                        "rewire_inputs": {"summarize": {"text": "$notify_ext.text"}},
                    },
                    "outputs": {"summary": "Proposed external notify splice."},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(mock_write_patch))

    # Even though allow_graph_edits is 'auto', injecting ExternalNotifyOp (WRITE) pauses in WAITING_FOR_USER (exit 2)
    r_paused = runner.invoke(
        cli_main, ["run", "--non-interactive", "--no-cache", str(wf_write_patch)]
    )
    assert r_paused.exit_code == 2, r_paused.output
    run_id = store.list_runs(limit=1)[0].id
    paused_state = store.get_run_state(run_id)
    assert paused_state is not None
    assert paused_state.status == RunStatus.WAITING_FOR_USER
    assert "notify_ext" not in paused_state.nodes
    cp = next(c for c in paused_state.checkpoints if c.node_id == val_id and c.answered_at is None)

    # Once explicitly approved by the user, notify_ext is spliced and runs
    r_approved = runner.invoke(
        cli_main,
        [
            "resume",
            run_id,
            "--non-interactive",
            "--answer",
            f"{val_id}.{cp.checkpoint_id}=Approve Patch",
        ],
    )
    assert r_approved.exit_code == 0, r_approved.output
    final_state = store.get_run_state(run_id)
    assert final_state is not None
    assert final_state.status == RunStatus.SUCCESS
    assert final_state.nodes["notify_ext"].status == NodeStatus.SUCCESS
    assert final_state.nodes["summarize"].status == NodeStatus.SUCCESS
