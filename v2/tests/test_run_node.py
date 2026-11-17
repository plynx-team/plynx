"""Tests for Task 4.7: plynx run-node <node_dir> in a scratch copy without touching SQLite."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from plynx.api_models import NodeStatus, RunStatus
from plynx.store import RunStore

ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = ROOT / "packages" / "plynx-sdk"


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CI", None)
    return env


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "plynx.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )


def _create_debug_pack(workspace: Path) -> Path:
    pack_dir = workspace / "custom_packs" / "debug_pack"
    src_dir = pack_dir / "src" / "debug_pack"
    src_dir.mkdir(parents=True)
    sdk_posix = SDK_PATH.resolve().as_posix()
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "debug-pack"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_posix}", editable = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/debug_pack"]
""",
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    ops_file = src_dir / "ops.py"
    ops_file.write_text(
        """from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op


class BuggyOp(Op):
    \"\"\"Reads a file input, logs diagnostics, and initially raises.\"\"\"

    TITLE = "Buggy op"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self, src: Path) -> Outputs:
        content = src.read_text(encoding="utf-8").strip()
        print(f"debug stdout: content={content}", flush=True)
        raise ValueError(f"boom on {content}")
""",
        encoding="utf-8",
    )
    return ops_file


def _snapshot_db_bytes(workspace: Path) -> bytes:
    db_path = workspace / ".plynx" / "plynx.db"
    return db_path.read_bytes()


def test_run_node_reruns_failed_node_in_scratch_prints_traceback_and_leaves_sqlite_unchanged(
    tmp_path: Path,
) -> None:
    """plynx run-node runs a failed node in scratch, prints traceback, and leaves DB untouched."""
    ops_file = _create_debug_pack(tmp_path)
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("payload_42\n", encoding="utf-8")

    wf_path = tmp_path / "debug_wf.yaml"
    wf_path.write_text(
        """version: 1
name: debug_wf
nodes:
  boom:
    op: debug_pack/ops:BuggyOp
    inputs:
      src: sample.txt
""",
        encoding="utf-8",
    )

    run_res = _run_cli(tmp_path, "run", str(wf_path))
    assert run_res.returncode == 1

    store = RunStore(tmp_path)
    run_id = store.list_runs()[0].id
    node_dir = store.node_dir(run_id, "boom")
    events_path = store.run_dir(run_id) / "events.jsonl"
    stderr_log = store.run_dir(run_id) / "logs" / "boom.stderr.log"

    # Snapshot SQLite state, DB bytes, event log, and node directory contents before run-node.
    state_before = store.get_run_state(run_id)
    assert state_before is not None
    assert state_before.status == RunStatus.FAILED
    assert state_before.nodes["boom"].status == NodeStatus.FAILED
    assert state_before.nodes["boom"].attempt == 1
    db_sha_before = hashlib.sha256(_snapshot_db_bytes(tmp_path)).hexdigest()
    events_before = events_path.read_bytes()
    stderr_log_before = stderr_log.read_bytes()
    workdir_before = sorted(p.name for p in (node_dir / "workdir").iterdir())

    # 1. Re-run the failed node via `plynx run-node <node_dir>`: streams output & traceback.
    debug_fail = _run_cli(tmp_path, "run-node", str(node_dir))
    assert debug_fail.returncode == 1
    assert "debug stdout: content=payload_42" in debug_fail.stdout
    assert "Traceback (most recent call last):" in debug_fail.stderr
    assert "ValueError: boom on payload_42" in debug_fail.stderr

    # Verify SQLite, events.jsonl, logs, and original node_dir are completely untouched.
    assert hashlib.sha256(_snapshot_db_bytes(tmp_path)).hexdigest() == db_sha_before
    assert events_path.read_bytes() == events_before
    assert stderr_log.read_bytes() == stderr_log_before
    assert sorted(p.name for p in (node_dir / "workdir").iterdir()) == workdir_before
    assert store.get_run_state(run_id) == state_before

    # 2. Fix the op source so it writes a scratch artifact and succeeds; re-run with run-node.
    ops_file.write_text(
        """from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op


class BuggyOp(Op):
    \"\"\"Reads a file input, writes to scratch workdir, and succeeds.\"\"\"

    TITLE = "Buggy op"
    CACHEABLE = False

    class Outputs(TypedDict):
        text: str

    def run(self, src: Path) -> Outputs:
        content = src.read_text(encoding="utf-8").strip()
        Path("scratch_only.txt").write_text("ephemeral", encoding="utf-8")
        print(f"fixed stdout: {content}", flush=True)
        return {"text": f"ok:{content}"}
""",
        encoding="utf-8",
    )

    debug_ok = _run_cli(tmp_path, "run-node", str(node_dir))
    assert debug_ok.returncode == 0, f"stdout={debug_ok.stdout}\nstderr={debug_ok.stderr}"
    assert "fixed stdout: payload_42" in debug_ok.stdout

    # Original node workdir must NOT have scratch_only.txt, outputs.json, or DB changes.
    assert not (node_dir / "workdir" / "scratch_only.txt").exists()
    assert not (node_dir / "outputs.json").exists()
    assert hashlib.sha256(_snapshot_db_bytes(tmp_path)).hexdigest() == db_sha_before
    assert store.get_run_state(run_id) == state_before


def test_run_node_missing_dir_or_inputs_exits_1(tmp_path: Path) -> None:
    """plynx run-node exits 1 cleanly if directory or inputs.json is missing."""
    missing = _run_cli(tmp_path, "run-node", str(tmp_path / "does_not_exist"))
    assert missing.returncode == 1
    assert "not found" in missing.stderr

    empty_dir = tmp_path / "empty_node"
    empty_dir.mkdir()
    no_inputs = _run_cli(tmp_path, "run-node", str(empty_dir))
    assert no_inputs.returncode == 1
    assert "inputs.json" in no_inputs.stderr
