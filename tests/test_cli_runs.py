"""Tests for Task 4.8: plynx runs and unique/ambiguous run ID prefix resolution."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.api_models import RunStatus
from plynx.cli import main as cli_main
from plynx.store import RunNotFoundError, RunStore

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_WORKFLOW = ROOT / "examples" / "workflows" / "foo_or_woo.yaml"


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CI", None)
    return env


def test_plynx_runs_lists_newest_first_and_respects_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plynx runs lists runs newest-first and honors --limit."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    empty_res = runner.invoke(cli_main, ["runs"])
    assert empty_res.exit_code == 0
    assert "No runs found." in empty_res.output

    store = RunStore(tmp_path)
    store.create_run(
        workflow_path="workflows/a.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        run_id="20261116_100000_aaaaaa",
        created_at=1000.0,
        status=RunStatus.SUCCESS,
    )
    store.create_run(
        workflow_path="workflows/b.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        run_id="20261116_110000_bbbbbb",
        created_at=2000.0,
        status=RunStatus.FAILED,
    )
    store.create_run(
        workflow_path="workflows/c.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        run_id="20261116_120000_cccccc",
        created_at=3000.0,
        status=RunStatus.SUCCESS,
    )

    all_res = runner.invoke(cli_main, ["runs"])
    assert all_res.exit_code == 0, all_res.output
    lines = all_res.output.splitlines()
    # Newest first: c -> b -> a
    pos_c = next(i for i, ln in enumerate(lines) if "20261116_120000_cccccc" in ln)
    pos_b = next(i for i, ln in enumerate(lines) if "20261116_110000_bbbbbb" in ln)
    pos_a = next(i for i, ln in enumerate(lines) if "20261116_100000_aaaaaa" in ln)
    assert pos_c < pos_b < pos_a

    lim_res = runner.invoke(cli_main, ["runs", "--limit", "2"])
    assert lim_res.exit_code == 0, lim_res.output
    assert "20261116_120000_cccccc" in lim_res.output
    assert "20261116_110000_bbbbbb" in lim_res.output
    assert "20261116_100000_aaaaaa" not in lim_res.output


def test_prefix_resolution_unique_and_ambiguous_in_runs_and_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unique prefix resolves; ambiguous prefix lists candidates and exits 1."""
    monkeypatch.chdir(tmp_path)
    store = RunStore(tmp_path)
    wf_bytes = EXAMPLE_WORKFLOW.read_bytes()

    r1 = store.create_run(
        workflow_path="workflows/foo_or_woo.yaml",
        workflow_bytes=wf_bytes,
        node_ids=["pick", "echo"],
        run_id="20261117_120000_aa1111",
        status=RunStatus.WAITING_FOR_USER,
        owner_pid=None,
    )
    store.release_ownership(r1)
    r2 = store.create_run(
        workflow_path="workflows/foo_or_woo.yaml",
        workflow_bytes=wf_bytes,
        node_ids=["pick", "echo"],
        run_id="20261117_120000_aa2222",
        status=RunStatus.FAILED,
        owner_pid=None,
    )
    store.release_ownership(r2)
    r3 = store.create_run(
        workflow_path="workflows/foo_or_woo.yaml",
        workflow_bytes=wf_bytes,
        node_ids=["pick", "echo"],
        run_id="20261117_120000_bb3333",
        status=RunStatus.SUCCESS,
        owner_pid=None,
    )
    store.release_ownership(r3)

    runner = CliRunner()

    # 1. Unique prefix resolves in `plynx runs <prefix>`.
    unique_res = runner.invoke(cli_main, ["runs", "20261117_120000_bb"])
    assert unique_res.exit_code == 0, unique_res.output
    assert r3 in unique_res.output
    assert "SUCCESS" in unique_res.output

    # 2. Ambiguous prefix lists all matching candidates and exits 1 in `plynx runs`.
    ambig_runs = runner.invoke(cli_main, ["runs", "20261117_120000_aa"])
    assert ambig_runs.exit_code == 1
    assert "ambiguous" in ambig_runs.output.lower()
    assert r1 in ambig_runs.output
    assert r2 in ambig_runs.output
    assert r3 not in ambig_runs.output

    # 3. Ambiguous prefix lists all matching candidates and exits 1 in `plynx resume`.
    ambig_resume = runner.invoke(cli_main, ["resume", "20261117_120000_aa"])
    assert ambig_resume.exit_code == 1
    assert "ambiguous" in ambig_resume.output.lower()
    assert r1 in ambig_resume.output
    assert r2 in ambig_resume.output

    # 4. Unknown prefix exits 1.
    missing_res = runner.invoke(cli_main, ["runs", "20990101_000000_ffffff"])
    assert missing_res.exit_code == 1
    assert "No run matching" in missing_res.output


def test_prefix_resolution_does_not_treat_sql_wildcards_specially(tmp_path: Path) -> None:
    """SQL LIKE wildcards ('%' and '_') in prefixes are matched literally."""
    store = RunStore(tmp_path)
    store.create_run(
        workflow_path="wf.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        run_id="20261117X120000_abcdef",
        status=RunStatus.SUCCESS,
    )
    with pytest.raises(RunNotFoundError):
        store.resolve_run_id("%")
    with pytest.raises(RunNotFoundError):
        store.resolve_run_id("20261117_")
    with pytest.raises(RunNotFoundError):
        store.resolve_run_id("")
    assert store.resolve_run_id("20261117X") == "20261117X120000_abcdef"


def test_resume_by_unique_prefix_end_to_end(tmp_path: Path) -> None:
    """A paused run can be resumed via a short unique prefix."""
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

    store = RunStore(tmp_path)
    full_id = store.list_runs()[0].id
    short_prefix = full_id[:8]

    resumed = subprocess.run(
        [
            sys.executable,
            "-m",
            "plynx.cli",
            "resume",
            short_prefix,
            "--answer",
            "pick.cp_0=foo",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_clean_env(),
        check=False,
    )
    assert resumed.returncode == 0, f"stdout={resumed.stdout}\nstderr={resumed.stderr}"
    state = store.get_run_state(full_id)
    assert state is not None
    assert state.status == RunStatus.SUCCESS
