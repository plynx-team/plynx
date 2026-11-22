"""Tests for Task 4.5: Local Ctrl-C and cross-process cancel_requested."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from plynx.api_models import NodeStatus, RunStatus, RunStatusEvent
from plynx.engine import Scheduler, SchedulerOptions
from plynx.engine.procgroup import is_pid_alive, kill_process_group
from plynx.store import RunStore
from plynx.workflow.models import Workflow

from tests.fakes import FakeExecutor

ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = ROOT / "packages" / "plynx-sdk"


def _create_tree_pack(workspace: Path, pid_file: Path) -> None:
    pack_dir = workspace / "custom_packs" / "tree_pack"
    src_dir = pack_dir / "src" / "tree_pack"
    src_dir.mkdir(parents=True)
    sdk_posix = SDK_PATH.resolve().as_posix()
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "tree-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_posix}", editable = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tree_pack"]
""",
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    pid_posix = pid_file.resolve().as_posix()
    (src_dir / "ops.py").write_text(
        f"""import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op


class SpawnTree(Op):
    \"\"\"Spawn a grandchild sleeper and wait until killed.\"\"\"

    TITLE = "Spawn tree"
    CACHEABLE = False

    class Outputs(TypedDict):
        out: str

    def run(self, seconds: int = 60) -> Outputs:
        grandchild = subprocess.Popen(
            [sys.executable, "-c", f"import time; time.sleep({{seconds}})"]
        )
        pid_path = Path("{pid_posix}")
        tmp_path = pid_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({{"child_pid": os.getpid(), "grandchild_pid": grandchild.pid}}),
            encoding="utf-8",
        )
        os.replace(tmp_path, pid_path)
        try:
            time.sleep(seconds)
        finally:
            grandchild.terminate()
        return {{"out": "done"}}
""",
        encoding="utf-8",
    )


def _write_cancel_workflow(workspace: Path) -> Path:
    wf_path = workspace / "cancel_wf.yaml"
    wf_path.write_text(
        """version: 1
name: cancel_wf
nodes:
  slow:
    op: tree_pack/ops:SpawnTree
    inputs:
      seconds: 60
  after:
    op: standard_io/demo:Echo
    inputs:
      text: $slow.out
""",
        encoding="utf-8",
    )
    return wf_path


