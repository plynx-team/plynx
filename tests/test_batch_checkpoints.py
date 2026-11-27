"""Tests for FEAT-AGT-1a: StrEnum constants, ``warn()``, and batch multi-question checkpoints."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from plynx.api_models import (
    AgentProvider as ApiAgentProvider,
)
from plynx.api_models import (
    AgentTurnStatus as ApiAgentTurnStatus,
)
from plynx.api_models import (
    CheckpointQuestionState,
    NodeStatus,
    RunStatus,
    is_batch_checkpoint,
)
from plynx.api_models import (
    GraphEditPolicy as ApiGraphEditPolicy,
)
from plynx.api_models import (
    ValidatorMode as ApiValidatorMode,
)
from plynx.cli.interaction import load_cli_answers, parse_question_input
from plynx.engine.scheduler import _encode_answer
from plynx.server import create_app
from plynx.store import USER_VERSION, RunStore
from plynx_sdk.protocol import (
    AgentProvider,
    AgentTurnStatus,
    CheckpointManifest,
    CheckpointQuestion,
    GraphEditPolicy,
    InputsManifest,
    OutputsManifest,
    ProtocolError,
    ResultManifest,
    ScalarValue,
    ValidatorMode,
    validate_batch_answers,
)

ROOT = Path(__file__).resolve().parent.parent
SDK_SRC = ROOT / "packages" / "plynx-sdk" / "src"
SDK_PATH = ROOT / "packages" / "plynx-sdk"

OPS_CODE = '''"""Fixture ops for warn() and batch checkpoints."""

from __future__ import annotations

from typing import TypedDict

from plynx_sdk import CheckpointQuestion, Op, checkpoint, checkpoint_batch, op, warn


class Report(Op):
    TITLE = "Report"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self) -> Outputs:
        self.warn("first anomaly")
        warn("second anomaly")
        return {"text": "ok"}


class Interview(Op):
    TITLE = "Interview"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self) -> Outputs:
        answers = self.checkpoint_batch(
            [
                CheckpointQuestion(
                    id="role", question="Target track?", header="Track", options=["ML", "Backend"]
                ),
                {
                    "id": "skills",
                    "question": "Skills?",
                    "options": ["python", "sql", "go"],
                    "multi_select": True,
                    "allow_freeform": False,
                },
                {"id": "note", "question": "Note?"},
            ]
        )
        return {"text": json_dump(answers)}


def json_dump(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True)


class ReservedId(Op):
    TITLE = "Reserved"

    class Outputs(TypedDict):
        text: str

    def run(self) -> Outputs:
        self.checkpoint_batch([{"id": "default", "question": "x?"}])
        return {"text": "unreachable"}


class MixedOut(TypedDict):
    text: str


@op(title="Mixed", cacheable=False)
def mixed() -> MixedOut:
    first = checkpoint("Single first?")
    batch = checkpoint_batch([{"id": "q", "question": "Batch?"}])
    return {"text": f"{first}|{batch['q']}"}
'''


def _setup_pack(base: Path) -> Path:
    pack_src = base / "batch_pack_src"
    pkg = pack_src / "batch_pack"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "ops.py").write_text(OPS_CODE, encoding="utf-8")
    return pack_src


def _harness(pack_src: Path, op_spec: str, node_dir: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SDK_SRC), str(pack_src)])
    return subprocess.run(
        [sys.executable, "-m", "plynx_sdk.harness", "--op", op_spec, "--dir", str(node_dir)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_inputs(node_dir: Path, answers: dict[str, object] | None = None) -> None:
    node_dir.mkdir(parents=True, exist_ok=True)
    manifest = InputsManifest(checkpoint_answers=answers or {})  # type: ignore[arg-type]
    (node_dir / "inputs.json").write_text(manifest.to_json(), encoding="utf-8")


# --- StrEnum constants -------------------------------------------------------------------------


def test_strenum_values_and_json_serialization() -> None:
    assert [m.value for m in AgentTurnStatus] == ["completed", "needs_input", "propose_patch"]
    assert [m.value for m in GraphEditPolicy] == ["forbidden", "confirm", "auto"]
    assert [m.value for m in ValidatorMode] == ["on_anomaly", "on_failure", "always"]
    assert [m.value for m in AgentProvider] == [
        "default",
        "claude",
        "cursor",
        "codex",
        "gemini",
        "opencode",
        "goose",
        "aider",
        "custom",
        "mock",
    ]
    assert json.dumps({"s": AgentTurnStatus.NEEDS_INPUT}) == '{"s": "needs_input"}'
    assert AgentProvider("mock") is AgentProvider.MOCK
    assert str(AgentTurnStatus.COMPLETED) == "completed"
    # api_models re-exports the exact same StrEnum classes (Invariant 6)
    assert ApiAgentTurnStatus is AgentTurnStatus
    assert ApiGraphEditPolicy is GraphEditPolicy
    assert ApiValidatorMode is ValidatorMode
    assert ApiAgentProvider is AgentProvider


# --- protocol ----------------------------------------------------------------------------------


def test_single_checkpoint_manifest_populates_default_question() -> None:
    cp = CheckpointManifest(checkpoint_id="cp_0", question="foo?", options=["foo"])
    assert not cp.is_batch
    assert [q.id for q in cp.questions] == ["default"]
    assert cp.questions[0].options == ["foo"]
    assert CheckpointManifest.from_json(cp.to_json()) == cp


def test_v2_0_checkpoint_json_without_questions_still_parses() -> None:
    raw = json.dumps(
        {
            "schema": 1,
            "checkpoint_id": "cp_0",
            "question": "old?",
            "options": None,
            "allow_freeform": True,
        }
    )
    cp = CheckpointManifest.from_json(raw)
    assert cp.questions[0].id == "default"
    assert cp.questions[0].allow_freeform is True


def test_batch_manifest_validation() -> None:
    q = CheckpointQuestion(id="a", question="A?")
    cp = CheckpointManifest(checkpoint_id="cp_0", questions=[q])
    assert cp.is_batch is True
    assert cp.display_question() == "A?"
    with pytest.raises(ProtocolError, match="duplicate"):
        CheckpointManifest(checkpoint_id="cp_0", questions=[q, q])
    with pytest.raises(ProtocolError):
        CheckpointManifest(checkpoint_id="cp_0")
    with pytest.raises(ProtocolError):
        CheckpointQuestion(id="bad id", question="x")


def test_validate_batch_answers_rules() -> None:
    qs = [
        CheckpointQuestion(id="role", question="r", options=["ML", "BE"], allow_freeform=False),
        CheckpointQuestion(id="skills", question="s", options=["py", "sql"], multi_select=True),
    ]
    assert validate_batch_answers(qs, {"role": "ML", "skills": "py"}) == {
        "role": "ML",
        "skills": ["py"],
    }
    assert validate_batch_answers(qs, {"role": "ML", "skills": ["py", "other"]})["skills"] == [
        "py",
        "other",
    ]
    with pytest.raises(ProtocolError, match="missing"):
        validate_batch_answers(qs, {"role": "ML"})
    with pytest.raises(ProtocolError, match="unknown"):
        validate_batch_answers(qs, {"role": "ML", "skills": [], "zzz": "x"})
    with pytest.raises(ProtocolError, match="not one of"):
        validate_batch_answers(qs, {"role": "Ops", "skills": []})
    with pytest.raises(ProtocolError, match="expected a str"):
        validate_batch_answers(qs, {"role": ["ML"], "skills": []})


def test_inputs_manifest_round_trips_batch_answers() -> None:
    manifest = InputsManifest(
        checkpoint_answers={"cp_0": "x", "cp_1": {"a": "1", "b": ["2", "3"]}},
    )
    assert InputsManifest.from_json(manifest.to_json()) == manifest
    with pytest.raises(ProtocolError):
        InputsManifest.from_dict(
            {"schema": 1, "inputs": {}, "checkpoint_answers": {"cp_0": {"a": 1}}}
        )


def test_warnings_field_validation_and_default() -> None:
    out = OutputsManifest(started_at=1.0, finished_at=2.0)
    assert out.warnings == []
    assert out.to_dict()["warnings"] == []
    legacy = {"schema": 1, "started_at": 1.0, "finished_at": 2.0, "outputs": {}}
    assert OutputsManifest.from_dict(legacy).warnings == []
    with pytest.raises(ProtocolError, match="warnings"):
        OutputsManifest.from_dict({**legacy, "warnings": "oops"})
    res = ResultManifest(
        status="SUCCESS", cache_key="k", cache_hit=False, started_at=1.0, finished_at=2.0
    )
    assert ResultManifest.from_json(res.to_json()).warnings == []


# --- harness subprocess: warn(), batch checkpoint, replay ---------------------------------------


def test_warn_recorded_in_outputs_json(tmp_path: Path) -> None:
    pack_src = _setup_pack(tmp_path)
    node_dir = tmp_path / "report"
    _write_inputs(node_dir)
    proc = _harness(pack_src, "batch_pack.ops:Report", node_dir)
    assert proc.returncode == 0, proc.stderr
    outputs = OutputsManifest.from_json((node_dir / "outputs.json").read_text(encoding="utf-8"))
    assert outputs.warnings == ["first anomaly", "second anomaly"]
    assert outputs.outputs == {"text": ScalarValue(value="ok")}


def test_batch_checkpoint_pauses_once_and_replays(tmp_path: Path) -> None:
    pack_src = _setup_pack(tmp_path)
    node_dir = tmp_path / "interview"
    _write_inputs(node_dir)

    p1 = _harness(pack_src, "batch_pack.ops:Interview", node_dir)
    assert p1.returncode == 10, p1.stderr
    cp = CheckpointManifest.from_json((node_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert cp.checkpoint_id == "cp_0"
    assert cp.is_batch
    assert [q.id for q in cp.questions] == ["role", "skills", "note"]
    assert cp.questions[0].header == "Track"
    assert cp.questions[1].multi_select is True
    assert cp.questions[2].allow_freeform is True

    _write_inputs(node_dir, {"cp_0": {"role": "ML", "skills": "python", "note": "hi"}})
    p2 = _harness(pack_src, "batch_pack.ops:Interview", node_dir)
    assert p2.returncode == 0, p2.stderr
    outputs = OutputsManifest.from_json((node_dir / "outputs.json").read_text(encoding="utf-8"))
    text = outputs.outputs["text"]
    assert isinstance(text, ScalarValue)
    assert json.loads(str(text.value)) == {"role": "ML", "skills": ["python"], "note": "hi"}


def test_batch_checkpoint_invalid_stored_answers_fail_op(tmp_path: Path) -> None:
    pack_src = _setup_pack(tmp_path)
    node_dir = tmp_path / "interview_bad"
    _write_inputs(node_dir, {"cp_0": {"role": "ML", "skills": ["rust"], "note": "x"}})
    proc = _harness(pack_src, "batch_pack.ops:Interview", node_dir)
    assert proc.returncode == 1
    assert "not one of" in proc.stderr


def test_batch_reserved_id_rejected(tmp_path: Path) -> None:
    pack_src = _setup_pack(tmp_path)
    node_dir = tmp_path / "reserved"
    _write_inputs(node_dir)
    proc = _harness(pack_src, "batch_pack.ops:ReservedId", node_dir)
    assert proc.returncode == 1
    assert "reserved" in proc.stderr


def test_single_then_batch_use_sequential_ids(tmp_path: Path) -> None:
    pack_src = _setup_pack(tmp_path)
    node_dir = tmp_path / "mixed"
    _write_inputs(node_dir, {"cp_0": "one"})
    proc = _harness(pack_src, "batch_pack.ops:mixed", node_dir)
    assert proc.returncode == 10, proc.stderr
    cp = CheckpointManifest.from_json((node_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert cp.checkpoint_id == "cp_1" and cp.is_batch

    _write_inputs(node_dir, {"cp_0": "one", "cp_1": {"q": "two"}})
    proc = _harness(pack_src, "batch_pack.ops:mixed", node_dir)
    assert proc.returncode == 0, proc.stderr
    outputs = OutputsManifest.from_json((node_dir / "outputs.json").read_text(encoding="utf-8"))
    assert outputs.outputs == {"text": ScalarValue(value="one|two")}


# --- store migration ---------------------------------------------------------------------------


def test_store_migrates_v1_database_in_place(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = store.create_run(workflow_path="w.yaml", workflow_bytes=b"x", node_ids=["n"])
    store.create_checkpoint(run_id, "n", "cp_0", "old?", options=["a"], allow_freeform=False)
    db_path = store.db_path

    # Downgrade the database to the v2.0.0 layout.
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE checkpoints DROP COLUMN questions_json;")
    conn.execute("ALTER TABLE node_runs DROP COLUMN warnings_json;")
    conn.execute("PRAGMA user_version = 1;")
    conn.commit()
    conn.close()

    migrated = RunStore(tmp_path)
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version;").fetchone()[0] == USER_VERSION == 2
    conn.close()
    cp = migrated.get_checkpoint(run_id, "n", "cp_0")
    assert cp is not None
    assert cp.question == "old?" and cp.questions == []
    assert not is_batch_checkpoint(cp.questions)
    migrated.update_node_status(run_id, "n", NodeStatus.SUCCESS, warnings=["lang=fr"])
    migrated_state = migrated.get_run_state(run_id)
    assert migrated_state is not None
    assert migrated_state.nodes["n"].warnings == ["lang=fr"]
    # Opening again is a no-op.
    RunStore(tmp_path)


def test_store_round_trips_batch_questions_and_answers(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = store.create_run(workflow_path="w.yaml", workflow_bytes=b"x", node_ids=["n"])
    questions = [
        CheckpointQuestionState(id="a", question="A?", options=["x", "y"]),
        CheckpointQuestionState(id="b", question="B?", multi_select=True),
    ]
    store.create_checkpoint(run_id, "n", "cp_0", "A? | B?", questions=questions)
    cp = store.get_checkpoint(run_id, "n", "cp_0")
    assert cp is not None and cp.questions == questions and cp.answers is None
    assert store.answer_checkpoint(run_id, "n", "cp_0", json.dumps({"a": "x", "b": ["1", "2"]}))
    cp = store.get_checkpoint(run_id, "n", "cp_0")
    assert cp is not None and cp.answers == {"a": "x", "b": ["1", "2"]}


# --- scheduler answer encoding -----------------------------------------------------------------


def test_encode_answer_matches_checkpoint_shape() -> None:
    single = CheckpointManifest(checkpoint_id="cp_0", question="q?")
    assert _encode_answer(single, "foo") == "foo"
    assert _encode_answer(single, {"default": "foo"}) is None

    batch = CheckpointManifest(
        checkpoint_id="cp_0",
        questions=[CheckpointQuestion(id="m", question="m?", multi_select=True)],
    )
    assert _encode_answer(batch, {"m": "one"}) == '{"m": ["one"]}'
    assert _encode_answer(batch, "plain") is None
    assert _encode_answer(batch, {"zzz": "one"}) is None


# --- CLI helpers -------------------------------------------------------------------------------


def test_load_cli_answers_batch_forms(tmp_path: Path) -> None:
    answers_file = tmp_path / "answers.json"
    answers_file.write_text(
        json.dumps({"n.cp_0": {"a": "1", "b": ["x"]}, "n.cp_1": "plain"}), encoding="utf-8"
    )
    loaded = load_cli_answers(
        answers_file,
        ["m.cp_0.role=ML", "m.cp_0.skills=py", "m.cp_0.skills=sql", "n.cp_1=override"],
    )
    assert loaded["n.cp_0"] == {"a": "1", "b": ["x"]}
    assert loaded["n.cp_1"] == "override"
    assert loaded["m.cp_0"] == {"role": "ML", "skills": ["py", "sql"]}


def test_parse_question_input() -> None:
    single = CheckpointQuestion(id="r", question="r?", options=["ML", "BE"], allow_freeform=False)
    assert parse_question_input("2\n", single) == (True, "BE", None)
    ok, value, err = parse_question_input("9\n", single)
    assert not ok and value is None and err is not None

    multi = CheckpointQuestion(id="s", question="s?", options=["a", "b", "c"], multi_select=True)
    assert parse_question_input("1, c\n", multi) == (True, ["a", "c"], None)
    assert parse_question_input("free\n", multi) == (True, ["free"], None)

    text = CheckpointQuestion(id="t", question="t?")
    assert parse_question_input("hello\n", text) == (True, "hello", None)
    assert parse_question_input("\n", text)[0] is False


# --- REST --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"answers": {"a": "x", "b": "1"}}, 200),
        ({"answer": "x"}, 422),
        ({"answers": {"a": "x"}}, 422),
        ({"answers": {"a": "nope", "b": ["1"]}}, 422),
        ({}, 422),
    ],
)
def test_server_batch_answer_validation(
    tmp_path: Path, payload: dict[str, object], status: int
) -> None:
    import asyncio

    store = RunStore(tmp_path)
    run_id = store.create_run(workflow_path="w.yaml", workflow_bytes=b"x", node_ids=["n"])
    store.update_node_status(run_id, "n", NodeStatus.WAITING_FOR_USER, attempt=1, exit_code=10)
    store.create_checkpoint(
        run_id,
        "n",
        "cp_0",
        "A? | B?",
        questions=[
            CheckpointQuestionState(id="a", question="A?", options=["x"], allow_freeform=False),
            CheckpointQuestionState(id="b", question="B?", multi_select=True),
        ],
    )
    store.update_run_status(run_id, RunStatus.WAITING_FOR_USER)
    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                f"/api/v1/runs/{run_id}/checkpoints/n/cp_0/answer", json=payload
            )
            assert resp.status_code == status, resp.text
            if status == 200:
                assert resp.json()["answers"] == {"a": "x", "b": ["1"]}
                state = (await client.get(f"/api/v1/runs/{run_id}")).json()
                cp = state["checkpoints"][0]
                assert cp["answers"] == {"a": "x", "b": ["1"]}
                assert len(cp["questions"]) == 2

    asyncio.run(_test())


def test_server_single_checkpoint_accepts_answers_default_key(tmp_path: Path) -> None:
    import asyncio

    store = RunStore(tmp_path)
    run_id = store.create_run(workflow_path="w.yaml", workflow_bytes=b"x", node_ids=["n"])
    store.update_node_status(run_id, "n", NodeStatus.WAITING_FOR_USER, attempt=1, exit_code=10)
    store.create_checkpoint(
        run_id,
        "n",
        "cp_0",
        "q?",
        questions=[CheckpointQuestionState(id="default", question="q?")],
    )
    store.update_run_status(run_id, RunStatus.WAITING_FOR_USER)
    app = create_app(tmp_path)

    async def _test() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                f"/api/v1/runs/{run_id}/checkpoints/n/cp_0/answer",
                json={"answers": {"default": "yes"}},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["answer"] == "yes"

    asyncio.run(_test())


# --- end-to-end through the CLI ----------------------------------------------------------------


def _create_e2e_pack(workspace: Path) -> None:
    pack_dir = workspace / "custom_packs" / "batch_pack"
    src_dir = pack_dir / "src" / "batch_pack"
    src_dir.mkdir(parents=True)
    sdk_posix = SDK_PATH.resolve().as_posix()
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "batch-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_posix}", editable = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/batch_pack"]
""",
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(OPS_CODE, encoding="utf-8")


