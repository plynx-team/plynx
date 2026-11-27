"""Click CLI entry point for ``plynx`` (PROTOCOL.md section 11)."""

from __future__ import annotations

import asyncio
import json
import sys
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import uvicorn
from plynx_sdk.protocol import AgentProvider
from pydantic import ValidationError

from plynx.api_models import NodeStatus, RunStatus
from plynx.cli.interaction import (
    is_non_interactive,
    load_cli_answers,
    make_terminal_checkpoint_callback,
    make_terminal_stage_approval_callback,
    make_terminal_stage_inputs_callback,
    parse_key_value_pair,
    run_with_cancel_signals,
)
from plynx.engine import LocalExecutor, Scheduler, SchedulerOptions, create_executor
from plynx.registry import OpRegistry, PackRegistry, find_workspace_root
from plynx.store import AmbiguousRunIdError, RunNotFoundError, RunStore, StoreError
from plynx.store.telemetry import compute_run_stats, detect_baseline_drift
from plynx.workflow.models import (
    Workflow,
    extract_validator_stage_id,
    load_workflow,
)
from plynx.workflow.validator import validate_workflow, validate_workflow_file


def _parse_scalar_value(raw: str) -> Any:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(parsed, (int, float, bool, list, dict)):
        return parsed
    return raw


def _lookup_port_type(workflow: Workflow, registry: OpRegistry, key: str) -> str | None:
    if "." not in key:
        return None
    node_id, _, port_name = key.partition(".")
    op_name: str | None = None
    node = workflow.nodes.get(node_id)
    if node is not None:
        op_name = node.op
    else:
        val_stage = extract_validator_stage_id(node_id)
        if val_stage is not None:
            st = workflow.stages.get(val_stage)
            if st is not None and st.validator is not None:
                op_name = st.validator.op
    if op_name is None:
        return None
    op_entry = registry.get(op_name)
    if op_entry is None:
        return None
    for port in op_entry.inputs:
        if port.name == port_name:
            return port.type
    if op_entry.allow_extra_inputs and op_entry.extra_inputs_type is not None:
        return op_entry.extra_inputs_type.type
    return None


def _relative_workflow_path(workflow: Path, workspace_root: Path) -> str:
    resolved_wf = workflow.resolve()
    try:
        rel = resolved_wf.relative_to(workspace_root.resolve())
        return rel.as_posix()
    except ValueError:
        return workflow.as_posix()


def _resolve_run_id_or_exit(store: RunStore, prefix: str) -> str:
    try:
        return store.resolve_run_id(prefix)
    except AmbiguousRunIdError as exc:
        click.echo(f"error: ambiguous run ID prefix {exc.prefix!r}; candidates:", err=True)
        for candidate in exc.candidates:
            click.echo(f"  {candidate}", err=True)
        sys.exit(1)
    except RunNotFoundError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)


@click.group()
def main() -> None:
    """PLynx v2 local-first workflow engine."""


@main.command("init")
@click.argument("target_dir", type=click.Path(path_type=Path), required=False, default=None)
def init_cmd(target_dir: Path | None) -> None:
    """Initialize a new PLynx workspace in TARGET_DIR (default: current directory)."""
    dest = (target_dir or Path.cwd()).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    (dest / ".plynx").mkdir(parents=True, exist_ok=True)

    workflows_dir = dest / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    gitkeep_wf = workflows_dir / ".gitkeep"
    if not any(workflows_dir.iterdir()):
        gitkeep_wf.touch(exist_ok=True)

    packs_dir = dest / "custom_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    (packs_dir / ".gitkeep").touch(exist_ok=True)

    cfg_file = dest / "plynx.yaml"
    if not cfg_file.is_file():
        cfg_file.write_text(
            "# PLynx workspace configuration (PROTOCOL.md section 12)\n"
            "workflows: workflows\n"
            "packs:\n"
            "  - custom_packs\n",
            encoding="utf-8",
        )

    bundled_skill = (
        Path(__file__).resolve().parent.parent / "skills" / "plynx-create-workflow" / "SKILL.md"
    )
    if bundled_skill.is_file():
        target_skill = dest / ".agents" / "skills" / "plynx-create-workflow" / "SKILL.md"
        if not target_skill.is_file():
            target_skill.parent.mkdir(parents=True, exist_ok=True)
            target_skill.write_text(bundled_skill.read_text(encoding="utf-8"), encoding="utf-8")

    git_root: Path | None = None
    for candidate in [dest, *dest.parents]:
        if (candidate / ".git").exists():
            git_root = candidate
            break

    if git_root is not None:
        target_gi = (
            dest / ".gitignore" if (dest / ".gitignore").is_file() else git_root / ".gitignore"
        )
        entry = ".plynx/"
        if target_gi.is_file():
            content = target_gi.read_text(encoding="utf-8")
            lines = [line.strip() for line in content.splitlines()]
            if entry not in lines and ".plynx" not in lines:
                separator = "" if content.endswith("\n") or not content else "\n"
                target_gi.write_text(f"{content}{separator}{entry}\n", encoding="utf-8")
        else:
            target_gi.write_text(f"{entry}\n", encoding="utf-8")

    click.echo(f"Initialized PLynx workspace in {dest}")


