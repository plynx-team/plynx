"""End-to-end skeleton test (Task 0.11): contract for all later phases."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from plynx.api_models import NodeStatus, RunStatus
from plynx.store import RunStore
from plynx_sdk.protocol import InputsManifest, ResultManifest, ScalarValue

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "plynx.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_skeleton_foo_or_woo_e2e(tmp_path: Path) -> None:
    """CLI subprocess: --non-interactive exits 2; --answer pick.cp_0=foo exits 0."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir(parents=True)
    wf_path = workflows_dir / "foo_or_woo.yaml"
    shutil.copy(EXAMPLE_WORKFLOW, wf_path)

    # 1. With --non-interactive, the checkpoint pauses the run and exits with code 2.
    paused = _run_cli(tmp_path, "run", "--non-interactive", str(wf_path))
    assert paused.returncode == 2, f"stdout={paused.stdout}\nstderr={paused.stderr}"

    store = RunStore(tmp_path)
    runs_after_pause = store.list_runs()
    assert len(runs_after_pause) == 1
    paused_state = store.get_run_state(runs_after_pause[0].id)
    assert paused_state is not None
    assert paused_state.status == RunStatus.WAITING_FOR_USER
    assert paused_state.nodes["pick"].status == NodeStatus.WAITING_FOR_USER
    assert paused_state.nodes["echo"].status == NodeStatus.PENDING
    assert len(paused_state.checkpoints) == 1
    assert paused_state.checkpoints[0].node_id == "pick"
    assert paused_state.checkpoints[0].checkpoint_id == "cp_0"

    # 2. With --answer pick.cp_0=foo, the run exits 0 and the echo node receives "foo".
    completed = _run_cli(tmp_path, "run", "--answer", "pick.cp_0=foo", str(wf_path))
    assert completed.returncode == 0, f"stdout={completed.stdout}\nstderr={completed.stderr}"

    runs_after_done = store.list_runs()
    assert len(runs_after_done) == 2
    completed_run_id = next(r.id for r in runs_after_done if r.id != paused_state.id)
    completed_state = store.get_run_state(completed_run_id)
    assert completed_state is not None
    assert completed_state.status == RunStatus.SUCCESS
    assert completed_state.nodes["pick"].status == NodeStatus.SUCCESS
    assert completed_state.nodes["echo"].status == NodeStatus.SUCCESS

    echo_dir = store.node_dir(completed_run_id, "echo")
    echo_inputs = InputsManifest.from_json((echo_dir / "inputs.json").read_text(encoding="utf-8"))
    assert echo_inputs.inputs["text"] == ScalarValue(value="foo")

    echo_result = ResultManifest.from_json((echo_dir / "result.json").read_text(encoding="utf-8"))
    assert echo_result.outputs["text"] == ScalarValue(value="foo")