def _wait_for_pids(pid_file: Path, *, timeout: float = 20.0) -> tuple[int, int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pid_file.is_file():
            data = json.loads(pid_file.read_text(encoding="utf-8"))
            return int(data["child_pid"]), int(data["grandchild_pid"])
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for child/grandchild PID file: {pid_file}")


def _wait_pid_dead(pid: int, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.05)
    return not is_pid_alive(pid)


def test_cross_process_cancel_kills_process_tree_and_exits_130(tmp_path: Path) -> None:
    """A second process cancels a running workflow; no child or grandchild survives; exit 130."""
    pid_file = tmp_path / "pids.json"
    _create_tree_pack(tmp_path, pid_file)
    wf_path = _write_cancel_workflow(tmp_path)

    owner_proc = subprocess.Popen(
        [sys.executable, "-m", "plynx.cli", "run", str(wf_path)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = 0
    grandchild_pid = 0
    try:
        child_pid, grandchild_pid = _wait_for_pids(pid_file)
        assert is_pid_alive(child_pid)
        assert is_pid_alive(grandchild_pid)

        store = RunStore(tmp_path)
        runs = store.list_runs()
        assert len(runs) == 1
        run_id = runs[0].id

        # Second process requests cancellation via SQLite.
        canceler = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "from plynx.store import RunStore; "
                    f"RunStore(Path({str(tmp_path)!r})).request_cancel({run_id!r})"
                ),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert canceler.returncode == 0, canceler.stderr

        stdout, stderr = owner_proc.communicate(timeout=15)
        assert owner_proc.returncode == 130, f"stdout={stdout}\nstderr={stderr}"
        assert _wait_pid_dead(child_pid), f"child PID {child_pid} survived cancel"
        assert _wait_pid_dead(grandchild_pid), f"grandchild PID {grandchild_pid} survived cancel"

        state = store.get_run_state(run_id)
        assert state is not None
        assert state.status == RunStatus.CANCELED
        assert state.cancel_requested is True
        assert state.nodes["slow"].status == NodeStatus.CANCELED
        assert state.nodes["after"].status == NodeStatus.CANCELED

        events = store.event_log(run_id).read_after(0)
        assert isinstance(events[-1], RunStatusEvent)
        assert events[-1].data.status == RunStatus.CANCELED
    finally:
        if owner_proc.poll() is None:
            owner_proc.kill()
            owner_proc.wait()
        if child_pid > 0:
            kill_process_group(child_pid)
        if grandchild_pid > 0:
            kill_process_group(grandchild_pid)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT process signaling is POSIX-specific")
def test_local_ctrl_c_sigint_kills_process_tree_and_exits_130(tmp_path: Path) -> None:
    """Local Ctrl-C (SIGINT) cancels the run, kills child & grandchild, and exits 130."""
    pid_file = tmp_path / "pids_sigint.json"
    _create_tree_pack(tmp_path, pid_file)
    wf_path = _write_cancel_workflow(tmp_path)

    owner_proc = subprocess.Popen(
        [sys.executable, "-m", "plynx.cli", "run", str(wf_path)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    child_pid = 0
    grandchild_pid = 0
    try:
        child_pid, grandchild_pid = _wait_for_pids(pid_file)
        assert is_pid_alive(child_pid)
        assert is_pid_alive(grandchild_pid)

        os.kill(owner_proc.pid, signal.SIGINT)
        stdout, stderr = owner_proc.communicate(timeout=15)
        assert owner_proc.returncode == 130, f"stdout={stdout}\nstderr={stderr}"
        assert _wait_pid_dead(child_pid), f"child PID {child_pid} survived SIGINT"
        assert _wait_pid_dead(grandchild_pid), f"grandchild PID {grandchild_pid} survived SIGINT"

        store = RunStore(tmp_path)
        run_id = store.list_runs()[0].id
        state = store.get_run_state(run_id)
        assert state is not None
        assert state.status == RunStatus.CANCELED
        assert state.nodes["slow"].status == NodeStatus.CANCELED
        assert state.nodes["after"].status == NodeStatus.CANCELED
    finally:
        if owner_proc.poll() is None:
            owner_proc.kill()
            owner_proc.wait()
        if child_pid > 0:
            kill_process_group(child_pid)
        if grandchild_pid > 0:
            kill_process_group(grandchild_pid)


def test_cancel_while_waiting_on_checkpoint_transitions_to_canceled(tmp_path: Path) -> None:
    """Cross-process cancel_requested wakes a run waiting on an open checkpoint."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "cancel_cp",
            "nodes": {
                "pick": {
                    "op": "standard_io/demo:AskFooOrWoo",
                    "inputs": {"prompt": "foo or woo?"},
                },
                "echo": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {"text": "$pick.choice"},
                },
            },
        }
    )
    store = RunStore(tmp_path)
    scheduler = Scheduler(store, FakeExecutor())

    async def _run_and_cancel() -> str:
        task = asyncio.create_task(
            scheduler.run(
                wf,
                options=SchedulerOptions(no_cache=True, poll_interval=0.01),
            )
        )
        run_id: str | None = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            runs = store.list_runs()
            if runs:
                run_id = runs[0].id
                state = store.get_run_state(run_id)
                if state is not None and state.status == RunStatus.WAITING_FOR_USER:
                    store.request_cancel(run_id)
                    break
            await asyncio.sleep(0.01)

        final_state = await task
        assert final_state.status == RunStatus.CANCELED
        assert final_state.nodes["pick"].status == NodeStatus.CANCELED
        assert final_state.nodes["echo"].status == NodeStatus.CANCELED
        assert run_id is not None
        return run_id

    asyncio.run(_run_and_cancel())
