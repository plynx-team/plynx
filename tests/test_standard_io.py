"""Tests for Task 1.7: ``standard_io`` pack ops and end-to-end execution."""

from __future__ import annotations

import asyncio
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from plynx.api_models import NodeStatus, RunStatus
from plynx.engine import LocalExecutor, Scheduler, SchedulerOptions
from plynx.store import RunStore
from plynx.workflow.models import Workflow, load_workflow
from plynx_sdk import checkpoint_context
from plynx_sdk.checkpoint import CheckpointInterrupt
from plynx_sdk.protocol import (
    OutputsManifest,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ScalarValue,
)
from standard_io.data import (
    CsvSummary,
    JsonExtract,
    JsonMerge,
    MathOp,
    TemplateFormat,
)
from standard_io.files import (
    BundleDirectory,
    ListDirectory,
    MarkdownReport,
)
from standard_io.interactive import (
    AskChoice,
)

from tests.fixtures.toy_ops import MultiStepQuestionnaire

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
                    "op": "standard_io/interactive:AskChoice",
                    "inputs": {"question": "Choose one", "options_csv": "foo, woo"},
                },
                "join": {
                    "op": "standard_io/text:Concat",
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


def test_template_format() -> None:
    """TemplateFormat formats strings using scalar parameters and dictionary values."""
    op = TemplateFormat()
    res1 = op.run(template="Hello {a}, welcome to {b}!", a="Alice", b="Wonderland")
    assert res1 == {"text": "Hello Alice, welcome to Wonderland!"}

    res2 = op.run(template="{greeting} {target}", values={"greeting": "Hi", "target": "World"})
    assert res2 == {"text": "Hi World"}

    res_extra = op.run(template="Project: {project}, owner: {owner}", project="PLynx", owner="Dev")
    assert res_extra == {"text": "Project: PLynx, owner: Dev"}

    with pytest.raises(KeyError):
        op.run(template="{missing_key}")


def test_math_op() -> None:
    """MathOp supports add, sub, mul, div, pow, mod and validates division by zero."""
    op = MathOp()
    assert op.run(10.5, 2.5, "add") == {"result": 13.0, "is_positive": True, "rounded": 13}
    assert op.run(5.0, 10.0, "sub") == {"result": -5.0, "is_positive": False, "rounded": -5}
    assert op.run(3.0, 4.0, "mul") == {"result": 12.0, "is_positive": True, "rounded": 12}
    assert op.run(7.0, 2.0, "div") == {"result": 3.5, "is_positive": True, "rounded": 4}
    assert op.run(2.0, 3.0, "pow") == {"result": 8.0, "is_positive": True, "rounded": 8}
    assert op.run(10.0, 3.0, "mod") == {"result": 1.0, "is_positive": True, "rounded": 1}

    with pytest.raises(ZeroDivisionError):
        op.run(10.0, 0.0, "div")

    with pytest.raises(ZeroDivisionError):
        op.run(10.0, 0.0, "mod")

    with pytest.raises(ValueError):
        op.run(10.0, 2.0, "unknown")  # type: ignore[arg-type]


def test_json_extract(tmp_path: Path) -> None:
    """JsonExtract extracts nested keys, array items, or whole JSON trees."""
    op = JsonExtract()
    data = {
        "user": {
            "profile": {
                "name": "Charlie",
                "tags": ["admin", "dev"],
                "active": True,
                "score": 42,
                "extra": None,
            }
        }
    }

    res = op.run(json_data=data, key="user.profile.name")
    assert res == {"value_str": "Charlie", "value_json": {"value": "Charlie"}, "found": True}

    res_idx = op.run(json_data=data, key="user.profile.tags.0")
    assert res_idx == {"value_str": "admin", "value_json": {"value": "admin"}, "found": True}

    res_bool = op.run(json_data=data, key="user.profile.active")
    assert res_bool == {"value_str": "true", "value_json": {"value": True}, "found": True}

    res_int = op.run(json_data=data, key="user.profile.score")
    assert res_int == {"value_str": "42", "value_json": {"value": 42}, "found": True}

    res_null = op.run(json_data=data, key="user.profile.extra")
    assert res_null == {"value_str": "null", "value_json": {"value": None}, "found": True}

    res_missing = op.run(json_data=data, key="user.nonexistent", default="N/A")
    assert res_missing == {"value_str": "N/A", "value_json": {}, "found": False}

    res_root = op.run(json_data=data, key="")
    assert res_root["found"] is True
    assert res_root["value_json"] == data

    # Test file input
    json_path = tmp_path / "sample.json"
    json_path.write_text(json.dumps({"city": "Tokyo", "population": 14000000}), encoding="utf-8")
    res_file = op.run(json_file=json_path, key="city")
    assert res_file == {"value_str": "Tokyo", "value_json": {"value": "Tokyo"}, "found": True}


def test_json_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JsonMerge combines two dicts and writes the resulting JSON file."""
    monkeypatch.chdir(tmp_path)
    op = JsonMerge()
    res = op.run(a={"x": 1, "y": 2}, b={"y": 3, "z": 4}, output_filename="merged.json")
    assert res["merged"] == {"x": 1, "y": 3, "z": 4}
    out_file = Path(res["file"])
    assert out_file.is_file()
    assert json.loads(out_file.read_text(encoding="utf-8")) == {"x": 1, "y": 3, "z": 4}

    with pytest.raises(ValueError, match="single relative file name"):
        op.run(a={}, b={}, output_filename="../invalid.json")


def test_csv_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CsvSummary extracts stats and generates summary JSON and Markdown."""
    monkeypatch.chdir(tmp_path)
    csv_file = tmp_path / "scores.csv"
    csv_file.write_text("id,name,score\n1,Alice,95\n2,Bob,88\n3,Charlie,92\n", encoding="utf-8")

    op = CsvSummary()
    res = op.run(csv_file=csv_file)
    assert res["row_count"] == 3
    assert res["column_count"] == 3
    assert res["column_names"] == ["id", "name", "score"]

    stats_file = Path(res["stats_json"])
    assert stats_file.is_file()
    assert json.loads(stats_file.read_text(encoding="utf-8")) == {
        "row_count": 3,
        "column_count": 3,
        "column_names": ["id", "name", "score"],
    }

    md_file = Path(res["summary_md"])
    assert md_file.is_file()
    md_text = md_file.read_text(encoding="utf-8")
    assert "# CSV Summary" in md_text
    assert "Row count**: 3" in md_text
    assert "`score`" in md_text


def test_list_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ListDirectory lists files, handles recursive search and glob patterns."""
    monkeypatch.chdir(tmp_path)
    test_dir = tmp_path / "dataset"
    test_dir.mkdir()
    (test_dir / "a.txt").write_text("A", encoding="utf-8")
    sub = test_dir / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("B", encoding="utf-8")
    (sub / "c.log").write_text("C", encoding="utf-8")

    op = ListDirectory()
    res_rec = op.run(directory=test_dir, recursive=True, pattern="*")
    assert res_rec["file_count"] == 3
    assert set(res_rec["filenames"]) == {"a.txt", "sub/b.txt", "sub/c.log"}
    manifest_file = Path(res_rec["manifest"])
    assert manifest_file.is_file()

    res_pat = op.run(directory=test_dir, recursive=True, pattern="*.txt")
    assert res_pat["file_count"] == 2
    assert set(res_pat["filenames"]) == {"a.txt", "sub/b.txt"}

    res_nonrec = op.run(directory=test_dir, recursive=False)
    assert res_nonrec["file_count"] == 1
    assert res_nonrec["filenames"] == ["a.txt"]


def test_bundle_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BundleDirectory groups files into an output folder, handling collisions and missing files."""
    monkeypatch.chdir(tmp_path)
    f1 = tmp_path / "item1.txt"
    f1.write_text("1", encoding="utf-8")
    f2 = tmp_path / "item2.txt"
    f2.write_text("2", encoding="utf-8")

    op = BundleDirectory()
    res = op.run(file_a=f1, file_b=f2, bundle_name="packaged")
    assert res["file_count"] == 2
    bundle_dir = Path(res["bundle"])
    assert bundle_dir.is_dir()
    assert (bundle_dir / "item1.txt").is_file()
    assert (bundle_dir / "item2.txt").is_file()

    # Missing file raises FileNotFoundError
    with pytest.raises(FileNotFoundError, match="not found"):
        op.run(f1=tmp_path / "nonexistent.txt")

    # Basename collision resolves cleanly without overwriting
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "same.txt").write_text("from d1", encoding="utf-8")
    (d2 / "same.txt").write_text("from d2", encoding="utf-8")
    res_coll = op.run(bundle_name="coll_bundle", first=d1 / "same.txt", second=d2 / "same.txt")
    assert res_coll["file_count"] == 2
    coll_dir = Path(res_coll["bundle"])
    assert (coll_dir / "same.txt").is_file()
    assert (coll_dir / "same_1.txt").is_file()
    assert (coll_dir / "same.txt").read_text(encoding="utf-8") == "from d1"
    assert (coll_dir / "same_1.txt").read_text(encoding="utf-8") == "from d2"

    with pytest.raises(ValueError, match="single relative folder name"):
        op.run(bundle_name="/root/escape")


