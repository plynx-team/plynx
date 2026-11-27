"""Tests for Phase 5 (FEAT-AGT-4):
- Built-in standard_io/agent:AgentPrompt and standard_io/agent:StageSupervisor discovery & execution
- End-to-end showcase workflow examples/workflows/adaptive_doc_review.yaml
  (self.warn -> StageSupervisor graph repair -> batch multi-question checkpoint_batch -> Markdown report)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.api_models import NodeStatus, RunStatus
from plynx.cli import main as cli_main
from plynx.registry import PackRegistry
from plynx.registry.extractor import extract_ops_from_file
from plynx.store import RunStore
from plynx.workflow.models import stage_validator_node_id
from plynx.workflow.validator import validate_workflow_file

ROOT = Path(__file__).resolve().parent.parent


def test_standard_io_agent_ops_ast_extraction() -> None:
    """AST extractor discovers AgentPrompt and StageSupervisor with standard AgentOp ports."""
    agent_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "agent.py"
    ops = extract_ops_from_file(agent_py, pack="standard_io", module="agent")
    by_id = {op.id: op for op in ops}

    assert set(by_id.keys()) == {
        "standard_io/agent:AgentPrompt",
        "standard_io/agent:StageSupervisor",
    }

    prompt_op = by_id["standard_io/agent:AgentPrompt"]
    assert prompt_op.valid is True
    assert prompt_op.category == "Core / Agents"
    assert prompt_op.allow_extra_inputs is True
    prompt_inputs = {p.name: p for p in prompt_op.inputs}
    assert {"prompt_file", "prompt", "provider", "model"} <= set(prompt_inputs.keys())
    assert prompt_inputs["provider"].options is not None
    assert "mock" in prompt_inputs["provider"].options
    assert len(prompt_op.outputs) == 1
    assert prompt_op.outputs[0].name == "response"
    assert prompt_op.outputs[0].type == "file"
    assert prompt_op.outputs[0].media == "text/markdown"

    sup_op = by_id["standard_io/agent:StageSupervisor"]
    assert sup_op.valid is True
    assert sup_op.category == "Core / Agents"
    assert sup_op.allow_extra_inputs is True
    sup_inputs = {p.name: p for p in sup_op.inputs}
    assert {"prompt_file", "prompt", "provider", "model"} <= set(sup_inputs.keys())
    assert len(sup_op.outputs) == 1
    assert sup_op.outputs[0].name == "summary"
    assert sup_op.outputs[0].type == "str"


def test_standard_io_agent_prompt_executes_with_mock_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """standard_io/agent:AgentPrompt runs with provider=mock and materializes response.md."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workflows").mkdir()
    wf_file = tmp_path / "workflows" / "prompt_demo.yaml"
    wf_file.write_text(
        """version: 1
name: prompt_demo
nodes:
  ask_agent:
    op: standard_io/agent:AgentPrompt
    inputs:
      prompt: "Summarize the release notes."
      provider: mock
""",
        encoding="utf-8",
    )
    mock_payload = {
        "ask_agent": [
            {
                "status": "completed",
                "outputs": {"response": "# Release Notes\n\n- Added AgentPrompt.\n"},
            }
        ]
    }
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", json.dumps(mock_payload))

    runner = CliRunner()
    val_res = runner.invoke(cli_main, ["validate", str(wf_file)])
    assert val_res.exit_code == 0, val_res.output

    run_res = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_file)])
    assert run_res.exit_code == 0, run_res.output

    store = RunStore(tmp_path)
    runs = store.list_runs(limit=1)
    assert len(runs) == 1
    state = store.get_run_state(runs[0].id)
    assert state is not None
    assert state.status == RunStatus.SUCCESS
    node_state = state.nodes["ask_agent"]
    assert node_state.status == NodeStatus.SUCCESS
    result_path = tmp_path / ".plynx" / "runs" / runs[0].id / "nodes" / "ask_agent" / "result.json"
    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    assert "response" in result_data["outputs"]
    response_out = result_data["outputs"]["response"]
    assert response_out["kind"] == "file"
    blob_path = (
        tmp_path
        / ".plynx"
        / "cache"
        / "blobs"
        / response_out["sha256"][:2]
        / response_out["sha256"]
    )
    assert "# Release Notes" in blob_path.read_text(encoding="utf-8")


