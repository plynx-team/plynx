"""Static workflow validator (PROTOCOL.md sections 2 & 3)."""

from __future__ import annotations

import graphlib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec, PortType, ValidationIssue
from plynx.registry import FakeRegistry, OpRegistry
from plynx.workflow.models import NodeRef, Workflow, load_workflow


def _literal_matches_port_type(value: Any, port_type: PortType) -> bool:
    if value is None:
        return True
    if port_type == "str":
        return isinstance(value, str)
    if port_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if port_type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if port_type == "bool":
        return isinstance(value, bool)
    if port_type == "json":
        return isinstance(value, (dict, list))
    if port_type in ("file", "directory"):
        return isinstance(value, str)
    return False


def _ports_compatible(src: OutputPortSpec, dst: InputPortSpec) -> tuple[bool, str | None]:
    if src.type != dst.type:
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


def validate_workflow(workflow: Workflow, registry: OpRegistry) -> list[ValidationIssue]:
    """Validate ``workflow`` against ``registry`` and return all validation issues."""
    issues: list[ValidationIssue] = []
    stage_index = {stage_id: idx for idx, stage_id in enumerate(workflow.stages.keys())}

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

    dep_graph: dict[str, set[str]] = {node_id: set() for node_id in workflow.nodes}

    for node_id, node in workflow.nodes.items():
        dst_op = node_ops.get(node_id)
        dst_inputs: dict[str, InputPortSpec] = (
            {port.name: port for port in dst_op.inputs} if dst_op is not None else {}
        )

        for port_name, val in node.inputs.items():
            dst_port = dst_inputs.get(port_name)
            if dst_op is not None and dst_port is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        node_id=node_id,
                        message=(
                            f"Node '{node_id}': unknown input port '{port_name}' for op '{node.op}'"
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
            elif dst_port is not None and not _literal_matches_port_type(val, dst_port.type):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        node_id=node_id,
                        message=(
                            f"Node '{node_id}': port type mismatch on input '{port_name}': "
                            f"expected '{dst_port.type}', got literal '{type(val).__name__}'"
                        ),
                    )
                )

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
) -> list[ValidationIssue]:
    """Load and validate a workflow YAML file, returning any parse or validation issues."""
    reg = FakeRegistry() if registry is None else registry
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

    return validate_workflow(workflow, reg)
