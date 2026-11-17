"""Click CLI entry point for ``plynx`` (PROTOCOL.md section 11)."""

from __future__ import annotations

import asyncio
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any

import click
import uvicorn
from pydantic import ValidationError

from plynx.api_models import NodeStatus, RunStatus
from plynx.cli.interaction import (
    is_non_interactive,
    load_cli_answers,
    make_terminal_checkpoint_callback,
    make_terminal_stage_approval_callback,
    parse_key_value_pair,
)
from plynx.engine import Scheduler, SchedulerOptions, create_executor
from plynx.registry import Registry, find_workspace_root
from plynx.store import RunStore
from plynx.workflow.models import load_workflow
from plynx.workflow.validator import validate_workflow, validate_workflow_file


def _parse_scalar_value(raw: str) -> Any:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(parsed, (int, float, bool, list, dict)):
        return parsed
    return raw


def _relative_workflow_path(workflow: Path, workspace_root: Path) -> str:
    resolved_wf = workflow.resolve()
    try:
        rel = resolved_wf.relative_to(workspace_root.resolve())
        return rel.as_posix()
    except ValueError:
        return workflow.as_posix()


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


@main.command("run")
@click.argument("workflow", type=click.Path(path_type=Path))
@click.option("set_pairs", "--set", multiple=True, help="Set scalar input (node.port=value).")
@click.option("input_pairs", "--input", multiple=True, help="Set file/dir input (node.port=path).")
@click.option(
    "answers_file",
    "--answers",
    type=click.Path(path_type=Path),
    default=None,
    help="JSON file of checkpoint answers ({'node.cp_n': 'value'}).",
)
@click.option(
    "answer_pairs",
    "--answer",
    multiple=True,
    help="Set checkpoint answer (node.cp_n=value).",
)
@click.option("--concurrency", type=int, default=None, help="Maximum concurrent nodes.")
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Exit 2 instead of prompting on open checkpoints or stage gates.",
)
@click.option("--no-cache", is_flag=True, default=False, help="Bypass the content cache.")
def run_cmd(
    workflow: Path,
    set_pairs: tuple[str, ...],
    input_pairs: tuple[str, ...],
    answers_file: Path | None,
    answer_pairs: tuple[str, ...],
    concurrency: int | None,
    non_interactive: bool,
    no_cache: bool,
) -> None:
    """Execute a workflow in-process."""
    if not workflow.is_file():
        click.echo(f"error: workflow file not found: {workflow}", err=True)
        sys.exit(1)

    workspace_root = find_workspace_root()
    registry = Registry(workspace_root)
    try:
        wf_model = load_workflow(workflow)
    except (ValidationError, ValueError, OSError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    run_inputs: dict[str, Any] = {}
    for pair in set_pairs:
        key, raw_val = parse_key_value_pair(pair, flag="--set")
        run_inputs[key] = _parse_scalar_value(raw_val)
    for pair in input_pairs:
        key, path_val = parse_key_value_pair(pair, flag="--input")
        run_inputs[key] = path_val

    issues = validate_workflow(wf_model, registry, run_inputs=run_inputs)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    for issue in warnings:
        click.echo(f"{issue.severity}: {issue.message}", err=True)
    if errors:
        for issue in errors:
            click.echo(f"{issue.severity}: {issue.message}", err=True)
        sys.exit(1)

    try:
        answers = load_cli_answers(answers_file, answer_pairs)
    except click.ClickException as exc:
        click.echo(f"error: {exc.format_message()}", err=True)
        sys.exit(1)

    effective_non_interactive = is_non_interactive(non_interactive)

    store = RunStore(workspace_root)
    executor = create_executor(workspace_root)
    scheduler = Scheduler(store, executor, registry)

    workflow_bytes = workflow.read_bytes()
    sidecar = workflow.with_name(f".{workflow.stem}.layout.json")
    layout_bytes = sidecar.read_bytes() if sidecar.is_file() else None
    wf_rel_path = _relative_workflow_path(workflow, workspace_root)

    def _print_node_status(node_id: str, status: NodeStatus, _attempt: int) -> None:
        click.echo(f"{node_id} {status.value}")

    prompt_lock = asyncio.Lock()
    opts = SchedulerOptions(
        concurrency=concurrency,
        run_inputs=run_inputs,
        answers=answers,
        non_interactive=effective_non_interactive,
        no_cache=no_cache,
        checkpoint_callback=(
            None
            if effective_non_interactive
            else make_terminal_checkpoint_callback(prompt_lock=prompt_lock)
        ),
        stage_approval_callback=(
            None
            if effective_non_interactive
            else make_terminal_stage_approval_callback(prompt_lock=prompt_lock)
        ),
        on_node_status=_print_node_status,
    )
    final_state = asyncio.run(
        scheduler.run(
            wf_model,
            workflow_path=wf_rel_path,
            workflow_bytes=workflow_bytes,
            layout_bytes=layout_bytes,
            options=opts,
        )
    )

    if final_state.status == RunStatus.SUCCESS:
        sys.exit(0)
    if final_state.status == RunStatus.WAITING_FOR_USER:
        sys.exit(2)
    if final_state.status == RunStatus.CANCELED:
        sys.exit(130)
    sys.exit(1)


@main.command("ops")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Dump full OpEntry schemas as JSON.",
)
def ops_cmd(as_json: bool) -> None:
    """List registered operations."""
    workspace_root = find_workspace_root()
    registry = Registry(workspace_root)
    ops = registry.list_ops()

    if as_json:
        data = [op.model_dump(mode="json") for op in ops]
        click.echo(json.dumps(data, indent=2))
        return

    if not ops:
        click.echo("No operations found.")
        return

    headers = ("NAME", "PACK", "CATEGORY", "INPUTS", "OUTPUTS", "DESCRIPTION")
    rows: list[tuple[str, str, str, str, str, str]] = []
    for op in ops:
        inputs_str = ", ".join(f"{p.name}: {p.type}" for p in op.inputs) or "-"
        outputs_str = ", ".join(f"{p.name}: {p.type}" for p in op.outputs) or "-"
        rows.append(
            (
                op.name,
                op.pack,
                op.category,
                inputs_str,
                outputs_str,
                op.description or "-",
            )
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator_line = "  ".join("-" * widths[i] for i in range(len(headers)))
    click.echo(header_line)
    click.echo(separator_line)
    for row in rows:
        click.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


@main.command("clean")
@click.option(
    "--days",
    default=14,
    type=int,
    show_default=True,
    help="Delete runs older than N days.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report what would be deleted without deleting.",
)
def clean_cmd(days: int, dry_run: bool) -> None:
    """Mark-and-sweep garbage collection of old unpinned runs and unreferenced blobs."""
    from plynx.cas import clean

    workspace_root = find_workspace_root()
    res = clean(workspace_root, days=days, dry_run=dry_run)
    prefix = "[dry-run] " if dry_run else ""
    click.echo(
        f"{prefix}Deleted {res.runs_deleted} runs, {res.cache_entries_deleted} cache entries, "
        f"{res.blobs_deleted} blobs ({res.bytes_reclaimed} bytes reclaimed)."
    )


@main.command("ui")
@click.option("--port", type=int, default=8080, show_default=True, help="Local port to bind.")
@click.option("--no-browser", is_flag=True, default=False, help="Do not open a browser window.")
def ui_cmd(port: int, no_browser: bool) -> None:
    """Start the local server on 127.0.0.1 and serve the UI."""
    from plynx.server.app import create_app

    workspace_root = find_workspace_root()
    app = create_app(workspace_root)
    url = f"http://127.0.0.1:{port}"
    if not no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
