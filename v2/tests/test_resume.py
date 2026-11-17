"""Tests for Task 4.4: plynx resume for failed and waiting runs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from plynx.api_models import (
    CheckpointResolvedEvent,
    NodeStatus,
    RunStatus,
    StageGateStatus,
    StageResolvedEvent,
)
from plynx.store import RunOwnershipError, RunStore, StoreError
from plynx_sdk.protocol import ResultManifest, ScalarValue

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"
SDK_PATH = ROOT / "packages" / "plynx-sdk"


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CI", None)
    return env


def _run_cli(
    cwd: Path,
    *args: str,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "plynx.cli", *args],
        cwd=cwd,
        input=stdin_text,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )


def _create_resume_pack(workspace: Path, counter_file: Path) -> Path:
    pack_dir = workspace / "custom_packs" / "resume_pack"
    src_dir = pack_dir / "src" / "resume_pack"
    src_dir.mkdir(parents=True)
    sdk_posix = SDK_PATH.resolve().as_posix()
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "resume-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_posix}", editable = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/resume_pack"]
""",
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    ops_file = src_dir / "ops.py"
    counter_posix = counter_file.resolve().as_posix()
    ops_file.write_text(
        f"""from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op


class Stamp(Op):
    \"\"\"Non-cacheable op that logs every execution to a counter file.\"\"\"

    TITLE = "Stamp"
    CACHEABLE = False

    class Outputs(TypedDict):
        value: str

    def run(self, tag: str) -> Outputs:
        counter = Path("{counter_posix}")
        with counter.open("a", encoding="utf-8") as handle:
            handle.write(f"{{tag}}\\n")
        return {{"value": f"{{tag}}_v1"}}


class Flaky(Op):
    \"\"\"Op that initially fails until its source is fixed.\"\"\"

    TITLE = "Flaky"
    CACHEABLE = False

    class Outputs(TypedDict):
        out: str

    def run(self, text: str) -> Outputs:
        raise RuntimeError("intentional initial failure")
""",
        encoding="utf-8",
    )
    return ops_file


def test_fix_failing_node_source_and_resume_runs_only_failed_and_dependents(
    tmp_path: Path,
) -> None:
    """Fix a failing node's source, resume: only that node and its dependents run."""
    counter_file = tmp_path / "exec_log.txt"
    ops_file = _create_resume_pack(tmp_path, counter_file)
    wf_path = tmp_path / "pipeline.yaml"
    wf_path.write_text(
        """version: 1
name: resume_pipeline
nodes:
  upstream:
    op: resume_pack/ops:Stamp
    inputs:
      tag: up
  side:
    op: resume_pack/ops:Stamp
    inputs:
      tag: side
  flaky:
    op: resume_pack/ops:Flaky
    inputs:
      text: $upstream.value
  downstream:
    op: standard_io/demo:Concat
    inputs:
      a: $flaky.out
      b: $side.value
""",
        encoding="utf-8",
    )

    first = _run_cli(tmp_path, "run", str(wf_path))
    assert first.returncode == 1, f"stdout={first.stdout}\nstderr={first.stderr}"

    store = RunStore(tmp_path)
    runs = store.list_runs()
    assert len(runs) == 1
    run_id = runs[0].id
    failed_state = store.get_run_state(run_id)
    assert failed_state is not None
    assert failed_state.status == RunStatus.FAILED
    assert failed_state.nodes["upstream"].status == NodeStatus.SUCCESS
    assert failed_state.nodes["side"].status == NodeStatus.SUCCESS
    assert failed_state.nodes["flaky"].status == NodeStatus.FAILED
    assert failed_state.nodes["flaky"].attempt == 1
    assert failed_state.nodes["downstream"].status == NodeStatus.BLOCKED
    assert failed_state.nodes["downstream"].attempt == 0
    old_owner_pid = failed_state.owner_pid

    exec_lines_before = sorted(counter_file.read_text(encoding="utf-8").splitlines())
    assert exec_lines_before == ["side", "up"]

    # Fix the failing node's source file.
    fixed_src = ops_file.read_text(encoding="utf-8").replace(
        'raise RuntimeError("intentional initial failure")',
        'return {"out": text + "_fixed:"}',
    )
    ops_file.write_text(fixed_src, encoding="utf-8")

    # Resume using the run_id (in a fresh CLI subprocess that takes ownership).
    resumed = _run_cli(tmp_path, "resume", run_id)
    assert resumed.returncode == 0, f"stdout={resumed.stdout}\nstderr={resumed.stderr}"

    # Non-cacheable completed nodes ('upstream' and 'side') MUST NOT have re-run.
    exec_lines_after = sorted(counter_file.read_text(encoding="utf-8").splitlines())
    assert exec_lines_after == ["side", "up"]

    final_state = store.get_run_state(run_id)
    assert final_state is not None
    assert final_state.status == RunStatus.SUCCESS
    assert final_state.error is None
    assert final_state.owner_pid is not None
    assert final_state.owner_pid != old_owner_pid
    assert final_state.nodes["upstream"].attempt == 1
    assert final_state.nodes["side"].attempt == 1
    assert final_state.nodes["flaky"].attempt == 2
    assert final_state.nodes["flaky"].status == NodeStatus.SUCCESS
    assert final_state.nodes["downstream"].attempt == 1
    assert final_state.nodes["downstream"].status == NodeStatus.SUCCESS

    downstream_res = ResultManifest.from_json(
        (store.node_dir(run_id, "downstream") / "result.json").read_text(encoding="utf-8")
    )
    assert downstream_res.outputs["text"] == ScalarValue(value="up_v1_fixed:side_v1")

    stderr_log = (store.run_dir(run_id) / "logs" / "flaky.stderr.log").read_text(encoding="utf-8")
    assert "--- attempt 2 ---" in stderr_log


