"""Tests for Task 4.2: CLI interactive prompts, --answers, --answer, --non-interactive, CI=true."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from plynx.api_models import NodeStatus, RunStatus
from plynx.cli.interaction import parse_checkpoint_input
from plynx.store import RunStore
from plynx_sdk.protocol import CheckpointManifest, ResultManifest, ScalarValue

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"
SDK_PATH = ROOT / "packages" / "plynx-sdk"


def _clean_interactive_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CI", None)
    return env


def _run_cli(
    cwd: Path,
    *args: str,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "plynx.cli", *args],
        cwd=cwd,
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env if env is not None else _clean_interactive_env(),
        check=False,
    )


def _create_freeform_pack(workspace: Path) -> None:
    pack_dir = workspace / "custom_packs" / "prompt_pack"
    src_dir = pack_dir / "src" / "prompt_pack"
    src_dir.mkdir(parents=True)
    sdk_posix = SDK_PATH.resolve().as_posix()
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "prompt-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_posix}", editable = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/prompt_pack"]
""",
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(
        """from typing import TypedDict
from plynx_sdk import Op


class AskFreeform(Op):
    \"\"\"Ask a freeform question.\"\"\"

    TITLE = "Ask freeform"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self, question: str = "Enter note:") -> Outputs:
        ans = self.checkpoint(question, options=["alpha", "beta"], allow_freeform=True)
        return {"text": ans}
""",
        encoding="utf-8",
    )


def test_parse_checkpoint_input_options_and_freeform() -> None:
    """parse_checkpoint_input handles [1-N], exact option text, invalid input, and freeform."""
    strict_cp = CheckpointManifest(
        checkpoint_id="cp_0",
        question="foo or woo?",
        options=["foo", "woo"],
        allow_freeform=False,
    )
    assert parse_checkpoint_input("1\n", strict_cp) == (True, "foo", None)
    assert parse_checkpoint_input("2\n", strict_cp) == (True, "woo", None)
    assert parse_checkpoint_input("foo\n", strict_cp) == (True, "foo", None)
    ok, ans, err = parse_checkpoint_input("3\n", strict_cp)
    assert not ok and ans is None and err is not None
    ok, ans, err = parse_checkpoint_input("other\n", strict_cp)
    assert not ok and ans is None and err is not None

    freeform_opts_cp = CheckpointManifest(
        checkpoint_id="cp_0",
        question="pick or type",
        options=["a", "b"],
        allow_freeform=True,
    )
    assert parse_checkpoint_input("2\n", freeform_opts_cp) == (True, "b", None)
    assert parse_checkpoint_input("custom text\n", freeform_opts_cp) == (True, "custom text", None)

    plain_cp = CheckpointManifest(
        checkpoint_id="cp_0",
        question="say anything",
        options=None,
        allow_freeform=True,
    )
    assert parse_checkpoint_input("hello world\n", plain_cp) == (True, "hello world", None)


def test_piped_stdin_drives_numbered_interactive_prompt(tmp_path: Path) -> None:
    """Piped stdin drives [1-N] prompt (including retry on invalid input) against real ops."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    # First enter invalid selection '9', then '2' (woo).
    res = _run_cli(tmp_path, "run", str(wf_path), stdin_text="9\n2\n")
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "[pick.cp_0] foo or woo?" in res.stdout
    assert "[1-2]" in res.stdout
    assert "Invalid selection" in res.stderr

    store = RunStore(tmp_path)
    runs = store.list_runs()
    assert len(runs) == 1
    run_id = runs[0].id
    state = store.get_run_state(run_id)
    assert state is not None
    assert state.status == RunStatus.SUCCESS
    assert state.nodes["pick"].status == NodeStatus.SUCCESS
    assert state.nodes["echo"].status == NodeStatus.SUCCESS

    echo_res = ResultManifest.from_json(
        (store.node_dir(run_id, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert echo_res.outputs["text"] == ScalarValue(value="woo")


def test_piped_stdin_drives_freeform_prompt(tmp_path: Path) -> None:
    """Piped stdin supplies freeform text when allow_freeform=True."""
    _create_freeform_pack(tmp_path)
    wf_path = tmp_path / "freeform.yaml"
    wf_path.write_text(
        """version: 1
name: freeform_test
nodes:
  ask:
    op: prompt_pack/ops:AskFreeform
    inputs:
      question: "Enter note:"
  echo:
    op: standard_io/demo:Echo
    inputs:
      text: $ask.text
""",
        encoding="utf-8",
    )

    res = _run_cli(tmp_path, "run", str(wf_path), stdin_text="custom freeform answer\n")
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "[ask.cp_0] Enter note:" in res.stdout

    store = RunStore(tmp_path)
    run_id = store.list_runs()[0].id
    echo_res = ResultManifest.from_json(
        (store.node_dir(run_id, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert echo_res.outputs["text"] == ScalarValue(value="custom freeform answer")


def test_answers_file_and_answer_flag_override(tmp_path: Path) -> None:
    """--answers supplies JSON answers and --answer overrides individual keys."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps({"pick.cp_0": "foo"}), encoding="utf-8")

    res_file = _run_cli(tmp_path, "run", "--answers", str(answers_path), str(wf_path))
    assert res_file.returncode == 0, res_file.stderr
    store = RunStore(tmp_path)
    run_1 = store.list_runs()[0].id
    res_1 = ResultManifest.from_json(
        (store.node_dir(run_1, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert res_1.outputs["text"] == ScalarValue(value="foo")

    res_override = _run_cli(
        tmp_path,
        "run",
        "--answers",
        str(answers_path),
        "--answer",
        "pick.cp_0=woo",
        str(wf_path),
    )
    assert res_override.returncode == 0, res_override.stderr
    run_2 = next(r.id for r in store.list_runs() if r.id != run_1)
    res_2 = ResultManifest.from_json(
        (store.node_dir(run_2, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert res_2.outputs["text"] == ScalarValue(value="woo")


def test_ci_env_triggers_non_interactive_exit_2_and_eof_pauses(tmp_path: Path) -> None:
    """CI=true exits 2 without prompting; EOF on stdin also pauses cleanly with exit 2."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    ci_env = _clean_interactive_env()
    ci_env["CI"] = "true"
    res_ci = _run_cli(tmp_path, "run", str(wf_path), env=ci_env)
    assert res_ci.returncode == 2, f"stdout={res_ci.stdout}\nstderr={res_ci.stderr}"

    res_eof = _run_cli(tmp_path, "run", str(wf_path), stdin_text="")
    assert res_eof.returncode == 2, f"stdout={res_eof.stdout}\nstderr={res_eof.stderr}"
