"""Click CLI entry point for ``plynx`` (PROTOCOL.md section 11)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from plynx.workflow.validator import validate_workflow_file


@click.group()
def main() -> None:
    """PLynx v2 local-first workflow engine."""


@main.command("validate")
@click.argument("workflow", type=click.Path(path_type=Path))
def validate_cmd(workflow: Path) -> None:
    """Statically validate a workflow YAML file without executing any node code."""
    if not workflow.is_file():
        click.echo(f"error: workflow file not found: {workflow}", err=True)
        sys.exit(1)
    issues = validate_workflow_file(workflow)
    errors = [issue for issue in issues if issue.severity == "error"]
    for issue in issues:
        click.echo(f"{issue.severity}: {issue.message}", err=True)
    if errors:
        sys.exit(1)
    click.echo(f"OK: {workflow}")
