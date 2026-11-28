"""Tests for Phase 5 (FEAT-AGT-4):
- Built-in standard_io/agent:AgentPrompt and standard_io/agent:StageSupervisor discovery & execution
- General-purpose DetectLanguage across real languages (English, French, Russian, Spanish)
- End-to-end showcase workflow examples/workflows/adaptive_doc_review.yaml
  (DetectLanguage warn -> StageSupervisor splices TranslateText -> AskQuestions batch checkpoint -> MarkdownReport)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from language_tools.ops import DetectLanguage
from plynx.api_models import NodeStatus, RunStatus
from plynx.cli import main as cli_main
from plynx.registry import PackRegistry
from plynx.registry.extractor import extract_ops_from_file
from plynx.store import RunStore
from plynx.workflow.models import stage_validator_node_id
from plynx.workflow.validator import validate_workflow_file
from plynx_sdk.anomaly import warning_context

ROOT = Path(__file__).resolve().parent.parent


def test_standard_io_agent_ops_ast_extraction() -> None:
    """AST extractor discovers AgentPrompt and StageSupervisor with standard AgentOp ports."""
    agent_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "agent.py"
    ops = extract_ops_from_file(agent_py, pack="standard_io", module="agent")
    by_id = {op.id: op for op in ops}

    assert set(by_id.keys()) == {
        "standard_io/agent:AgentBool",
        "standard_io/agent:AgentJson",
        "standard_io/agent:AgentPrompt",
        "standard_io/agent:AgentText",
        "standard_io/agent:StageSupervisor",
    }

    text_op = by_id["standard_io/agent:AgentText"]
    assert text_op.valid is True
    assert text_op.side_effects == "read"
    assert [(p.name, p.type) for p in text_op.outputs] == [("text", "str")]

    json_op = by_id["standard_io/agent:AgentJson"]
    assert json_op.valid is True
    assert json_op.side_effects == "read"
    assert [(p.name, p.type, p.media) for p in json_op.outputs] == [
        ("data", "json", None),
        ("file", "file", "application/json"),
    ]

    bool_op = by_id["standard_io/agent:AgentBool"]
    assert bool_op.valid is True
    assert bool_op.side_effects == "read"
    assert [(p.name, p.type) for p in bool_op.outputs] == [
        ("value", "bool"),
        ("reason", "str"),
    ]

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


def test_detect_language_genuinely_detects_multiple_languages() -> None:
    """DetectLanguage genuinely detects English, Russian, French, and Spanish on arbitrary text."""
    op = DetectLanguage()

    with warning_context() as warns_en:
        res_en = op.run(
            "Quarterly revenue grew significantly across enterprise subscriptions this year.",
            expected_language="en",
        )
    assert res_en["language"] == "en"
    assert res_en["confidence"] > 0.8
    assert warns_en == []

    with warning_context() as warns_ru:
        res_ru = op.run(
            "Привет команда! Квартальный отчет показывает уверенный рост выручки компании.",
            expected_language="en",
        )
    assert res_ru["language"] == "ru"
    assert len(warns_ru) == 1
    assert "'ru'" in warns_ru[0]

    with warning_context() as warns_es:
        res_es = op.run(
            "Hola equipo, el informe trimestral muestra un crecimiento sólido en las ventas.",
            expected_language="en",
        )
    assert res_es["language"] == "es"
    assert len(warns_es) == 1
    assert "'es'" in warns_es[0]

    # Disabling expected_language (`""`) performs pure detection with zero warnings
    with warning_context() as warns_none:
        res_fr = op.run(
            "Bonjour à tous, voici les résultats financiers du dernier trimestre.",
            expected_language="",
        )
    assert res_fr["language"] == "fr"
    assert warns_none == []


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


def test_standard_io_typed_agent_ops_warnings_and_failed_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AgentText, AgentJson, AgentBool run end-to-end with warnings and clean failed status."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workflows").mkdir()
    wf_ok = tmp_path / "workflows" / "typed_agents.yaml"
    wf_ok.write_text(
        """version: 1
name: typed_agents
nodes:
  gen_text:
    op: standard_io/agent:AgentText
    inputs:
      prompt: "Normalize greeting."
      provider: mock
  gen_json:
    op: standard_io/agent:AgentJson
    inputs:
      prompt: "Extract structured fields."
      source: $gen_text.text
      provider: mock
  check_bool:
    op: standard_io/agent:AgentBool
    inputs:
      prompt: "Verify payload."
      payload: $gen_json.data
      provider: mock
