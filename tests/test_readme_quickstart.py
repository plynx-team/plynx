"""Tests verifying that quickstart README commands work verbatim (Task 7.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.cli import main as cli_main

ROOT = Path(__file__).resolve().parent.parent


def test_readme_quickstart_commands_work_verbatim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that each command listed in README.md executes cleanly."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # 1. plynx --help
    help_res = runner.invoke(cli_main, ["--help"])
    assert help_res.exit_code == 0
    assert "PLynx v2 local-first workflow engine" in help_res.output

    # 2. plynx validate examples/workflows/foo_or_woo.yaml
    wf_path = str(ROOT / "examples" / "workflows" / "foo_or_woo.yaml")
    val_res = runner.invoke(cli_main, ["validate", wf_path])
    assert val_res.exit_code == 0
    assert "OK:" in val_res.output

    # 3. plynx run --answer pick.cp_0=foo examples/workflows/foo_or_woo.yaml
    run_res = runner.invoke(
        cli_main,
        ["run", "--answer", "pick.cp_0=foo", wf_path],
    )
    assert run_res.exit_code == 0

    # 4. plynx runs
    runs_res = runner.invoke(cli_main, ["runs"])
    assert runs_res.exit_code == 0
    assert "SUCCESS" in runs_res.output

    # 5. plynx clean --days 7
    clean_res = runner.invoke(cli_main, ["clean", "--days", "7"])
    assert clean_res.exit_code == 0
    assert "Deleted" in clean_res.output