def test_markdown_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MarkdownReport creates a formatted Markdown report document."""
    monkeypatch.chdir(tmp_path)
    op = MarkdownReport()
    res = op.run(
        title="Execution Report",
        body="All tasks passed.",
        metrics={"duration_sec": 4.5, "passed": True},
        filename="custom_report.md",
    )
    report_file = Path(res["report"])
    assert report_file.is_file()
    content = report_file.read_text(encoding="utf-8")
    assert "# Execution Report" in content
    assert "All tasks passed." in content
    assert "- **duration_sec**: 4.5" in content
    assert "- **passed**: True" in content


def test_ask_choice_unit() -> None:
    """AskChoice presents questions and returns chosen option or freeform response."""
    op = AskChoice()
    with pytest.raises(CheckpointInterrupt) as excinfo, checkpoint_context(answers={}):
        op.run(question="Select color", options_csv="Red, Green, Blue", allow_freeform=False)

    cp = excinfo.value.manifest
    assert cp.options == ["Red", "Green", "Blue"]
    assert cp.allow_freeform is False

    with checkpoint_context(answers={"cp_0": "Green"}):
        res = op.run(question="Select color", options_csv="Red, Green, Blue")
        assert res == {"choice": "Green"}


def test_multi_step_questionnaire_unit() -> None:
    """MultiStepQuestionnaire iterates through 3 sequential checkpoints with idempotent replay."""
    op = MultiStepQuestionnaire()

    # Step 1: cp_0 role selection
    with pytest.raises(CheckpointInterrupt) as exc0, checkpoint_context(answers={}):
        op.run()
    cp0 = exc0.value.manifest
    assert cp0.checkpoint_id == "cp_0"
    assert cp0.options == ["Data Scientist", "Software Engineer", "DevOps Engineer", "Researcher"]
    assert cp0.allow_freeform is False

    # Step 2: cp_1 freeform goal
    with (
        pytest.raises(CheckpointInterrupt) as exc1,
        checkpoint_context(answers={"cp_0": "Data Scientist"}),
    ):
        op.run()
    cp1 = exc1.value.manifest
    assert cp1.checkpoint_id == "cp_1"
    assert cp1.allow_freeform is True

    # Step 3: cp_2 environment selection
    with (
        pytest.raises(CheckpointInterrupt) as exc2,
        checkpoint_context(answers={"cp_0": "Data Scientist", "cp_1": "Train neural network"}),
    ):
        op.run()
    cp2 = exc2.value.manifest
    assert cp2.checkpoint_id == "cp_2"
    assert cp2.options == ["Local Machine", "Staging Cluster", "Production Cloud"]
    assert cp2.allow_freeform is False

    # Completion with all answers
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with (
        redirect_stdout(stdout_buf),
        redirect_stderr(stderr_buf),
        checkpoint_context(
            answers={
                "cp_0": "Data Scientist",
                "cp_1": "Train neural network",
                "cp_2": "Production Cloud",
            }
        ),
    ):
        res = op.run()

    assert res["step1_answer"] == "Data Scientist"
    assert res["step2_answer"] == "Train neural network"
    assert res["step3_answer"] == "Production Cloud"
    expected_summary = (
        "Role: Data Scientist | Goal: Train neural network | Environment: Production Cloud"
    )
    assert expected_summary in res["summary"]
    assert "[STDOUT] Step 1 completed. Selected role: Data Scientist" in stdout_buf.getvalue()
    assert "[STDERR] [MultiStepQuestionnaire] Commencing step 1" in stderr_buf.getvalue()


def test_data_and_files_end_to_end_pipeline(tmp_path: Path) -> None:
    """End-to-end pipeline executing data and file ops."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "data_and_files_pipeline",
            "nodes": {
                "format": {
                    "op": "standard_io/data:TemplateFormat",
                    "inputs": {"template": "Pipeline project {a}", "a": "Alpha"},
                },
                "math": {
                    "op": "standard_io/data:MathOp",
                    "inputs": {"a": 20.0, "b": 4.0, "operation": "div"},
                },
                "merge": {
                    "op": "standard_io/data:JsonMerge",
                    "inputs": {
                        "a": {"status": "ok"},
                        "b": {"priority": 1},
                        "output_filename": "config.json",
                    },
                },
                "report": {
                    "op": "standard_io/files:MarkdownReport",
                    "inputs": {
                        "title": "$format.text",
                        "body": "Pipeline completed cleanly.",
                        "metrics": {"ratio": "$math.result"},
                        "filename": "summary.md",
                    },
                },
                "bundle": {
                    "op": "standard_io/files:BundleDirectory",
                    "inputs": {
                        "file_a": "$merge.file",
                        "file_b": "$report.report",
                        "bundle_name": "artifacts",
                    },
                },
                "list_dir": {
                    "op": "standard_io/files:ListDirectory",
                    "inputs": {
                        "directory": "$bundle.bundle",
                        "recursive": True,
                    },
                },
            },
        }
    )

    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)

    state = asyncio.run(scheduler.run(wf))
    assert state.status == RunStatus.SUCCESS

    for nid in ("format", "math", "merge", "report", "bundle", "list_dir"):
        assert state.nodes[nid].status == NodeStatus.SUCCESS

    # Verify math result
    math_raw = (store.node_dir(state.id, "math") / "result.json").read_text(encoding="utf-8")
    math_res = ResultManifest.from_json(math_raw)
    assert math_res.outputs["result"] == ScalarValue(value=5.0)
    assert math_res.outputs["is_positive"] == ScalarValue(value=True)

    # Verify bundle output is a directory
    bundle_raw = (store.node_dir(state.id, "bundle") / "result.json").read_text(encoding="utf-8")
    bundle_res = ResultManifest.from_json(bundle_raw)
    assert isinstance(bundle_res.outputs["bundle"], ResultDirectoryValue)

    # Verify list_dir inspected the bundle directory
    list_raw = (store.node_dir(state.id, "list_dir") / "result.json").read_text(encoding="utf-8")
    list_res = ResultManifest.from_json(list_raw)
    assert list_res.outputs["file_count"] == ScalarValue(value=2)
    assert isinstance(list_res.outputs["manifest"], ResultFileValue)