def _run_cli(
    cwd: Path, *args: str, stdin_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("CI", None)
    return subprocess.run(
        [sys.executable, "-m", "plynx.cli", *args],
        cwd=cwd,
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


E2E_WORKFLOW = """version: 1
name: batch_e2e
nodes:
  report:
    op: batch_pack/ops:Report
  interview:
    op: batch_pack/ops:Interview
"""


def test_e2e_batch_checkpoint_via_answers_and_stdin(tmp_path: Path) -> None:
    _create_e2e_pack(tmp_path)
    wf_path = tmp_path / "batch.yaml"
    wf_path.write_text(E2E_WORKFLOW, encoding="utf-8")

    # 1. Pre-supplied answers (single pause, single resume).
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps({"interview.cp_0": {"role": "Backend", "skills": ["go"], "note": "n"}}),
        encoding="utf-8",
    )
    res = _run_cli(tmp_path, "run", "--answers", str(answers), str(wf_path))
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"

    store = RunStore(tmp_path)
    run_id = store.list_runs()[0].id
    result = ResultManifest.from_json(
        (store.node_dir(run_id, "interview") / "result.json").read_text(encoding="utf-8")
    )
    text = result.outputs["text"]
    assert isinstance(text, ScalarValue)
    assert json.loads(str(text.value)) == {"role": "Backend", "skills": ["go"], "note": "n"}
    report = ResultManifest.from_json(
        (store.node_dir(run_id, "report") / "result.json").read_text(encoding="utf-8")
    )
    assert report.warnings == ["first anomaly", "second anomaly"]
    state = store.get_run_state(run_id)
    assert state is not None
    assert state.status == RunStatus.SUCCESS
    assert state.nodes["report"].warnings == ["first anomaly", "second anomaly"]

    # 2. Terminal prompts: role, skills (comma separated), note.
    res = _run_cli(tmp_path, "run", str(wf_path), stdin_text="1\n1,3\nhello\n")
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "[interview.cp_0] 3 questions" in res.stdout
    run_2 = next(r.id for r in store.list_runs() if r.id != run_id)
    result_2 = ResultManifest.from_json(
        (store.node_dir(run_2, "interview") / "result.json").read_text(encoding="utf-8")
    )
    text_2 = result_2.outputs["text"]
    assert isinstance(text_2, ScalarValue)
    assert json.loads(str(text_2.value)) == {
        "role": "ML",
        "skills": ["python", "go"],
        "note": "hello",
    }
    state_2 = store.get_run_state(run_2)
    assert state_2 is not None
    cps = [c for c in state_2.checkpoints if c.node_id == "interview"]
    assert len(cps) == 1
    assert cps[0].answers == {"role": "ML", "skills": ["python", "go"], "note": "hello"}
    assert [q.id for q in cps[0].questions] == ["role", "skills", "note"]
