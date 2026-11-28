"""Unit tests for Phase 3 (FEAT-AGT-1b) in ``plynx-sdk``:
- ``AgentTurnsManifest``, ``AgentTurnRecord``, ``GraphPatchPayload``
- ``AgentOp`` (Choice A & Choice B) and ``StageValidatorOp``
- 0-token replay across simulated ``exit 10`` checkpoint restarts via ``agent_turns.json``
- Auto-generated JSON Schema envelope & file output materialization
- Multi-provider CLI command builders and universal ``turn_output.json`` / stdout fallback
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

import pytest
from plynx_sdk import (
    AgentOp,
    AgentProvider,
    AgentProviderLiteral,
    AgentTurnRecord,
    AgentTurnsManifest,
    AgentTurnStatus,
    CsvFile,
    GraphEditPolicy,
    GraphPatchPayload,
    JsonFile,
    MarkdownFile,
    Range,
    StageValidatorOp,
    TextFile,
    agent_context,
    build_provider_command,
    generate_turn_schema,
    load_agent_turns,
    materialize_turn_outputs,
)
from plynx_sdk.adapters import _parse_envelope_from_text
from plynx_sdk.harness import EXIT_CHECKPOINT, EXIT_SUCCESS, run_harness
from plynx_sdk.protocol import (
    CheckpointManifest,
    InputsManifest,
    OutputsManifest,
    ProtocolError,
    ScalarValue,
)


def test_agent_turns_manifest_and_graph_patch_roundtrip() -> None:
    """AgentTurnsManifest and GraphPatchPayload validate and round-trip cleanly."""
    patch = GraphPatchPayload.from_dict(
        {
            "reason": "Detected French input; splice translator",
            "add_nodes": [
                {
                    "id": "translate_doc",
                    "op": "standard_io/text:Concat",
                    "stage": "ingest",
                    "inputs": {"a": "$parse.text", "b": " [EN]"},
                }
            ],
            "rewire_inputs": {"summarize.doc": "$translate_doc.text"},
        }
    )
    assert "translate_doc" in patch.add_nodes
    assert patch.rewire_inputs == {"summarize": {"doc": "$translate_doc.text"}}

    manifest = AgentTurnsManifest.from_dict(
        {
            "turns": [
                {
                    "turn_index": 0,
                    "provider": "cursor",
                    "model": "auto",
                    "session_id": "chat_abc123",
                    "status": "needs_input",
                    "prompt_summary": "Compare CV against job description...",
                    "questions": [
                        {
                            "id": "role",
                            "question": "Target track?",
                            "options": ["ML", "Backend"],
                        }
                    ],
                    "user_answers": {"role": "ML"},
                    "started_at": "2026-11-26T18:00:00Z",
                    "finished_at": "2026-11-26T18:00:08Z",
                },
                {
                    "turn_index": 1,
                    "provider": "cursor",
                    "model": "auto",
                    "session_id": "chat_abc123",
                    "status": "propose_patch",
                    "graph_patch": patch.to_dict(include_schema=False),
                    "started_at": 1795716010.0,
                    "finished_at": 1795716015.5,
                },
            ]
        }
    )
    assert len(manifest.turns) == 2
    assert manifest.turns[0].provider == AgentProvider.CURSOR
    assert manifest.turns[0].status == AgentTurnStatus.NEEDS_INPUT
    assert manifest.turns[0].user_answers == {"role": "ML"}
    assert isinstance(manifest.turns[0].started_at, float)
    assert manifest.turns[1].status == AgentTurnStatus.PROPOSE_PATCH
    assert manifest.turns[1].graph_patch is not None

    reloaded = AgentTurnsManifest.from_json(manifest.to_json())
    assert reloaded.to_dict() == manifest.to_dict()


def test_agent_turn_envelope_warnings_and_failed_status(tmp_path: Path) -> None:
    """AgentOp records warnings via self.warn() and raises RuntimeError on status='failed'."""
    from plynx_sdk.anomaly import warning_context

    class SimpleTextAgent(AgentOp):
        TITLE = "Simple Text Agent"

        class Outputs(TypedDict):
            text: str

    schema = generate_turn_schema(SimpleTextAgent)
    assert "failed" in schema["properties"]["status"]["enum"]
    assert "warnings" in schema["properties"]
    assert "error" in schema["properties"]

    # 1. Completed turn with warnings -> forwarded to warning_context()
    node_dir_ok = tmp_path / "ok_node"
    with agent_context(node_dir=node_dir_ok), warning_context() as collected:
        out = SimpleTextAgent().run_agent(
            prompt="Return text",
            provider=AgentProvider.MOCK,
            mock_responses=[
                {
                    "status": "completed",
                    "outputs": {"text": "done"},
                    "warnings": ["Low OCR confidence"],
                }
            ],
        )
    assert out == {"text": "done"}
    assert collected == ["Low OCR confidence"]
    turns_ok = load_agent_turns(node_dir_ok)
    assert turns_ok.turns[0].warnings == ["Low OCR confidence"]

    # 2. Failed turn -> raises RuntimeError and records status='failed' + error
    node_dir_fail = tmp_path / "fail_node"
    with (
        agent_context(node_dir=node_dir_fail),
        pytest.raises(RuntimeError, match="Corrupt payload"),
    ):
        SimpleTextAgent().run_agent(
            prompt="Return text",
            provider=AgentProvider.MOCK,
            mock_responses=[{"status": "failed", "error": "Corrupt payload"}],
        )
    turns_fail = load_agent_turns(node_dir_fail)
    assert turns_fail.turns[0].status == AgentTurnStatus.FAILED
    assert turns_fail.turns[0].error == "Corrupt payload"

    # 3. Failed turn without error string -> ProtocolError
    with (
        agent_context(node_dir=tmp_path / "bad_fail_node"),
        pytest.raises(ProtocolError, match="non-empty 'error'"),
    ):
        SimpleTextAgent().run_agent(
            prompt="Return text",
            provider=AgentProvider.MOCK,
            mock_responses=[{"status": "failed", "error": "   "}],
        )


def test_generate_turn_schema_respects_graph_edit_policy() -> None:
    """generate_turn_schema omits propose_patch when forbidden and includes it when allowed."""

    class ReviewOp(AgentOp):
        TITLE = "Review CV"

        class Outputs(TypedDict):
            score: Annotated[int, Range(0, 100)]
            verdict: Literal["pass", "hold"]
            summary: MarkdownFile
            metrics: JsonFile | None

    forbidden_schema = generate_turn_schema(ReviewOp, allow_graph_edits=GraphEditPolicy.FORBIDDEN)
    status_enum = forbidden_schema["properties"]["status"]["enum"]
    assert status_enum == ["completed", "needs_input", "failed"]
    assert "graph_patch" not in forbidden_schema["properties"]

    out_props = forbidden_schema["properties"]["outputs"]["properties"]
    assert out_props["score"]["minimum"] == 0
    assert out_props["score"]["maximum"] == 100
    assert out_props["verdict"]["enum"] == ["pass", "hold"]
    assert set(forbidden_schema["properties"]["outputs"]["required"]) == {
        "score",
        "verdict",
        "summary",
    }

    confirm_schema = generate_turn_schema(ReviewOp, allow_graph_edits=GraphEditPolicy.CONFIRM)
    assert "propose_patch" in confirm_schema["properties"]["status"]["enum"]
    assert "graph_patch" in confirm_schema["properties"]


def test_automatic_file_and_scalar_output_materialization(tmp_path: Path) -> None:
    """Inline file contents materialize to workdir/<port>.<ext> while existing files stay intact."""

    class MultiArtifactAgent(AgentOp):
        TITLE = "Multi Artifact"

        class Outputs(TypedDict):
            report: MarkdownFile
            data: JsonFile
            notes: TextFile
            table: CsvFile
            raw_blob: Path
            existing_doc: MarkdownFile
            count: int

    node_dir = tmp_path / "node_a"
    workdir = node_dir / "workdir"
    workdir.mkdir(parents=True)
    prewritten = workdir / "custom_written.md"
    prewritten.write_text("# Written Directly by CLI\n", encoding="utf-8")

    materialized = materialize_turn_outputs(
        {
            "report": "# Summary\n\nAll checks green.",
            "data": {"ok": True, "items": [1, 2]},
            "notes": "plain text note",
            "table": "col1,col2\na,1\n",
            "raw_blob": "generic path payload",
            "existing_doc": "custom_written.md",
            "count": 42,
        },
        MultiArtifactAgent,
        node_dir=node_dir,
        workdir=workdir,
    )

    assert materialized["report"] == Path("report.md")
    assert (workdir / "report.md").read_text(encoding="utf-8") == "# Summary\n\nAll checks green."

    assert materialized["data"] == Path("data.json")
    assert json.loads((workdir / "data.json").read_text(encoding="utf-8")) == {
        "ok": True,
        "items": [1, 2],
    }

    assert materialized["notes"] == Path("notes.txt")
    assert (workdir / "notes.txt").read_text(encoding="utf-8") == "plain text note"

    assert materialized["table"] == Path("table.csv")
    assert (workdir / "table.csv").read_text(encoding="utf-8") == "col1,col2\na,1\n"

    assert materialized["raw_blob"] == Path("raw_blob.txt")
    assert (workdir / "raw_blob.txt").read_text(encoding="utf-8") == "generic path payload"

    # Pre-existing file inside workdir is preserved by relative path, not overwritten
    assert materialized["existing_doc"] == Path("custom_written.md")
    assert not (workdir / "existing_doc.md").exists()
    assert materialized["count"] == 42


def test_zero_token_replay_across_exit_10_restarts_in_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Turn 0 is NOT re-executed on Attempt 2 after exit-10 checkpoint restart."""
    call_log: list[dict[str, Any]] = []

    def scripted_mock(
        *,
        turn_index: int,
        resume_session_id: str | None,
        user_answers: dict[str, Any] | None,
        prompt: str,
        workdir: Path,
        node_id: str,
    ) -> dict[str, Any]:
        call_log.append(
            {
                "turn_index": turn_index,
                "resume_session_id": resume_session_id,
                "user_answers": user_answers,
                "prompt": prompt,
            }
        )
        if turn_index == 0:
            return {
                "status": "needs_input",
                "session_id": "sess_xyz_99",
                "questions": [
                    {
                        "id": "track",
                        "header": "Role",
                        "question": "Which engineering track?",
                        "options": ["ML", "Systems"],
                        "multi_select": False,
                        "allow_freeform": False,
                    },
                    {
                        "id": "langs",
                        "question": "Preferred languages?",
                        "options": ["Python", "Rust", "TypeScript"],
                        "multi_select": True,
                        "allow_freeform": False,
                    },
                ],
            }
        assert turn_index == 1
        assert resume_session_id == "sess_xyz_99"
        assert user_answers == {"track": "ML", "langs": ["Python", "Rust"]}
        return {
            "status": "completed",
            "session_id": "sess_xyz_99",
            "outputs": {
                "summary": f"# Evaluation ({user_answers['track']})\n",
                "match_score": 91,
            },
        }

    # Register a temporary module with both Choice A and Choice B AgentOps
    mod = types.ModuleType("_test_dynamic_agent_pack")

    class ChoiceBEvaluator(AgentOp):
        TITLE = "Evaluate Candidate"

        class Outputs(TypedDict):
            summary: MarkdownFile
            match_score: int

        def run(
            self,
            candidate_name: str,
            prompt_file: MarkdownFile | None = None,
            prompt: str = "",
            provider: AgentProviderLiteral = "mock",
            model: str = "",
            **extra: Any,
        ) -> Outputs:
            res = self.run_agent(
                prompt_file=prompt_file,
                prompt=prompt,
                provider=provider,
                model=model,
                mock_responses=scripted_mock,
                candidate_name=candidate_name,
                **extra,
            )
            return res  # type: ignore[return-value]

    mod.ChoiceBEvaluator = ChoiceBEvaluator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_test_dynamic_agent_pack", mod)

    node_dir = tmp_path / "eval_node"
    node_dir.mkdir(parents=True)
    inputs_v1 = InputsManifest(
        inputs={
            "candidate_name": ScalarValue(value="Ada"),
            "prompt": ScalarValue(value="Evaluate candidate profile."),
            "provider": ScalarValue(value="mock"),
            "model": ScalarValue(value="mock-v1"),
            "extra_note": ScalarValue(value="Focus on distributed ML"),
        }
    )
    (node_dir / "inputs.json").write_text(inputs_v1.to_json(), encoding="utf-8")

    # Attempt 1: executes Turn 0, writes agent_turns.json + checkpoint.json, exits 10
    rc1 = run_harness("_test_dynamic_agent_pack:ChoiceBEvaluator", node_dir)
    assert rc1 == EXIT_CHECKPOINT
    assert len(call_log) == 1
    assert call_log[0]["turn_index"] == 0
    # Verify mandatory workdir scoping prompt
    assert str(node_dir / "workdir") in call_log[0]["prompt"]
    assert ".agents/skills/" in call_log[0]["prompt"]

    cp_manifest = CheckpointManifest.from_json((node_dir / "checkpoint.json").read_bytes())
    assert cp_manifest.checkpoint_id == "cp_0"
    assert [q.id for q in cp_manifest.questions] == ["track", "langs"]

    turns_after_a1 = load_agent_turns(node_dir)
    assert len(turns_after_a1.turns) == 1
    assert turns_after_a1.turns[0].session_id == "sess_xyz_99"
    assert turns_after_a1.turns[0].user_answers is None

    # Attempt 2: user answers cp_0 -> Turn 0 replays in 0 calls, only Turn 1 runs!
    (node_dir / "checkpoint.json").unlink()
    inputs_v2 = InputsManifest(
        inputs=inputs_v1.inputs,
        checkpoint_answers={"cp_0": {"track": "ML", "langs": ["Python", "Rust"]}},
    )
    (node_dir / "inputs.json").write_text(inputs_v2.to_json(), encoding="utf-8")

    rc2 = run_harness("_test_dynamic_agent_pack:ChoiceBEvaluator", node_dir)
    assert rc2 == EXIT_SUCCESS
    # Total adapter invocations across BOTH attempts must be 2 (Turn 0 once + Turn 1 once), NOT 3!
    assert len(call_log) == 2
    assert [c["turn_index"] for c in call_log] == [0, 1]

    turns_after_a2 = load_agent_turns(node_dir)
    assert len(turns_after_a2.turns) == 2
    assert turns_after_a2.turns[0].user_answers == {
        "track": "ML",
        "langs": ["Python", "Rust"],
    }
    assert turns_after_a2.turns[1].status == AgentTurnStatus.COMPLETED

    outputs_manifest = OutputsManifest.from_json((node_dir / "outputs.json").read_bytes())
    assert outputs_manifest.outputs["match_score"].to_dict() == {
        "kind": "scalar",
        "value": 91,
    }
    assert outputs_manifest.outputs["summary"].to_dict() == {
        "kind": "file",
        "path": "workdir/summary.md",
        "media": "text/markdown",
    }
    assert (node_dir / "workdir" / "summary.md").read_text(encoding="utf-8") == (
        "# Evaluation (ML)\n"
    )


