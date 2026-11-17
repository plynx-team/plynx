"""Tests for Task 4.6: Dead owner detection (engine_died) and recovery via resume."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from plynx.api_models import NodeStatus, RunStatus, RunStatusEvent
from plynx.engine.procgroup import kill_process_group
from plynx.server import create_app
from plynx.store import RunStore
from plynx_sdk.protocol import ResultManifest, ScalarValue

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"
SDK_PATH = ROOT / "packages" / "plynx-sdk"


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CI", None)
    return env


def _create_crash_pack(
    workspace: Path,
    counter_file: Path,
    running_pid_file: Path,
    allow_finish_file: Path,
) -> None:
    pack_dir = workspace / "custom_packs" / "crash_pack"
    src_dir = pack_dir / "src" / "crash_pack"
    src_dir.mkdir(parents=True)
    sdk_posix = SDK_PATH.resolve().as_posix()
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "crash-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_posix}", editable = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/crash_pack"]
""",
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    counter_posix = counter_file.resolve().as_posix()
    running_posix = running_pid_file.resolve().as_posix()
    allow_posix = allow_finish_file.resolve().as_posix()
    (src_dir / "ops.py").write_text(
        f"""import os
import time
from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op


class FastFirst(Op):
    \"\"\"Non-cacheable first step.\"\"\"

    TITLE = "Fast first"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self, seed: str = "hello") -> Outputs:
        with Path("{counter_posix}").open("a", encoding="utf-8") as handle:
            handle.write("first\\n")
        return {{"text": seed}}


class SlowUntilAllowed(Op):
    \"\"\"Blocks until allow_finish exists; allows testing kill -9 on the owner.\"\"\"

    TITLE = "Slow until allowed"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self, text: str) -> Outputs:
        allow_path = Path("{allow_posix}")
        if not allow_path.is_file():
            pid_path = Path("{running_posix}")
            tmp = pid_path.with_suffix(".tmp")
            tmp.write_text(str(os.getpid()), encoding="utf-8")
            os.replace(tmp, pid_path)
            time.sleep(30)
        return {{"text": f"{{text}}_recovered"}}
""",
        encoding="utf-8",
    )


def test_kill_9_owner_then_plynx_runs_shows_failed_and_resume_continues(tmp_path: Path) -> None:
    """kill -9 the owner -> plynx runs marks FAILED (engine_died) -> plynx resume succeeds."""
    counter_file = tmp_path / "first_runs.txt"
    running_pid_file = tmp_path / "second_pid.txt"
    allow_finish_file = tmp_path / "allow_finish.txt"
    _create_crash_pack(tmp_path, counter_file, running_pid_file, allow_finish_file)

    wf_path = tmp_path / "crash_wf.yaml"
    wf_path.write_text(
        """version: 1
name: crash_wf
nodes:
  first:
    op: crash_pack/ops:FastFirst
    inputs:
      seed: hello
  second:
    op: crash_pack/ops:SlowUntilAllowed
    inputs:
      text: $first.text
  third:
    op: standard_io/demo:Echo
    inputs:
      text: $second.text
""",
        encoding="utf-8",
    )

    owner_proc = subprocess.Popen(
        [sys.executable, "-m", "plynx.cli", "run", str(wf_path)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_clean_env(),
    )
    child_pid = 0
    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if running_pid_file.is_file():
                child_pid = int(running_pid_file.read_text(encoding="utf-8").strip())
                break
            time.sleep(0.05)
        assert child_pid > 0, "second node never started running"

        # Abruptly kill -9 the engine owner process.
        owner_proc.kill()
        owner_proc.wait(timeout=5)
    finally:
        if owner_proc.poll() is None:
            owner_proc.kill()
            owner_proc.wait()
        if child_pid > 0:
            kill_process_group(child_pid)

    # Next `plynx runs` detects the dead owner and marks the run FAILED (engine_died).
    runs_res = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "runs"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )
    assert runs_res.returncode == 0, runs_res.stderr
    assert "FAILED" in runs_res.stdout
    assert "engine_died" in runs_res.stdout

    store = RunStore(tmp_path)
    run_id = store.list_runs()[0].id
    dead_state = store.get_run_state(run_id)
    assert dead_state is not None
    assert dead_state.status == RunStatus.FAILED
    assert dead_state.error == "engine_died"
    assert dead_state.owner_pid is None
    assert dead_state.nodes["first"].status == NodeStatus.SUCCESS
    assert dead_state.nodes["second"].status == NodeStatus.FAILED
    assert dead_state.nodes["second"].error == "engine_died"
    assert dead_state.nodes["third"].status == NodeStatus.PENDING

    # Allow second node to succeed, then resume.
    allow_finish_file.write_text("ok", encoding="utf-8")
    resume_res = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "resume", run_id],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )
    assert resume_res.returncode == 0, f"stdout={resume_res.stdout}\nstderr={resume_res.stderr}"

    # Non-cacheable 'first' must NOT have re-run on resume.
    assert counter_file.read_text(encoding="utf-8").splitlines() == ["first"]

    final_state = store.get_run_state(run_id)
    assert final_state is not None
    assert final_state.status == RunStatus.SUCCESS
    assert final_state.nodes["first"].attempt == 1
    assert final_state.nodes["second"].attempt == 2
    assert final_state.nodes["third"].status == NodeStatus.SUCCESS

    third_res = ResultManifest.from_json(
        (store.node_dir(run_id, "third") / "result.json").read_text(encoding="utf-8")
    )
    assert third_res.outputs["text"] == ScalarValue(value="hello_recovered")


def test_server_start_reconciles_dead_owner(tmp_path: Path) -> None:
    """create_app marks runs with dead owner_pid as FAILED (engine_died) on startup."""
    # Spawn and immediately finish a tiny process so we have a guaranteed dead PID.
    dead_proc = subprocess.Popen([sys.executable, "-c", "pass"])
    dead_pid = dead_proc.pid
    dead_proc.wait(timeout=5)

    store = RunStore(tmp_path)
    run_id = store.create_run(
        workflow_path="workflows/test.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        owner_pid=dead_pid,
        status=RunStatus.RUNNING,
    )
    store.update_node_status(run_id, "n1", NodeStatus.RUNNING, attempt=1)

    create_app(tmp_path)

    state = store.get_run_state(run_id)
    assert state is not None
    assert state.status == RunStatus.FAILED
    assert state.error == "engine_died"
    assert state.nodes["n1"].status == NodeStatus.FAILED
    assert state.nodes["n1"].error == "engine_died"

    events = store.event_log(run_id).read_after(0)
    run_events = [e for e in events if isinstance(e, RunStatusEvent)]
    assert run_events[-1].data.status == RunStatus.FAILED
    assert run_events[-1].data.error == "engine_died"


def test_cleanly_paused_run_stays_waiting_after_plynx_runs(tmp_path: Path) -> None:
    """A run paused via --non-interactive (exit 2) is NOT marked FAILED by dead-owner check."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    paused = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "run", "--non-interactive", str(wf_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )
    assert paused.returncode == 2

    runs_res = subprocess.run(
        [sys.executable, "-m", "plynx.cli", "runs"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )
    assert runs_res.returncode == 0
    assert "WAITING_FOR_USER" in runs_res.stdout
    assert "engine_died" not in runs_res.stdout