def test_resume_waiting_checkpoint_run_with_answer_and_interactive(tmp_path: Path) -> None:
    """plynx resume continues a paused checkpoint run via --answer or piped stdin."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    # 1. Pause non-interactively, then resume with --answer.
    paused = _run_cli(tmp_path, "run", "--non-interactive", str(wf_path))
    assert paused.returncode == 2
    store = RunStore(tmp_path)
    run_id = store.list_runs()[0].id
    paused_state = store.get_run_state(run_id)
    assert paused_state is not None
    assert paused_state.status == RunStatus.WAITING_FOR_USER
    assert paused_state.owner_pid is None

    resumed = _run_cli(tmp_path, "resume", run_id, "--answer", "pick.cp_0=woo")
    assert resumed.returncode == 0, f"stdout={resumed.stdout}\nstderr={resumed.stderr}"

    done_state = store.get_run_state(run_id)
    assert done_state is not None
    assert done_state.status == RunStatus.SUCCESS
    assert done_state.nodes["pick"].attempt == 2
    assert done_state.nodes["echo"].status == NodeStatus.SUCCESS

    echo_res = ResultManifest.from_json(
        (store.node_dir(run_id, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert echo_res.outputs["text"] == ScalarValue(value="woo")

    events = store.event_log(run_id).read_after(0)
    assert len([e for e in events if isinstance(e, CheckpointResolvedEvent)]) == 1

    # 2. Pause non-interactively, then resume interactively with piped stdin.
    paused_2 = _run_cli(tmp_path, "run", "--non-interactive", str(wf_path))
    assert paused_2.returncode == 2
    run_id_2 = next(r.id for r in store.list_runs() if r.id != run_id)

    resumed_2 = _run_cli(tmp_path, "resume", run_id_2, stdin_text="1\n")
    assert resumed_2.returncode == 0, f"stdout={resumed_2.stdout}\nstderr={resumed_2.stderr}"
    echo_res_2 = ResultManifest.from_json(
        (store.node_dir(run_id_2, "echo") / "result.json").read_text(encoding="utf-8")
    )
    assert echo_res_2.outputs["text"] == ScalarValue(value="foo")


def test_resume_waiting_stage_gate_does_not_rerun_stage1(tmp_path: Path) -> None:
    """Resuming a run paused at a stage gate keeps stage 1 outputs and approves to run stage 2."""
    wf_path = tmp_path / "gated.yaml"
    wf_path.write_text(
        """version: 1
name: resume_gated
stages:
  s1:
    title: "Stage 1"
    require_approval: true
  s2:
    title: "Stage 2"
nodes:
  first:
    op: standard_io/demo:Echo
    stage: s1
    inputs:
      text: stage1_done
  second:
    op: standard_io/demo:Concat
    stage: s2
    inputs:
      a: $first.text
      b: _stage2
""",
        encoding="utf-8",
    )

    paused = _run_cli(tmp_path, "run", "--non-interactive", "--no-cache", str(wf_path))
    assert paused.returncode == 2

    store = RunStore(tmp_path)
    run_id = store.list_runs()[0].id
    resumed = _run_cli(tmp_path, "resume", run_id, stdin_text="y\n")
    assert resumed.returncode == 0, f"stdout={resumed.stdout}\nstderr={resumed.stderr}"

    final_state = store.get_run_state(run_id)
    assert final_state is not None
    assert final_state.status == RunStatus.SUCCESS
    assert final_state.nodes["first"].attempt == 1
    assert final_state.nodes["second"].attempt == 1
    assert final_state.stage_gates["s1"].status == StageGateStatus.APPROVED

    events = store.event_log(run_id).read_after(0)
    assert len([e for e in events if isinstance(e, StageResolvedEvent)]) == 1


def test_claim_run_rejects_live_other_owner_and_succeeded_run(tmp_path: Path) -> None:
    """claim_run_for_resume refuses runs owned by another live process or already SUCCESS."""
    store = RunStore(tmp_path)
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        running_id = store.create_run(
            workflow_path="wf.yaml",
            workflow_bytes=b"version: 1\n",
            node_ids=["a"],
            owner_pid=sleeper.pid,
            status=RunStatus.RUNNING,
        )
        with pytest.raises(RunOwnershipError):
            store.claim_run_for_resume(running_id, owner_pid=os.getpid())
    finally:
        sleeper.kill()
        sleeper.wait()

    done_id = store.create_run(
        workflow_path="wf.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["a"],
        status=RunStatus.SUCCESS,
    )
    with pytest.raises(StoreError):
        store.claim_run_for_resume(done_id)
