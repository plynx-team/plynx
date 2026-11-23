"""Static workflow validator (PROTOCOL.md sections 2 & 3)."""

from __future__ import annotations

import graphlib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from plynx.api_models import (
    InputPortSpec,
    OpEntry,
    OutputPortSpec,
    ValidationIssue,
    WorkflowInputSpec,
)
from plynx.registry import OpRegistry, PackRegistry, find_workspace_root, is_direct_builtin_pack
from plynx.workflow.models import NodeRef, Workflow, load_workflow


def _literal_matches_port_spec(value: Any, port: InputPortSpec) -> tuple[bool, str | None]:
    if value is None:
        if port.required:
            return False, f"required input '{port.name}' cannot be null"
        return True, None

    type_ok = False
    if port.type == "str":
        type_ok = isinstance(value, str)
    elif port.type == "int":
        type_ok = isinstance(value, int) and not isinstance(value, bool)
    elif port.type == "float":
        type_ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif port.type == "bool":
        type_ok = isinstance(value, bool)
    elif port.type == "json":
        type_ok = isinstance(value, (dict, list))
    elif port.type in ("file", "directory"):
        type_ok = isinstance(value, str)

    if not type_ok:
        return (
            False,
            f"port type mismatch on input '{port.name}': "
            f"expected '{port.type}', got literal '{type(value).__name__}'",
        )

    if port.options is not None and value not in port.options:
        return (
            False,
            f"input '{port.name}' value {value!r} is not in allowed options {port.options}",
        )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if port.min is not None and value < port.min:
            return (
                False,
                f"input '{port.name}' value {value} is less than minimum {port.min}",
            )
        if port.max is not None and value > port.max:
            return (
                False,
                f"input '{port.name}' value {value} is greater than maximum {port.max}",
            )

    return True, None


def _ports_compatible(src: OutputPortSpec, dst: InputPortSpec) -> tuple[bool, str | None]:
    if src.type != dst.type and not (src.type == "int" and dst.type == "float"):
        return (
            False,
            f"port type mismatch: expected '{dst.type}', got '{src.type}'",
        )
    if (
        dst.type == "file"
        and dst.media is not None
        and src.media is not None
        and dst.media != src.media
    ):
        return (
            False,
            f"port type media mismatch: expected '{dst.media}', got '{src.media}'",
        )
    return True, None


def get_unbound_run_inputs(
    workflow: Workflow,
    registry: OpRegistry,
) -> list[WorkflowInputSpec]:
    """Return all required input ports that have no default and are not bound in ``workflow``."""
    unbound: list[WorkflowInputSpec] = []
    for node_id, node in workflow.nodes.items():
        op_entry = registry.get(node.op)
        if op_entry is None or not op_entry.valid:
            continue
        for port in op_entry.inputs:
            if port.name not in node.inputs and port.required and port.default is None:
                unbound.append(
                    WorkflowInputSpec(
                        node_id=node_id,
                        name=port.name,
                        type=port.type,
                        media=port.media,
                        options=port.options,
                        min=port.min,
                        max=port.max,
                        step=port.step,
                        required=port.required,
                        default=port.default,
                        description=port.description,
                        stage_id=node.stage,
                    )
                )
    return unbound


def _resolve_node_ops(
    workflow: Workflow,
    registry: OpRegistry,
    issues: list[ValidationIssue],
) -> dict[str, OpEntry]:
    node_ops: dict[str, OpEntry] = {}
    for node_id, node in workflow.nodes.items():
        op_entry = registry.get(node.op)
        if op_entry is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=node_id,
                    message=f"Node '{node_id}': unknown op '{node.op}'",
                )
            )
            continue
        if not op_entry.valid:
            reason = op_entry.error or "invalid op declaration"
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=node_id,
                    message=f"Node '{node_id}': invalid op '{node.op}': {reason}",
                )
            )
            continue
        node_ops[node_id] = op_entry
    return node_ops


def _check_pack_lockfiles(
    node_ops: dict[str, OpEntry],
    registry: OpRegistry,
    issues: list[ValidationIssue],
) -> None:
    discovered_packs: dict[str, Path] = getattr(registry, "discovered_packs", {})
    checked_packs: set[str] = set()
    for op_entry in node_ops.values():
        pack_name = op_entry.pack
        if pack_name in checked_packs:
            continue
        checked_packs.add(pack_name)
        pack_dir = discovered_packs.get(pack_name)
        if (
            pack_dir is not None
            and not is_direct_builtin_pack(pack_dir)
            and not (pack_dir / "uv.lock").is_file()
        ):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    node_id=None,
                    message=f"Pack '{pack_name}' is missing 'uv.lock' (reproducibility hazard)",
                )
            )


def _check_unbound_inputs(
    workflow: Workflow,
    node_ops: dict[str, OpEntry],
    run_inputs: dict[str, Any] | None,
    issues: list[ValidationIssue],
) -> None:
    for node_id, node in workflow.nodes.items():
        dst_op = node_ops.get(node_id)
        if dst_op is None:
            continue
        for port in dst_op.inputs:
            if port.name in node.inputs:
                continue
            bound_in_run_inputs = bool(run_inputs and f"{node_id}.{port.name}" in run_inputs)
            if not bound_in_run_inputs and port.required and port.default is None:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        node_id=node_id,
                        message=(
                            f"Node '{node_id}': unbound run input '{port.name}' "
                            f"(type '{port.type}')"
                        ),
                    )
                )