""",
        encoding="utf-8",
    )
    mock_ok = {
        "gen_text": [
            {
                "status": "completed",
                "outputs": {"text": "Hello world"},
                "warnings": ["Normalized mixed casing"],
            }
        ],
        "gen_json": [
            {
                "status": "completed",
                "outputs": {"data": {"greeting": "Hello world", "count": 2}},
            }
        ],
        "check_bool": [
            {
                "status": "completed",
                "outputs": {"value": True, "reason": "Matches schema."},
            }
        ],
    }
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", json.dumps(mock_ok))
    runner = CliRunner()
    res = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_ok)])
    assert res.exit_code == 0, res.output

    store = RunStore(tmp_path)
    run_id = store.list_runs(limit=1)[0].id
    state = store.get_run_state(run_id)
    assert state is not None
    assert state.status == RunStatus.SUCCESS
    assert state.nodes["gen_text"].warnings == ["Normalized mixed casing"]

    json_res = json.loads(
        (store.node_dir(run_id, "gen_json") / "result.json").read_text(encoding="utf-8")
    )
    assert json_res["outputs"]["data"]["value"] == {"greeting": "Hello world", "count": 2}
    assert json_res["outputs"]["file"]["kind"] == "file"
    assert json_res["outputs"]["file"]["media"] == "application/json"

    bool_res = json.loads(
        (store.node_dir(run_id, "check_bool") / "result.json").read_text(encoding="utf-8")
    )
    assert bool_res["outputs"]["value"]["value"] is True
    assert bool_res["outputs"]["reason"]["value"] == "Matches schema."

    # Agent returning status='failed' exits 1 (FAILED) with error message recorded
    wf_fail = tmp_path / "workflows" / "agent_fail.yaml"
    wf_fail.write_text(
        """version: 1
name: agent_fail
nodes:
  parse_doc:
    op: standard_io/agent:AgentText
    inputs:
      prompt: "Parse corrupt input."
      provider: mock
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PLYNX_MOCK_AGENT_RESPONSES",
        json.dumps(
            {
                "parse_doc": [
                    {
                        "status": "failed",
                        "error": "Input document is encrypted and unreadable.",
                    }
                ]
            }
        ),
    )
    fail_res = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_fail)])
    assert fail_res.exit_code == 1
    fail_run_id = store.list_runs(limit=1)[0].id
    fail_state = store.get_run_state(fail_run_id)
    assert fail_state is not None
    assert fail_state.status == RunStatus.FAILED
    assert fail_state.nodes["parse_doc"].status == NodeStatus.FAILED
    assert fail_state.nodes["parse_doc"].exit_code == 1
    stderr_text = (store.run_dir(fail_run_id) / "logs" / "parse_doc.stderr.log").read_text(
        encoding="utf-8"
    )
    assert "Input document is encrypted and unreadable." in stderr_text