@main.command("validate")
@click.argument("workflow", type=click.Path(path_type=Path))
def validate_cmd(workflow: Path) -> None:
    """Statically validate a workflow YAML file without executing any node code."""
    if not workflow.is_file():
        click.echo(f"error: workflow file not found: {workflow}", err=True)
        sys.exit(1)
    workspace_root = find_workspace_root()
    registry = PackRegistry(workspace_root)
    issues = validate_workflow_file(workflow, registry=registry)
    errors = [issue for issue in issues if issue.severity == "error"]
    for issue in issues:
        click.echo(f"{issue.severity}: {issue.message}", err=True)
    if errors:
        sys.exit(1)
    click.echo(f"OK: {workflow}")


_CLI_AGENT_PROVIDER_CHOICES = tuple(p.value for p in AgentProvider if p != AgentProvider.DEFAULT)


@main.command("run")
@click.argument("workflow", type=click.Path(path_type=Path))
@click.option("set_pairs", "--set", multiple=True, help="Set scalar input (node.port=value).")
@click.option("input_pairs", "--input", multiple=True, help="Set file/dir input (node.port=path).")
@click.option(
    "answers_file",
    "--answers",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "JSON file of checkpoint answers ({'node.cp_n': 'value'} or "
        "{'node.cp_n': {'question_id': 'value'}} for batch checkpoints)."
    ),
)
@click.option(
    "answer_pairs",
    "--answer",
    multiple=True,
    help=(
        "Set checkpoint answer (node.cp_n=value, or node.cp_n.question_id=value for "
        "batch checkpoints; repeat for multi-select)."
    ),
)
@click.option("--concurrency", type=int, default=None, help="Maximum concurrent nodes.")
@click.option(
    "--agent-provider",
    type=click.Choice(_CLI_AGENT_PROVIDER_CHOICES),
    default=None,
    help="Default coding-agent CLI provider for this run.",
)
@click.option(
    "--agent-model",
    type=str,
    default=None,
    help="Default coding-agent model override for this run.",
)
@click.option(
    "--max-injected-nodes",
    type=click.IntRange(min=0),
    default=None,
    help="Maximum dynamic agent-injected nodes permitted in this run.",
)
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
    agent_provider: str | None,
    agent_model: str | None,
    max_injected_nodes: int | None,
    non_interactive: bool,
    no_cache: bool,
) -> None:
    """Execute a workflow in-process."""
    if not workflow.is_file():
        click.echo(f"error: workflow file not found: {workflow}", err=True)
        sys.exit(1)

    workspace_root = find_workspace_root()
    registry = PackRegistry(workspace_root)
    try:
        wf_model = load_workflow(workflow)
    except (ValidationError, ValueError, OSError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    run_inputs: dict[str, Any] = {}
    for pair in set_pairs:
        key, raw_val = parse_key_value_pair(pair, flag="--set")
        port_type = _lookup_port_type(wf_model, registry, key)
        if port_type == "str":
            run_inputs[key] = raw_val
        else:
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

    async def _run_workflow(cancel_event: asyncio.Event) -> Any:
        prompt_lock = asyncio.Lock()
        opts = SchedulerOptions(
            concurrency=concurrency,
            run_inputs=run_inputs,
            answers=answers,
            non_interactive=effective_non_interactive,
            no_cache=no_cache,
            agent_provider=agent_provider,
            agent_model=agent_model,
            max_injected_nodes=max_injected_nodes,
            cancel_event=cancel_event,
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
            stage_inputs_callback=(
                None
                if effective_non_interactive
                else make_terminal_stage_inputs_callback(prompt_lock=prompt_lock)
            ),
            on_node_status=_print_node_status,
        )
        return await scheduler.run(
            wf_model,
            workflow_path=wf_rel_path,
            workflow_bytes=workflow_bytes,
            layout_bytes=layout_bytes,
            options=opts,
        )

    final_state = asyncio.run(run_with_cancel_signals(_run_workflow))
    click.echo(f"run_id: {final_state.id}")

    if final_state.status == RunStatus.SUCCESS:
        sys.exit(0)
    if final_state.status == RunStatus.WAITING_FOR_USER:
        sys.exit(2)
    if final_state.status == RunStatus.CANCELED:
        sys.exit(130)
    sys.exit(1)


@main.command("resume")
@click.argument("run_id")
@click.option(
    "answers_file",
    "--answers",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "JSON file of checkpoint answers ({'node.cp_n': 'value'} or "
        "{'node.cp_n': {'question_id': 'value'}} for batch checkpoints)."
    ),
)
@click.option(
    "answer_pairs",
    "--answer",
    multiple=True,
    help=(
        "Set checkpoint answer (node.cp_n=value, or node.cp_n.question_id=value for "
        "batch checkpoints; repeat for multi-select)."
    ),
)
@click.option("--concurrency", type=int, default=None, help="Maximum concurrent nodes.")
@click.option(
    "--agent-provider",
    type=click.Choice(_CLI_AGENT_PROVIDER_CHOICES),
    default=None,
    help="Override default coding-agent CLI provider when resuming.",
)
@click.option(
    "--agent-model",
    type=str,
    default=None,
    help="Override default coding-agent model when resuming.",
)
@click.option(
    "--max-injected-nodes",
    type=click.IntRange(min=0),
    default=None,
    help="Override maximum dynamic agent-injected nodes when resuming.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Exit 2 instead of prompting on open checkpoints or stage gates.",
)
def resume_cmd(
    run_id: str,
    answers_file: Path | None,
    answer_pairs: tuple[str, ...],
    concurrency: int | None,
    agent_provider: str | None,
    agent_model: str | None,
    max_injected_nodes: int | None,
    non_interactive: bool,
) -> None:
    """Continue a failed, canceled, or waiting run, reusing completed node outputs."""
    try:
        answers = load_cli_answers(answers_file, answer_pairs)
    except click.ClickException as exc:
        click.echo(f"error: {exc.format_message()}", err=True)
        sys.exit(1)

    workspace_root = find_workspace_root()
    store = RunStore(workspace_root)
    resolved_id = _resolve_run_id_or_exit(store, run_id)

    registry = PackRegistry(workspace_root)
    executor = create_executor(workspace_root)
    scheduler = Scheduler(store, executor, registry)

    effective_non_interactive = is_non_interactive(non_interactive)

    def _print_node_status(node_id: str, status: NodeStatus, _attempt: int) -> None:
        click.echo(f"{node_id} {status.value}")

    async def _resume_workflow(cancel_event: asyncio.Event) -> Any:
        prompt_lock = asyncio.Lock()
        opts = SchedulerOptions(
            concurrency=concurrency,
            answers=answers,
            non_interactive=effective_non_interactive,
            no_cache=True,
            agent_provider=agent_provider,
            agent_model=agent_model,
            max_injected_nodes=max_injected_nodes,
            cancel_event=cancel_event,
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
            stage_inputs_callback=(
                None
                if effective_non_interactive
                else make_terminal_stage_inputs_callback(prompt_lock=prompt_lock)
            ),
            on_node_status=_print_node_status,
        )
        return await scheduler.resume(resolved_id, options=opts)

    try:
        final_state = asyncio.run(run_with_cancel_signals(_resume_workflow))
    except StoreError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    if final_state.status == RunStatus.SUCCESS:
        sys.exit(0)
    if final_state.status == RunStatus.WAITING_FOR_USER:
        sys.exit(2)
    if final_state.status == RunStatus.CANCELED:
        sys.exit(130)
    sys.exit(1)