def test_provider_cli_command_builders_and_guards(tmp_path: Path) -> None:
    """Verify non-interactive flags, --resume <sid>, no --continue/--bare, and model omission."""
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    schema_path = workdir / "turn_schema.json"
    output_path = workdir / "turn_output.json"
    prompt_file = workdir / "turn_prompt.md"
    schema_dict = {"type": "object", "properties": {"status": {"type": "string"}}}

    # 1. Claude: omits --model when empty, uses --resume <sid>, --dangerously-skip-permissions
    claude_cmd = build_provider_command(
        AgentProvider.CLAUDE,
        prompt="hello",
        schema_path=schema_path,
        schema_dict=schema_dict,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
        model="",
        resume_session_id="claude_sid_1",
    )
    assert claude_cmd[:4] == ["claude", "-p", "--output-format", "json"]
    assert "--json-schema" in claude_cmd
    assert "--dangerously-skip-permissions" in claude_cmd
    assert "--model" not in claude_cmd
    assert "--resume" in claude_cmd
    assert claude_cmd[claude_cmd.index("--resume") + 1] == "claude_sid_1"
    assert "--continue" not in claude_cmd
    assert "--bare" not in claude_cmd

    # 2. Cursor: cursor-agent -p --output-format json --model gpt-5 --resume s2 --force
    cursor_cmd = build_provider_command(
        AgentProvider.CURSOR,
        prompt="do task",
        schema_path=schema_path,
        schema_dict=schema_dict,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
        model="gpt-5",
        resume_session_id="s2",
    )
    assert cursor_cmd[0] == "cursor-agent"
    assert "--force" in cursor_cmd
    assert cursor_cmd[cursor_cmd.index("--model") + 1] == "gpt-5"
    assert cursor_cmd[cursor_cmd.index("--resume") + 1] == "s2"
    assert "--continue" not in cursor_cmd

    # 3. Codex: fresh vs resume
    codex_fresh = build_provider_command(
        AgentProvider.CODEX,
        prompt="fresh prompt",
        schema_path=schema_path,
        schema_dict=schema_dict,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
        model="o3",
    )
    codex_sandbox_options = [
        "-c",
        'sandbox_mode="workspace-write"',
        "-c",
        'approval_policy="on-request"',
    ]
    assert codex_fresh[:6] == ["codex", "exec", *codex_sandbox_options]
    assert "--output-schema" in codex_fresh
    assert codex_fresh[codex_fresh.index("-m") + 1] == "o3"

    codex_resume = build_provider_command(
        AgentProvider.CODEX,
        prompt="followup",
        schema_path=schema_path,
        schema_dict=schema_dict,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
        model="",
        resume_session_id="thread_77",
    )
    assert codex_resume[:7] == ["codex", "exec", "resume", *codex_sandbox_options]
    assert "-m" not in codex_resume
    assert "thread_77" in codex_resume

    # 4. Gemini, OpenCode, Goose, Aider
    for prov, expected_bin in (
        (AgentProvider.GEMINI, ("gemini", "agy")),
        (AgentProvider.OPENCODE, ("opencode",)),
        (AgentProvider.GOOSE, ("goose",)),
        (AgentProvider.AIDER, ("aider",)),
    ):
        built = build_provider_command(
            prov,
            prompt="task",
            schema_path=schema_path,
            schema_dict=schema_dict,
            output_path=output_path,
            prompt_file_path=prompt_file,
            workdir=workdir,
            model="local-model",
            resume_session_id="sid_9",
        )
        assert built[0] in expected_bin
        assert "--continue" not in built
        assert "--bare" not in built