def test_adaptive_doc_review_showcase_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Showcase workflow validates and runs: DetectLanguage -> StageSupervisor -> TranslateText -> AskQuestions -> MarkdownReport."""
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
                    "reason": "Detected French document ('fr'); splice TranslateText before formatting.",
                    "add_nodes": {
                        "translate_doc": {
                            "op": "language_tools/ops:TranslateText",
                            "stage": "ingest",
                            "title": "Translate Document to English",
                            "inputs": {
                                "text": "$detect_lang.text",
                                "target_language": "English",
                            },
                        }
                    },
                    "rewire_inputs": {
                        "format_body": {"document": "$translate_doc.text"},
                    },
                },
            }
        ],
        "translate_doc": [
            {
                "status": "completed",
                "outputs": {
                    "text": (
                        "Hello team. The quarterly report shows revenue increased by 14% "
                        "driven by enterprise renewals. Thank you for your collaboration."
                    ),
                    "source_language": "fr",
                },
            }
        ],
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
    assert state_a.nodes["detect_lang"].status == NodeStatus.SUCCESS
    assert any("'fr'" in w for w in state_a.nodes["detect_lang"].warnings)
    open_patch_cps = [
        cp for cp in state_a.checkpoints if cp.node_id == val_node_id and cp.answered_at is None
    ]
    assert len(open_patch_cps) == 1
    patch_cp = open_patch_cps[0]
    assert patch_cp.options == ["Approve Patch", "Reject"]

    # Step B: approve the graph patch -> splices translate_doc, then pauses on AskQuestions batch checkpoint
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
    assert state_b.nodes["ask_preferences"].status == NodeStatus.WAITING_FOR_USER

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
            "ask_preferences.cp_0.audience=Executive",
            "--answer",
            "ask_preferences.cp_0.focus=Metrics",
            "--answer",
            "ask_preferences.cp_0.focus=Action Items",
        ],
    )
    assert resume_c.exit_code == 0, resume_c.output

    state_c = store.get_run_state(run_id)
    assert state_c is not None
    assert state_c.status == RunStatus.SUCCESS
    assert state_c.nodes["final_report"].status == NodeStatus.SUCCESS
    report_result = json.loads(
        (
            tmp_path / ".plynx" / "runs" / run_id / "nodes" / "final_report" / "result.json"
        ).read_text(encoding="utf-8")
    )
    report_out = report_result["outputs"]["report"]
    assert report_out["kind"] == "file"
    sha = report_out["sha256"]
    report_text = (tmp_path / ".plynx" / "cache" / "blobs" / sha[:2] / sha).read_text(
        encoding="utf-8"
    )
    assert "# Quarterly Document Review" in report_text
    assert "- **Target Audience**: Executive" in report_text
    assert "- **Focus Areas**: Metrics, Action Items" in report_text
    assert "Hello team. The quarterly report shows revenue increased by 14%" in report_text


def test_maintenance_handoff_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the same workflow with structured fields and with a superseded formatter."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli_main, ["init", "."]).exit_code == 0
    workflow = Path("workflows/maintenance_handoff.yaml")
    baseline = (ROOT / "examples" / workflow).read_bytes()
    workflow.write_bytes(baseline)
    ticket = Path("examples/samples/maintenance_handoff.json")
    ticket.parent.mkdir(parents=True)
    ticket.write_text(
        json.dumps({"ticket": "OPS-001", "approved_window": "Monday 09:00 UTC", "owner": "Ari"}),
        encoding="utf-8",
    )
    run = ["run", "--non-interactive", "--agent-provider", "mock", str(workflow)]
    normal = runner.invoke(cli_main, run)
    assert normal.exit_code == 0, normal.output

    ticket.write_bytes((ROOT / ticket).read_bytes())
    supervisor = stage_validator_node_id("prepare")
    statement = "OPS-317 — approved window: Friday 04:00 UTC. Owner: Mina."
    patch = {
        "reason": "The release-control decision approves Friday with Mina and withdraws Tuesday.",
        "add_nodes": {
            "interpret_decision": {
                "op": "standard_io/agent:AgentText",
                "stage": "prepare",
                "inputs": {
                    "record": "$ticket.value_json",
                    "prompt": "State the approved ticket, window and owner from the decision.",
                },
            },
        },
        "rewire_inputs": {"draft": {"body": "$interpret_decision.text"}},
    }
    monkeypatch.setenv(
        "PLYNX_MOCK_AGENT_RESPONSES",
        json.dumps(
            {
                supervisor: {"status": "propose_patch", "graph_patch": patch},
                "interpret_decision": {"status": "completed", "outputs": {"text": statement}},
            }
        ),
    )
    paused = runner.invoke(cli_main, run)
    assert paused.exit_code == 2, paused.output
    store = RunStore(tmp_path)
    run_id = store.list_runs(limit=1)[0].id
    state = store.get_run_state(run_id)
    assert state is not None and state.nodes["notice"].status == NodeStatus.FAILED
    cp = next(c for c in state.checkpoints if c.node_id == supervisor)
    resumed = runner.invoke(
        cli_main,
        [
            "resume",
            run_id,
            "--non-interactive",
            "--answer",
            f"{supervisor}.{cp.checkpoint_id}=Approve Patch",
        ],
    )
    assert resumed.exit_code == 0, resumed.output
    state = store.get_run_state(run_id)
    assert state is not None and state.workflow_snapshot is not None
    assert state.nodes["notice"].status == NodeStatus.FAILED
    meta = state.workflow_snapshot.nodes["notice"].meta
    assert meta is not None and meta.superseded_by == "interpret_decision"
    assert state.nodes["interpret_decision"].status == NodeStatus.SUCCESS
    result = json.loads((store.node_dir(run_id, "draft") / "result.json").read_bytes())
    sha = result["outputs"]["report"]["sha256"]
    report = (tmp_path / ".plynx/cache/blobs" / sha[:2] / sha).read_text(encoding="utf-8")
    assert report.strip() == f"# Maintenance notice\n\n{statement}"
    assert workflow.read_bytes() == baseline