@main.command("run-node")
@click.argument("node_dir", type=click.Path(path_type=Path))
@click.option(
    "--op",
    "op_override",
    type=str,
    default=None,
    help="Explicit op (<pack>/<module>:<Name>) if not using a run directory snapshot.",
)
def run_node_cmd(node_dir: Path, op_override: str | None) -> None:
    """Re-run one node attempt from NODE_DIR in a scratch copy without touching SQLite."""
    resolved_dir = node_dir.resolve()
    if not resolved_dir.is_dir():
        click.echo(f"error: node directory not found: {node_dir}", err=True)
        sys.exit(1)
    if not (resolved_dir / "inputs.json").is_file():
        click.echo(f"error: inputs.json not found in {node_dir}", err=True)
        sys.exit(1)

    op = op_override
    if op is None:
        if resolved_dir.parent.name == "nodes":
            snapshot_path = resolved_dir.parent.parent / "workflow.snapshot.yaml"
            if snapshot_path.is_file():
                try:
                    wf_model = load_workflow(snapshot_path)
                except (ValidationError, ValueError, OSError) as exc:
                    click.echo(f"error: failed to read workflow snapshot: {exc}", err=True)
                    sys.exit(1)
                node_spec = wf_model.nodes.get(resolved_dir.name)
                if node_spec is not None:
                    op = node_spec.op
                else:
                    val_stage = extract_validator_stage_id(resolved_dir.name)
                    if val_stage is not None:
                        st_spec = wf_model.stages.get(val_stage)
                        if st_spec is not None and st_spec.validator is not None:
                            op = st_spec.validator.op
        if op is None:
            click.echo(
                f"error: could not determine op for {node_dir}; pass --op <pack>/<module>:<Name>",
                err=True,
            )
            sys.exit(1)

    workspace_root = find_workspace_root(resolved_dir)
    executor = LocalExecutor(workspace_root)

    def _write_stdout(chunk: str) -> None:
        click.echo(chunk, nl=False)
        sys.stdout.flush()

    def _write_stderr(chunk: str) -> None:
        click.echo(chunk, nl=False, err=True)
        sys.stderr.flush()

    async def _run_scratch(cancel_event: asyncio.Event) -> int:
        return await executor.run_in_scratch(
            resolved_dir,
            op,
            cancel_event=cancel_event,
            on_stdout=_write_stdout,
            on_stderr=_write_stderr,
        )

    exit_code = asyncio.run(run_with_cancel_signals(_run_scratch))
    sys.exit(exit_code)


