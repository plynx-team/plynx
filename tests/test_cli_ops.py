"""Tests for ``plynx ops`` CLI command (Task 2.6)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from plynx.cli import main as cli_main

EXPECTED_STANDARD_IO_OPS = {
    "standard_io/agent:AgentPrompt",
    "standard_io/agent:StageSupervisor",
    "standard_io/interactive:AskChoice",
    "standard_io/demo:Echo",
    "standard_io/demo:ReadText",
    "standard_io/demo:WriteText",
    "standard_io/text:Concat",
}


def test_cli_ops_human_table() -> None:
    """plynx ops outputs a human-readable table listing every op in standard_io."""
    runner = CliRunner()
    result = runner.invoke(cli_main, ["ops"])
    assert result.exit_code == 0, result.output

    lines = result.output.splitlines()
    assert len(lines) >= 3
    header = lines[0]
    for col in ("NAME", "PACK", "CATEGORY", "INPUTS", "OUTPUTS", "DESCRIPTION"):
        assert col in header

    # Ensure every demo op in standard_io is listed
    output_text = result.output
    for op_id in EXPECTED_STANDARD_IO_OPS:
        op_name = op_id.split(":")[-1]
        assert op_name in output_text
        assert "standard_io" in output_text


def test_cli_ops_json() -> None:
    """plynx ops --json dumps full OpEntry schemas as valid JSON."""
    runner = CliRunner()
    result = runner.invoke(cli_main, ["ops", "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= len(EXPECTED_STANDARD_IO_OPS)

    discovered_ids = {entry["id"] for entry in data}
    for expected_id in EXPECTED_STANDARD_IO_OPS:
        assert expected_id in discovered_ids

    # Validate schema fields of each entry
    for entry in data:
        assert "id" in entry
        assert "name" in entry
        assert "pack" in entry
        assert "category" in entry
        assert "inputs" in entry
        assert "outputs" in entry
        assert "valid" in entry
        assert entry["valid"] is True


def test_cli_ops_no_ops_found(tmp_path: Path, monkeypatch: object) -> None:
    """When an isolated empty workspace has no packs, plynx ops handles it gracefully."""
    # Note: discover_builtin_packs_dirs finds repo builtin_packs in normal development,
    # so we mock discover_packs to return an empty dict to test the empty branch.
    import unittest.mock as mock

    runner = CliRunner()
    with mock.patch("plynx.cli.PackRegistry") as mock_reg_cls:
        mock_reg = mock.MagicMock()
        mock_reg.list_ops.return_value = []
        mock_reg_cls.return_value = mock_reg

        result = runner.invoke(cli_main, ["ops"])
        assert result.exit_code == 0
        assert "No operations found." in result.output