def test_adaptive_doc_review_showcase_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Showcase workflow validates and runs: warn -> StageSupervisor patch -> batch checkpoint."""
    showcase_src = ROOT / "examples" / "workflows" / "adaptive_doc_review.yaml"
    assert showcase_src.is_file()

    # 1. Static validation in the repository workspace
    repo_registry = PackRegistry(ROOT)
    issues = validate_workflow_file(showcase_src, registry=repo_registry)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, [i.message for i in errors]

    # 2. Run end-to-end in an isolated temp workspace pointing at examples/custom_packs
    (tmp_path / "plynx.yaml").write_text(
        f"workflows: workflows\npacks:\n  - {(ROOT / 'examples' / 'custom_packs').as_posix()}\n",
        encoding="utf-8",
    )
    (tmp_path / "workflows").mkdir()
    wf_copy = tmp_path / "workflows" / "adaptive_doc_review.yaml"
    wf_copy.write_text(showcase_src.read_text(encoding="utf-8"), encoding="utf-8")

    val_node_id = stage_validator_node_id("ingest")
    mock_payload = {
        val_node_id: [
            {
                "status": "propose_patch",
                "graph_patch": {
                    "reason": "French document detected (lang=fr); splice TranslateToEnglish before review.",
                    "add_nodes": {
                        "translate_doc": {
                            "op": "doc_review/ops:TranslateToEnglish",
                            "stage": "ingest",
                            "title": "Translate French Document",
                            "inputs": {"text": "$ingest_doc.text"},
                        }
                    },
                    "rewire_inputs": {
                        "compile_brief": {"text": "$translate_doc.text"},
                    },
                },
            }
        ]
    }
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", json.dumps(mock_payload))

    runner = CliRunner()
    # Step A: run pauses for StageSupervisor patch approval (GraphEditPolicy.CONFIRM)
    run_res = runner.invoke(
        cli_main,
        ["run", "--non-interactive", "--agent-provider", "mock", str(wf_copy)],
    )
    assert run_res.exit_code == 2, run_res.output

    store = RunStore(tmp_path)
    runs = store.list_runs(limit=1)
    assert len(runs) == 1
    run_id = runs[0].id
    state_a = store.get_run_state(run_id)
    assert state_a is not None
    assert state_a.status == RunStatus.WAITING_FOR_USER
    assert state_a.nodes["ingest_doc"].status == NodeStatus.SUCCESS
    assert any("lang=fr" in w for w in state_a.nodes["ingest_doc"].warnings)
    open_patch_cps = [
        cp for cp in state_a.checkpoints if cp.node_id == val_node_id and cp.answered_at is None
    ]
    assert len(open_patch_cps) == 1
    patch_cp = open_patch_cps[0]
    assert patch_cp.options == ["Approve Patch", "Reject"]

    # Step B: approve the graph patch -> splices translate_doc, then pauses on batch checkpoint
    resume_b = runner.invoke(
        cli_main,
        [
            "resume",
            run_id,
            "--non-interactive",
            "--agent-provider",
            "mock",
            "--answer",
            f"{val_node_id}.{patch_cp.checkpoint_id}=Approve Patch",
        ],
    )
    assert resume_b.exit_code == 2, resume_b.output

    state_b = store.get_run_state(run_id)
    assert state_b is not None
    assert state_b.status == RunStatus.WAITING_FOR_USER
    assert "translate_doc" in state_b.nodes
    assert state_b.nodes["translate_doc"].status == NodeStatus.SUCCESS
    assert state_b.nodes["compile_brief"].status == NodeStatus.WAITING_FOR_USER

    # Step C: answer batch multi-question checkpoint in a single resume
    resume_c = runner.invoke(
        cli_main,
        [
            "resume",
            run_id,
            "--non-interactive",
            "--agent-provider",
            "mock",
            "--answer",
            "compile_brief.cp_0.audience=Executive",
            "--answer",
            "compile_brief.cp_0.focus=Metrics",
            "--answer",
            "compile_brief.cp_0.focus=Action Items",
        ],
    )
    assert resume_c.exit_code == 0, resume_c.output

    state_c = store.get_run_state(run_id)
    assert state_c is not None
    assert state_c.status == RunStatus.SUCCESS
    assert state_c.nodes["compile_brief"].status == NodeStatus.SUCCESS
    brief_result = json.loads(
        (
            tmp_path / ".plynx" / "runs" / run_id / "nodes" / "compile_brief" / "result.json"
        ).read_text(encoding="utf-8")
    )
    report_out = brief_result["outputs"]["report"]
    assert report_out["kind"] == "file"
    sha = report_out["sha256"]
    report_text = (tmp_path / ".plynx" / "cache" / "blobs" / sha[:2] / sha).read_text(
        encoding="utf-8"
    )
    assert "# Quarterly Document Review" in report_text
    assert "**Audience**: Executive" in report_text
    assert "**Focus Areas**: Metrics, Action Items" in report_text
    assert "Hello team. Quarterly report: revenue increased by 14 percent" in report_text