@main.command("runs")
@click.argument("run_id", required=False, default=None)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=20,
    show_default=True,
    help="Maximum runs to list.",
)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Report per-node execution stats, cache-hit rates, injections, and baseline drift.",
)
@click.option(
    "--workflow",
    "workflow_filter",
    type=str,
    default=None,
    help="Filter runs or stats by workflow path.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit stats or run details as JSON.",
)
def runs_cmd(
    run_id: str | None,
    limit: int,
    stats: bool,
    workflow_filter: str | None,
    as_json: bool,
) -> None:
    """List recent runs, inspect one run, or report execution telemetry (--stats)."""
    workspace_root = find_workspace_root()
    store = RunStore(workspace_root)
    store.reconcile_dead_owners()

    norm_wf_filter: str | None = None
    if workflow_filter:
        wf_cand = Path(workflow_filter)
        if wf_cand.exists():
            norm_wf_filter = _relative_workflow_path(wf_cand, workspace_root)
        else:
            norm_wf_filter = workflow_filter.replace("\\", "/")

    if stats:
        total_runs, node_stats, drift_alerts = compute_run_stats(
            store,
            workflow_path=norm_wf_filter,
        )
        if as_json:
            payload = {
                "total_runs": total_runs,
                "nodes": [item.model_dump(mode="json") for item in node_stats],
                "drift_alerts": [alert.model_dump(mode="json") for alert in drift_alerts],
            }
            click.echo(json.dumps(payload, indent=2))
            return

        if not node_stats:
            click.echo("No runs found.")
            return

        for alert in drift_alerts:
            click.echo(f"[DRIFT] {alert.message}")
        if drift_alerts:
            click.echo("")

        stat_headers = (
            "WORKFLOW",
            "NODE",
            "OP",
            "RUNS",
            "CACHE HIT%",
            "AVG DUR",
            "FAILURES",
            "INJECTED",
        )
        stat_rows: list[tuple[str, str, str, str, str, str, str, str]] = []
        for st in node_stats:
            avg_s = (
                f"{st.avg_duration_seconds:.2f}s" if st.avg_duration_seconds is not None else "-"
            )
            stat_rows.append(
                (
                    st.workflow_path,
                    st.node_id,
                    st.op or "-",
                    str(st.executions),
                    f"{st.cache_hit_rate * 100:.0f}%",
                    avg_s,
                    str(st.failures),
                    str(st.dynamic_injections),
                )
            )
        widths = [len(h) for h in stat_headers]
        for s_row in stat_rows:
            for idx, cell in enumerate(s_row):
                widths[idx] = max(widths[idx], len(cell))
        click.echo("  ".join(h.ljust(widths[i]) for i, h in enumerate(stat_headers)))
        click.echo("  ".join("-" * widths[i] for i in range(len(stat_headers))))
        for s_row in stat_rows:
            click.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(s_row)))
        return

    if run_id is not None:
        resolved_id = _resolve_run_id_or_exit(store, run_id)
        state = store.get_run_state(resolved_id)
        if state is None:
            click.echo(f"error: run {resolved_id!r} not found", err=True)
            sys.exit(1)
        if as_json:
            click.echo(json.dumps(state.model_dump(mode="json"), indent=2))
            return
        created_str = datetime.fromtimestamp(state.created_at, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"Run:      {state.id}")
        click.echo(f"Status:   {state.status.value}")
        click.echo(f"Workflow: {state.workflow_path}")
        click.echo(f"Created:  {created_str} UTC")
        if state.error:
            click.echo(f"Error:    {state.error}")
        if state.nodes:
            click.echo("Nodes:")
            for nid, nstate in state.nodes.items():
                extras: list[str] = []
                if nstate.cache_hit:
                    extras.append("cache_hit")
                if nstate.attempt:
                    extras.append(f"attempt={nstate.attempt}")
                if nstate.warnings:
                    extras.append(f"warnings={len(nstate.warnings)}")
                if nstate.error:
                    extras.append(f"error={nstate.error}")
                suffix = f" ({', '.join(extras)})" if extras else ""
                click.echo(f"  {nid}: {nstate.status.value}{suffix}")
        return

    runs = store.list_runs(limit=limit, workflow_path=norm_wf_filter)

    if not runs:
        click.echo("No runs found.")
        return

    drift_alerts = detect_baseline_drift(store, workflow_path=norm_wf_filter)
    for alert in drift_alerts:
        click.echo(f"[DRIFT] {alert.message}")
    if drift_alerts:
        click.echo("")

    headers = ("ID", "STATUS", "WORKFLOW", "CREATED", "ERROR")
    rows: list[tuple[str, str, str, str, str]] = []
    for run in runs:
        created_str = datetime.fromtimestamp(run.created_at, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(
            (
                run.id,
                run.status.value,
                run.workflow_path,
                created_str,
                run.error or "-",
            )
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    click.echo("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    click.echo("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        click.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


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
    registry = PackRegistry(workspace_root)
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
    type=click.IntRange(min=0),
    show_default=True,
    help="Delete runs older than N days (must be >= 0).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report what would be deleted without deleting.",
)
def clean_cmd(days: int, dry_run: bool) -> None:
    """Mark-and-sweep garbage collection of old unpinned runs and unreferenced blobs."""
    if days < 0:
        click.echo("error: --days must be non-negative", err=True)
        sys.exit(1)
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
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="Host to bind (loopback only).",
)
@click.option("--no-browser", is_flag=True, default=False, help="Do not open a browser window.")
def ui_cmd(port: int, no_browser: bool, host: str = "127.0.0.1") -> None:
    """Start the local server on 127.0.0.1 and serve the UI."""
    from plynx.server import create_app, validate_host

    try:
        validate_host(host)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--host") from exc

    workspace_root = find_workspace_root()
    app = create_app(workspace_root, host=host)
    url = f"http://{host}:{port}"
    if not no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")


def _find_agent_guide() -> Path | None:
    """Locate bundled ``AGENT_GUIDE.md`` in wheel or editable repo layout."""
    pkg_guide = Path(__file__).resolve().parent.parent / "AGENT_GUIDE.md"
    if pkg_guide.is_file():
        return pkg_guide
    repo_root = Path(__file__).resolve().parents[5]
    repo_guide = repo_root / "docs" / "AGENT_GUIDE.md"
    if repo_guide.is_file():
        return repo_guide
    return None


@main.command("agent-guide")
def agent_guide_cmd() -> None:
    """Print the self-contained PLynx reference guide for AI coding agents."""
    guide_path = _find_agent_guide()
    if guide_path is None:
        click.echo("error: AGENT_GUIDE.md not found in installation", err=True)
        sys.exit(1)
    click.echo(guide_path.read_text(encoding="utf-8"), nl=False)
