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
from plynx.workflow.models import (
    STAGE_ID_FOR_VALIDATOR_PATTERN,
    NodeRef,
    StageValidatorSpec,
    Workflow,
    load_workflow,
    stage_validator_node_id,
)


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
                        suggestions=port.suggestions,
                        min=port.min,
                        max=port.max,
                        step=port.step,
                        required=port.required,
                        default=port.default,
                        description=port.description,
                        stage_id=node.stage,
                    )
                )
    for stage_id, stage in workflow.stages.items():
        if stage.validator is None:
            continue
        val_op = registry.get(stage.validator.op)
        if val_op is None or not val_op.valid:
            continue
        val_nid = stage_validator_node_id(stage_id)
        for port in val_op.inputs:
            if port.name not in stage.validator.inputs and port.required and port.default is None:
                unbound.append(
                    WorkflowInputSpec(
                        node_id=val_nid,
                        name=port.name,
                        type=port.type,
                        media=port.media,
                        options=port.options,
                        suggestions=port.suggestions,
                        min=port.min,
                        max=port.max,
                        step=port.step,
                        required=port.required,
                        default=port.default,
                        description=port.description,
                        stage_id=stage_id,
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
        if node.allow_graph_edits is not None and op_entry.agent_role is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=node_id,
                    message=(
                        f"Node '{node_id}': 'allow_graph_edits' is only supported on "
                        f"AgentOp / StageValidatorOp operations (got '{node.op}')"
                    ),
                )
            )
        node_ops[node_id] = op_entry
    return node_ops


def _validate_stage_validators(
    workflow: Workflow,
    registry: OpRegistry,
    node_ops: dict[str, OpEntry],
    stage_index: dict[str, int],
    run_inputs: dict[str, Any] | None,
    issues: list[ValidationIssue],
) -> list[OpEntry]:
    validator_ops: list[OpEntry] = []
    for stage_id, stage in workflow.stages.items():
        val_spec: StageValidatorSpec | None = stage.validator
        if val_spec is None:
            continue
        val_nid = stage_validator_node_id(stage_id)
        if not STAGE_ID_FOR_VALIDATOR_PATTERN.match(stage_id):
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=val_nid,
                    message=(
                        f"Stage '{stage_id}': stage ID with validator must match "
                        "^[a-zA-Z0-9][a-zA-Z0-9_-]*$"
                    ),
                )
            )
        op_entry = registry.get(val_spec.op)
        if op_entry is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=val_nid,
                    message=f"Stage '{stage_id}' validator: unknown op '{val_spec.op}'",
                )
            )
            continue
        if not op_entry.valid:
            reason = op_entry.error or "invalid op declaration"
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=val_nid,
                    message=(f"Stage '{stage_id}' validator: invalid op '{val_spec.op}': {reason}"),
                )
            )
            continue
        if op_entry.agent_role not in ("validator", "agent"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=val_nid,
                    message=(
                        f"Stage '{stage_id}' validator: op '{val_spec.op}' must be a "
                        "StageValidatorOp or AgentOp"
                    ),
                )
            )
            continue

        validator_ops.append(op_entry)
        dst_inputs = {port.name: port for port in op_entry.inputs}

        for port in op_entry.inputs:
            if port.name in val_spec.inputs:
                continue
            bound = bool(run_inputs and f"{val_nid}.{port.name}" in run_inputs)
            if not bound and port.required and port.default is None:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        node_id=val_nid,
                        message=(
                            f"Stage '{stage_id}' validator: unbound run input "
                            f"'{port.name}' (type '{port.type}')"
                        ),
                    )
                )

        for port_name, val in val_spec.inputs.items():
            dst_port = dst_inputs.get(port_name)
            if dst_port is None:
                if op_entry.allow_extra_inputs:
                    dst_port = op_entry.extra_inputs_type
                else:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=val_nid,
                            message=(
                                f"Stage '{stage_id}' validator: unknown input port "
                                f"'{port_name}' for op '{val_spec.op}'"
                            ),
                        )
                    )
            if isinstance(val, NodeRef):
                src_nid = val.from_node
                if src_nid not in workflow.nodes:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=val_nid,
                            message=(
                                f"Stage '{stage_id}' validator: input '{port_name}' "
                                f"references missing node '{src_nid}'"
                            ),
                        )
                    )
                    continue
                src_stage = workflow.nodes[src_nid].stage
                if stage_index[stage_id] < stage_index[src_stage]:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=val_nid,
                            message=(
                                f"Stage '{stage_id}' validator: backward stage edge "
                                f"from node '{src_nid}' (stage '{src_stage}')"
                            ),
                        )
                    )
                src_op = node_ops.get(src_nid)
                if src_op is not None:
                    src_outputs = {p.name: p for p in src_op.outputs}
                    src_port = src_outputs.get(val.output)
                    if src_port is None:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                node_id=val_nid,
                                message=(
                                    f"Stage '{stage_id}' validator: input '{port_name}' "
                                    f"references unknown output '{val.output}' on '{src_nid}'"
                                ),
                            )
                        )
                    elif dst_port is not None:
                        compatible, mismatch_reason = _ports_compatible(src_port, dst_port)
                        if not compatible:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    node_id=val_nid,
                                    message=(
                                        f"Stage '{stage_id}' validator: {mismatch_reason} "
                                        f"on input '{port_name}' from '{src_nid}.{val.output}'"
                                    ),
                                )
                            )
            elif dst_port is not None:
                matches, err_msg = _literal_matches_port_spec(val, dst_port)
                if not matches:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=val_nid,
                            message=f"Stage '{stage_id}' validator: {err_msg}",
                        )
                    )
    return validator_ops


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
    validator_ops = _validate_stage_validators(
        workflow, registry, node_ops, stage_index, run_inputs, issues
    )
    all_ops_for_locks = dict(node_ops)
    for idx, v_op in enumerate(validator_ops):
        all_ops_for_locks[f"__val__{idx}"] = v_op
    _check_pack_lockfiles(all_ops_for_locks, registry, issues)
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
