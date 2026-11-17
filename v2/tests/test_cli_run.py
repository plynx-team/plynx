"""Tests for ``plynx run`` CLI command (Task 0.8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.api_models import NodeStatus, NodeStatusEvent, RunStatus
from plynx.cli import main as cli_main
from plynx.store import RunStore
from plynx_sdk.protocol import InputsManifest, ScalarValue

from tests.test_validator import EXAMPLE_WORKFLOW, VALIDATOR_FIXTURES


def test_cli_run_foo_or_woo_exits_0_and_persists_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plynx run foo_or_woo.yaml exits 0, prints node statuses, and writes state."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["run", str(EXAMPLE_WORKFLOW)])
    assert result.exit_code == 0, result.output

    output_lines = [line.strip() for line in result.output.splitlines() if line.strip()]
    assert output_lines

    store = RunStore(tmp_path)
    runs = store.list_runs()
    assert len(runs) == 1
    run_id = runs[0].id

    state = store.get_run_state(run_id)
    assert state is not None
    assert state.status == RunStatus.SUCCESS
    assert state.nodes["pick"].status == NodeStatus.SUCCESS
    assert state.nodes["echo"].status == NodeStatus.SUCCESS

    rdir = store.run_dir(run_id)
    assert rdir.is_dir()
    assert (rdir / "run_manifest.json").is_file()
    assert (rdir / "workflow.snapshot.yaml").is_file()
    assert (rdir / "events.jsonl").is_file()

    events = store.event_log(run_id).read_after(0)
    node_event_lines = [
        f"{ev.data.node_id} {ev.data.status.value}"
        for ev in events
        if isinstance(ev, NodeStatusEvent)
    ]
    assert output_lines == node_event_lines


def test_cli_run_non_interactive_and_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--non-interactive exits 2 on checkpoint; --answer pick.cp_0=foo exits 0."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    res_pause = runner.invoke(
        cli_main,
        ["run", "--non-interactive", str(EXAMPLE_WORKFLOW)],
    )
    assert res_pause.exit_code == 2

    res_ok = runner.invoke(
        cli_main,
        ["run", "--answer", "pick.cp_0=foo", str(EXAMPLE_WORKFLOW)],
    )
    assert res_ok.exit_code == 0, res_ok.output

    store = RunStore(tmp_path)
    runs = store.list_runs()
    latest_run_id = runs[0].id
    echo_inputs_raw = (store.node_dir(latest_run_id, "echo") / "inputs.json").read_text(
        encoding="utf-8"
    )
    echo_inputs = InputsManifest.from_json(echo_inputs_raw)
    assert echo_inputs.inputs["text"] == ScalarValue(value="foo")


def test_cli_run_invalid_workflow_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plynx run exits 1 when workflow validation fails."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    bad_wf = VALIDATOR_FIXTURES / "unknown_op.yaml"
    res = runner.invoke(cli_main, ["run", str(bad_wf)])
    assert res.exit_code == 1
    assert "unknown op" in res.output