def _validate_node_inputs(
    workflow: Workflow,
    node_ops: dict[str, OpEntry],
    stage_index: dict[str, int],
    dep_graph: dict[str, set[str]],
    issues: list[ValidationIssue],
) -> None:
    for node_id, node in workflow.nodes.items():
        dst_op = node_ops.get(node_id)
        dst_inputs: dict[str, InputPortSpec] = (
            {port.name: port for port in dst_op.inputs} if dst_op is not None else {}
        )

        for port_name, val in node.inputs.items():
            dst_port = dst_inputs.get(port_name)
            if dst_op is not None and dst_port is None:
                if dst_op.allow_extra_inputs:
                    dst_port = dst_op.extra_inputs_type
                else:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=node_id,
                            message=(
                                f"Node '{node_id}': unknown input port '{port_name}' "
                                f"for op '{node.op}'"
                            ),
                        )
                    )

            if isinstance(val, NodeRef):
                src_node_id = val.from_node
                if src_node_id not in workflow.nodes:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=node_id,
                            message=(
                                f"Node '{node_id}': input '{port_name}' references "
                                f"missing node '{src_node_id}'"
                            ),
                        )
                    )
                    continue

                dep_graph[node_id].add(src_node_id)

                src_stage = workflow.nodes[src_node_id].stage
                dst_stage = node.stage
                if stage_index[dst_stage] < stage_index[src_stage]:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=node_id,
                            message=(
                                f"Node '{node_id}': backward stage edge from node "
                                f"'{src_node_id}' (stage '{src_stage}') to node "
                                f"'{node_id}' (stage '{dst_stage}')"
                            ),
                        )
                    )

                src_op = node_ops.get(src_node_id)
                if src_op is not None:
                    src_outputs = {port.name: port for port in src_op.outputs}
                    src_port = src_outputs.get(val.output)
                    if src_port is None:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                node_id=node_id,
                                message=(
                                    f"Node '{node_id}': input '{port_name}' references "
                                    f"unknown output '{val.output}' on node '{src_node_id}'"
                                ),
                            )
                        )
                    elif dst_port is not None:
                        compatible, mismatch_reason = _ports_compatible(src_port, dst_port)
                        if not compatible:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    node_id=node_id,
                                    message=(
                                        f"Node '{node_id}': {mismatch_reason} on input "
                                        f"'{port_name}' from '{src_node_id}.{val.output}'"
                                    ),
                                )
                            )
            elif dst_port is not None:
                matches, err_msg = _literal_matches_port_spec(val, dst_port)
                if not matches:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=node_id,
                            message=f"Node '{node_id}': {err_msg}",
                        )
                    )


def validate_workflow(
    workflow: Workflow,
    registry: OpRegistry,
    *,
    run_inputs: dict[str, Any] | None = None,
) -> list[ValidationIssue]:
    """Validate ``workflow`` against ``registry`` and return all validation issues."""
    issues: list[ValidationIssue] = []
    stage_index = {stage_id: idx for idx, stage_id in enumerate(workflow.stages.keys())}

    node_ops = _resolve_node_ops(workflow, registry, issues)
    _check_pack_lockfiles(node_ops, registry, issues)
    _check_unbound_inputs(workflow, node_ops, run_inputs, issues)

    dep_graph: dict[str, set[str]] = {node_id: set() for node_id in workflow.nodes}
    _validate_node_inputs(workflow, node_ops, stage_index, dep_graph, issues)

    sorter = graphlib.TopologicalSorter(dep_graph)
    try:
        sorter.prepare()
    except graphlib.CycleError as exc:
        cycle_nodes: list[str] = list(exc.args[1]) if len(exc.args) > 1 else []
        culprit = cycle_nodes[0] if cycle_nodes else next(iter(workflow.nodes), "")
        cycle_display = " -> ".join(reversed(cycle_nodes)) if cycle_nodes else "cycle"
        issues.append(
            ValidationIssue(
                severity="error",
                node_id=culprit or None,
                message=f"Node '{culprit}': cycle detected ({cycle_display})",
            )
        )

    return issues


def validate_workflow_file(
    path: Path,
    registry: OpRegistry | None = None,
    *,
    run_inputs: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> list[ValidationIssue]:
    """Load and validate a workflow YAML file, returning any parse or validation issues."""
    if registry is None:
        ws_root = (workspace_root or find_workspace_root()).resolve()
        reg: OpRegistry = PackRegistry(ws_root)
    else:
        reg = registry
    try:
        workflow = load_workflow(path)
    except ValidationError as exc:
        issues: list[ValidationIssue] = []
        for err in exc.errors():
            loc_parts = [str(part) for part in err.get("loc", ())]
            node_id: str | None = None
            if len(loc_parts) >= 2 and loc_parts[0] == "nodes":
                node_id = loc_parts[1]
            prefix = f"Node '{node_id}': " if node_id else ""
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=node_id,
                    message=f"{prefix}{err.get('msg', str(exc))}",
                )
            )
        return issues or [ValidationIssue(severity="error", message=str(exc))]
    except (ValueError, OSError) as exc:
        return [ValidationIssue(severity="error", message=str(exc))]

    return validate_workflow(workflow, reg, run_inputs=run_inputs)