def test_ask_choice_scheduler_replay(tmp_path: Path) -> None:
    """Scheduler executes AskChoice with checkpoint pausing and answer resumption."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "interactive_choice",
            "nodes": {
                "choice": {
                    "op": "standard_io/interactive:AskChoice",
                    "inputs": {"question": "Choose target", "options_csv": "dev, staging, prod"},
                },
            },
        }
    )

    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)

    # Attempt 1: No answers -> pauses at cp_0
    state1 = asyncio.run(scheduler.run(wf, options=SchedulerOptions(non_interactive=True)))
    assert state1.status == RunStatus.WAITING_FOR_USER
    assert state1.nodes["choice"].status == NodeStatus.WAITING_FOR_USER
    assert len(state1.checkpoints) == 1
    assert state1.checkpoints[0].checkpoint_id == "cp_0"

    # Attempt 2: Answer cp_0 -> succeeds!
    state2 = asyncio.run(
        scheduler.run(
            wf,
            options=SchedulerOptions(
                answers={"choice.cp_0": "staging"},
            ),
        )
    )
    assert state2.status == RunStatus.SUCCESS
    assert state2.nodes["choice"].status == NodeStatus.SUCCESS

    outputs = OutputsManifest.from_json(
        (store.node_dir(state2.id, "choice") / "outputs.json").read_text(encoding="utf-8")
    )
    assert outputs.outputs["choice"] == ScalarValue(value="staging")