def test_custom_cli_subprocess_stdin_devnull_and_stdout_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AgentProvider.CUSTOM runs real subprocess with stdin=DEVNULL and supports stdout fallback."""
    helper_script = tmp_path / "fake_cli.py"
    helper_script.write_text(
        "import json, sys\n"
        "# Verify stdin is EOF / DEVNULL immediately (never hangs waiting for user input)\n"
        "assert sys.stdin.read() == ''\n"
        "print(json.dumps({\n"
        "    'session_id': 'custom_sess_42',\n"
        "    'structured_output': {\n"
        "        'status': 'completed',\n"
        "        'outputs': {'answer': '# From Custom CLI'}\n"
        "    }\n"
        "}))\n",
        encoding="utf-8",
    )

    class SimpleChoiceAAgent(AgentOp):
        TITLE = "Choice A Agent"

        class Outputs(TypedDict):
            answer: MarkdownFile

    node_dir = tmp_path / "custom_node"
    workdir = node_dir / "workdir"
    custom_cmd = f'"{sys.executable}" "{helper_script}" --schema "{{schema_path}}"'

    op_inst = SimpleChoiceAAgent()
    with agent_context(node_dir=node_dir, workdir=workdir):
        res = op_inst.run_agent(
            prompt="Generate answer",
            provider=AgentProvider.CUSTOM,
            custom_command=custom_cmd,
        )

    assert res["answer"] == Path("answer.md")
    assert (workdir / "answer.md").read_text(encoding="utf-8") == "# From Custom CLI"
    turns = load_agent_turns(node_dir)
    assert len(turns.turns) == 1
    assert turns.turns[0].session_id == "custom_sess_42"

    # Windows (os.name == "nt"): shlex.split(..., posix=False) keeps surrounding quotes,
    # so build_provider_command must strip matching outer quotes while preserving backslashes.
    monkeypatch.setattr("plynx_sdk.adapters.os.name", "nt")
    win_cmd = build_provider_command(
        AgentProvider.CUSTOM,
        prompt="hello",
        schema_path=workdir / "turn_schema.json",
        schema_dict={"type": "object"},
        output_path=workdir / "turn_output.json",
        prompt_file_path=workdir / "turn_prompt.md",
        workdir=workdir,
        custom_command=r'"C:\Program Files\Python\python.exe" "C:\tmp\script.py" --schema "{schema_path}"',
    )
    assert win_cmd[0] == r"C:\Program Files\Python\python.exe"
    assert win_cmd[1] == r"C:\tmp\script.py"
    assert win_cmd[2] == "--schema"
    assert win_cmd[3] == str(workdir / "turn_schema.json")


def test_stage_validator_op_propose_patch_and_forbidden_guard(tmp_path: Path) -> None:
    """StageValidatorOp writes graph_patch.json when proposing patch; AgentOp rejects forbidden patch."""

    class CheckStage(StageValidatorOp):
        TITLE = "Stage Check"

    reason = "**Sanitize the input** so parsing can continue.\n\nEvidence: `raw.out` has a BOM."
    val_dir = tmp_path / "validator_node"
    with agent_context(node_dir=val_dir):
        out = CheckStage().run_agent(
            prompt="Check stage",
            provider="mock",
            mock_responses={
                "status": "propose_patch",
                "graph_patch": {
                    "reason": reason,
                    "add_nodes": {
                        "sanitize": {
                            "op": "standard_io/text:Concat",
                            "inputs": {"a": "$raw.out"},
                        }
                    },
                    "rewire_inputs": {"final": {"text": "$sanitize.text"}},
                },
            },
        )
    assert out["summary"] == f"Proposed graph patch: {reason}"
    patch_file = val_dir / "graph_patch.json"
    assert patch_file.is_file()
    loaded_patch = GraphPatchPayload.from_json(patch_file.read_bytes())
    assert loaded_patch.reason == reason
    [turn] = load_agent_turns(val_dir).turns
    assert turn.graph_patch is not None
    assert turn.graph_patch.reason == reason

    prompt = (val_dir / "workdir" / "turn_prompt.md").read_text(encoding="utf-8")
    assert "For `graph_patch.reason`: In one short sentence" in prompt
    assert "one short evidence line naming the source and the decisive observation" in prompt

    class StrictAgent(AgentOp):
        TITLE = "No Edits Allowed"

        class Outputs(TypedDict):
            text: str

    strict_dir = tmp_path / "strict_node"
    with pytest.raises(ProtocolError, match="forbidden"), agent_context(node_dir=strict_dir):
        StrictAgent().run_agent(
            prompt="Try unauthorized patch",
            provider="mock",
            mock_responses={
                "status": "propose_patch",
                "graph_patch": {"reason": "Not allowed"},
            },
        )
    strict_prompt = (strict_dir / "workdir" / "turn_prompt.md").read_text(encoding="utf-8")
    assert "graph_patch.reason" not in strict_prompt


def test_parse_fenced_json_and_jsonl_envelopes() -> None:
    """_parse_envelope_from_text handles CLI wrappers, fenced JSON, and JSONL streams."""
    fenced = 'Here is my analysis:\n```json\n{"status": "completed", "outputs": {"x": 1}}\n```'
    env1, sid1 = _parse_envelope_from_text(fenced)
    assert env1 == {"status": "completed", "outputs": {"x": 1}}
    assert sid1 is None

    jsonl = (
        '{"type": "thread.started", "thread_id": "th_999"}\n'
        '{"type": "turn.done", "result": {"status": "completed", "outputs": {"x": 2}}}\n'
    )
    env2, sid2 = _parse_envelope_from_text(jsonl)
    assert env2 == {"status": "completed", "outputs": {"x": 2}}
    assert sid2 == "th_999"

    # Real `agy --output-format json --json-schema` wrapper has top-level `"status": "SUCCESS"`;
    # parser must extract `structured_output` + `conversation_id` rather than outer `"SUCCESS"`.
    agy_stdout = json.dumps(
        {
            "conversation_id": "conv-agy-123",
            "status": "SUCCESS",
            "response": '{"outputs":{"summary":"ok"},"status":"completed"}\n',
            "structured_output": {"status": "completed", "outputs": {"summary": "ok"}},
        }
    )
    env3, sid3 = _parse_envelope_from_text(agy_stdout)
    assert env3 == {"status": "completed", "outputs": {"summary": "ok"}}
    assert sid3 == "conv-agy-123"

    # Real `agy --output-format stream-json --json-schema` NDJSON stream with nested `result`
    agy_stream = (
        '{"event":"init","conversation_id":"conv-stream-7","init":{"model":"gemini-3.8-flash-medium"}}\n'
        '{"event":"step_update","step_update":{"step_index":1,"state":"ACTIVE","step_type":"tool","tool_name":"read_file"}}\n'
        '{"event":"result","result":{"conversation_id":"conv-stream-7","status":"SUCCESS",'
        '"structured_output":{"status":"completed","outputs":{"summary":"streamed ok"}}}}\n'
    )
    env3b, sid3b = _parse_envelope_from_text(agy_stream)
    assert env3b == {"status": "completed", "outputs": {"summary": "streamed ok"}}
    assert sid3b == "conv-stream-7"

    # OpenCode `--format json` streams `part.text` chunks across JSONL lines
    opencode_jsonl = (
        '{"type":"step_start","sessionID":"ses_open_1","part":{"type":"step-start"}}\n'
        '{"type":"text","sessionID":"ses_open_1","part":{"type":"text","text":"{\\"status\\": \\"completed\\", "}}\n'
        '{"type":"text","sessionID":"ses_open_1","part":{"type":"text","text":"\\"outputs\\": {\\"k\\": \\"v\\"}}"}}\n'
    )
    env4, sid4 = _parse_envelope_from_text(opencode_jsonl)
    assert env4 == {"status": "completed", "outputs": {"k": "v"}}
    assert sid4 == "ses_open_1"


def test_provider_quirks_agy_claude_codex_aider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify agy -p placement, Claude min/max sanitization, Codex strict schema, and Aider flags."""
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    schema_path = workdir / "turn_schema.json"
    output_path = workdir / "turn_output.json"
    prompt_file = workdir / "turn_prompt.md"

    class BoundedOp(AgentOp):
        TITLE = "Bounded"

        class Outputs(TypedDict):
            score: Annotated[int, Range(1, 5)]
            note: str | None

    closed_schema = generate_turn_schema(BoundedOp, allow_graph_edits=GraphEditPolicy.FORBIDDEN)

    # 1. agy fallback: -p must immediately precede prompt at the end (never before --output-format)
    monkeypatch.setattr(
        "plynx_sdk.adapters.shutil.which",
        lambda name: "/usr/local/bin/agy" if name == "agy" else None,
    )
    agy_cmd = build_provider_command(
        AgentProvider.GEMINI,
        prompt="hello agy",
        schema_path=schema_path,
        schema_dict=closed_schema,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
        model="gemini-3.8-flash-medium",
        resume_session_id="conv_42",
    )
    assert agy_cmd[0] == "agy"
    assert agy_cmd[1:3] == ["--output-format", "stream-json"]
    assert agy_cmd[-2:] == ["-p", "hello agy"]
    assert "--dangerously-skip-permissions" in agy_cmd
    assert agy_cmd[agy_cmd.index("--model") + 1] == "gemini-3.8-flash-medium"
    assert agy_cmd[agy_cmd.index("--conversation") + 1] == "conv_42"

    # Leading-dash prompt uses --print=<prompt> so Go flag doesn't treat prompt as a flag
    agy_dash = build_provider_command(
        AgentProvider.GEMINI,
        prompt="- bullet prompt",
        schema_path=schema_path,
        schema_dict=closed_schema,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
    )
    assert agy_dash[-1] == "--print=- bullet prompt"

    # 2. Claude: strips numeric minimum/maximum from --json-schema (moves to description)
    claude_cmd = build_provider_command(
        AgentProvider.CLAUDE,
        prompt="score it",
        schema_path=schema_path,
        schema_dict=closed_schema,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
    )
    claude_schema_str = claude_cmd[claude_cmd.index("--json-schema") + 1]
    assert '"minimum"' not in claude_schema_str
    assert '"maximum"' not in claude_schema_str
    assert "Range: [1, 5]" in claude_schema_str

    # 3. Codex: closed schema writes strict turn_schema.codex.json (all properties required);
    # open graph_patch schema omits --output-schema so OpenAI strict mode doesn't 400.
    codex_closed = build_provider_command(
        AgentProvider.CODEX,
        prompt="run closed",
        schema_path=schema_path,
        schema_dict=closed_schema,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
    )
    assert "--output-schema" in codex_closed
    strict_file = Path(codex_closed[codex_closed.index("--output-schema") + 1])
    strict_loaded = json.loads(strict_file.read_text(encoding="utf-8"))
    assert set(strict_loaded["required"]) == set(strict_loaded["properties"].keys())
    assert strict_loaded["additionalProperties"] is False

    open_schema = generate_turn_schema(BoundedOp, allow_graph_edits=GraphEditPolicy.CONFIRM)
    codex_open = build_provider_command(
        AgentProvider.CODEX,
        prompt="run open",
        schema_path=schema_path,
        schema_dict=open_schema,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
    )
    assert "--output-schema" not in codex_open

    # 4. Aider: passes --no-auto-commits and --no-gitignore so it can write inside .plynx/
    aider_cmd = build_provider_command(
        AgentProvider.AIDER,
        prompt="write output",
        schema_path=schema_path,
        schema_dict=closed_schema,
        output_path=output_path,
        prompt_file_path=prompt_file,
        workdir=workdir,
        model="ollama/qwen2.5-coder",
    )
    assert "--no-auto-commits" in aider_cmd
    assert "--no-gitignore" in aider_cmd


def test_agent_turn_record_export() -> None:
    """AgentTurnRecord rejects missing questions when status == needs_input."""
    with pytest.raises(ProtocolError, match="questions"):
        AgentTurnRecord(
            turn_index=0,
            provider=AgentProvider.MOCK,
            status=AgentTurnStatus.NEEDS_INPUT,
            started_at=1.0,
            finished_at=2.0,
            questions=[],
        )
