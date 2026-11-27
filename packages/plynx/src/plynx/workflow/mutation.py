"""Dynamic workflow snapshot mutation validation and round-trip YAML patching (FEAT-AGT-3)."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from io import StringIO
from typing import Any

from plynx_sdk.protocol import GraphPatchPayload
from pydantic import ValidationError
from ruamel.yaml import YAML

from plynx.api_models import NodeStatus, ValidationIssue
from plynx.registry import OpRegistry
from plynx.workflow.models import (
    DEFAULT_STAGE_ID,
    NODE_ID_PATTERN,
    NodeRef,
    Workflow,
    parse_workflow_yaml,
)
from plynx.workflow.validator import validate_workflow


@dataclass(frozen=True)
class SnapshotMutationResult:
    """Outcome of ``validate_snapshot_mutation``."""

    valid: bool
    issues: list[ValidationIssue]
    added_node_ids: list[str]
    rewired_node_ids: list[str]
    superseded_failed_node_ids: list[str]
    total_injected_nodes: int


def compute_ancestors(workflow: Workflow) -> dict[str, set[str]]:
    """Return mapping of ``node_id`` -> set of all transitive upstream ``node_id``s."""
    direct: dict[str, set[str]] = {}
    for nid, spec in workflow.nodes.items():
        deps: set[str] = set()
        for val in spec.inputs.values():
            if isinstance(val, NodeRef) and val.from_node in workflow.nodes:
                deps.add(val.from_node)
        direct[nid] = deps

    ancestors: dict[str, set[str]] = {}
    for nid in workflow.nodes:
        visited: set[str] = set()
        stack = list(direct.get(nid, ()))
        while stack:
            cur = stack.pop()
            if cur in visited or cur == nid:
                continue
            visited.add(cur)
            stack.extend(direct.get(cur, ()))
        ancestors[nid] = visited
    return ancestors


def _non_failed_direct_deps(
    workflow: Workflow,
    node_id: str,
    node_statuses: Mapping[str, NodeStatus],
) -> set[str]:
    spec = workflow.nodes.get(node_id)
    if spec is None:
        return set()
    return {
        val.from_node
        for val in spec.inputs.values()
        if isinstance(val, NodeRef)
        and val.from_node in workflow.nodes
        and node_statuses.get(val.from_node) != NodeStatus.FAILED
    }


def _referenced_nodes(workflow: Workflow, *, exclude: set[str] | None = None) -> set[str]:
    skip = exclude or set()
    refs: set[str] = set()
    for nid, spec in workflow.nodes.items():
        if nid in skip:
            continue
        if spec.meta is not None and spec.meta.superseded_by:
            continue
        for val in spec.inputs.values():
            if isinstance(val, NodeRef):
                refs.add(val.from_node)
    return refs


def validate_snapshot_mutation(
    old_snapshot: Workflow,
    new_snapshot: Workflow,
    registry: OpRegistry,
    node_statuses: Mapping[str, NodeStatus] | None = None,
    *,
    max_injected_nodes: int = 3,
    baseline_node_ids: set[str] | None = None,
    allow_drop_lineage: bool = False,
    run_inputs: dict[str, Any] | None = None,
) -> SnapshotMutationResult:
    """Validate a proposed ``workflow.snapshot.yaml`` mutation against all 4 FEAT-AGT-3 guardrails.

    Enforces:
    1. Standard static validation (``validate_workflow``: valid ops, port types, no cycles, stage order).
    2. ``PENDING``-only target rule (``SUCCESS`` / ``RUNNING`` nodes cannot be deleted or modified;
       existing ``op`` cannot change; only ``PENDING`` or failed/blocked nodes may have inputs rewired).
    3. Lineage preservation (``U -> [New Subgraph] -> V`` across 1-to-1 adapters, N-to-1 aggregators,
       variadic extra ports, and failed-node fallback subgraphs preserving ``U``'s upstream lineage).
    4. ``max_injected_nodes`` cumulative per-run budget.
    """
    statuses = dict(node_statuses) if node_statuses is not None else {}
    issues: list[ValidationIssue] = []

    # Check 1: Standard static validation
    static_issues = validate_workflow(new_snapshot, registry, run_inputs=run_inputs)
    for issue in static_issues:
        if issue.severity == "error":
            issues.append(issue)

    added_node_ids = [nid for nid in new_snapshot.nodes if nid not in old_snapshot.nodes]
    rewired_node_ids: list[str] = []

    immutable_statuses = {
        NodeStatus.SUCCESS,
        NodeStatus.RUNNING,
        NodeStatus.BUILDING_ENVIRONMENT,
        NodeStatus.WAITING_FOR_USER,
    }

    # Check 2: PENDING-only target rule & existing node immutability
    for nid, old_spec in old_snapshot.nodes.items():
        st = statuses.get(nid)
        new_spec = new_snapshot.nodes.get(nid)
        if new_spec is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=nid,
                    message=f"Snapshot mutation cannot delete existing node '{nid}'",
                )
            )
            continue

        if new_spec.op != old_spec.op:
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=nid,
                    message=(
                        f"Node '{nid}': cannot change 'op' from '{old_spec.op}' to "
                        f"'{new_spec.op}' on an existing node"
                    ),
                )
            )

        inputs_changed = new_spec.inputs != old_spec.inputs
        stage_changed = new_spec.stage != old_spec.stage

        if st in immutable_statuses and (inputs_changed or stage_changed):
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=nid,
                    message=(
                        f"Node '{nid}' has status '{st.value}' and cannot have its "
                        "inputs or stage modified"
                    ),
                )
            )
            continue

        if inputs_changed:
            rewired_node_ids.append(nid)

    # Check 3: Lineage Preservation (U -> [New Subgraph] -> V)
    new_ancestors = compute_ancestors(new_snapshot)
    for v_nid in rewired_node_ids:
        old_inputs = old_snapshot.nodes[v_nid].inputs
        new_inputs = new_snapshot.nodes[v_nid].inputs
        for port, old_val in old_inputs.items():
            if not isinstance(old_val, NodeRef):
                continue
            u_nid = old_val.from_node
            new_val = new_inputs.get(port)
            if not isinstance(new_val, NodeRef):
                if not allow_drop_lineage:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=v_nid,
                            message=(
                                f"Lineage violation on '{v_nid}.{port}': cannot drop "
                                f"upstream reference '${u_nid}.{old_val.output}'"
                            ),
                        )
                    )
                continue

            n_nid = new_val.from_node
            if n_nid == u_nid:
                continue

            u_status = statuses.get(u_nid)
            if u_status == NodeStatus.FAILED:
                # Fallback replacement for a failed node U: N must preserve U's non-failed ancestors.
                required_ancestors = _non_failed_direct_deps(old_snapshot, u_nid, statuses)
                n_lineage = new_ancestors.get(n_nid, set()) | {n_nid}
                missing = sorted(required_ancestors - n_lineage)
                if missing and not allow_drop_lineage:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=v_nid,
                            message=(
                                f"Lineage violation on '{v_nid}.{port}': fallback node '{n_nid}' "
                                f"replacing failed node '{u_nid}' drops upstream dependency "
                                f"{', '.join(missing)}"
                            ),
                        )
                    )
            else:
                if u_nid not in new_ancestors.get(n_nid, set()) and not allow_drop_lineage:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=v_nid,
                            message=(
                                f"Lineage violation on '{v_nid}.{port}': rewiring from "
                                f"'${u_nid}.{old_val.output}' to '${n_nid}.{new_val.output}' "
                                f"orphans upstream node '{u_nid}' (expected '{u_nid}' to remain "
                                f"an upstream ancestor of '{n_nid}')"
                            ),
                        )
                    )

    # Identify failed nodes superseded by fallback nodes (bypassed, not rewired)
    old_refs = _referenced_nodes(old_snapshot)
    new_refs = _referenced_nodes(new_snapshot)
    superseded_failed_node_ids: list[str] = []
    for nid, old_spec in old_snapshot.nodes.items():
        if statuses.get(nid) != NodeStatus.FAILED or nid in rewired_node_ids:
            continue
        new_spec = new_snapshot.nodes.get(nid)
        if new_spec is None:
            continue
        if new_spec.meta is not None and new_spec.meta.superseded_by:
            superseded_failed_node_ids.append(nid)
            continue
        if nid in new_refs:
            continue
        if nid in old_refs:
            # Previously referenced downstream, now completely bypassed by rewired fallback
            superseded_failed_node_ids.append(nid)
            continue
        # Leaf failed node: superseded if an added node in the same stage preserves its upstream deps
        req_deps = _non_failed_direct_deps(old_snapshot, nid, statuses)
        same_stage_added = [
            add_id
            for add_id in added_node_ids
            if new_snapshot.nodes[add_id].stage == old_spec.stage
            and req_deps.issubset(new_ancestors.get(add_id, set()) | {add_id})
        ]
        if same_stage_added:
            superseded_failed_node_ids.append(nid)

    # Check 4: Cumulative max_injected_nodes budget
    if baseline_node_ids is not None:
        base_ids = set(baseline_node_ids)
    else:
        base_ids = {
            nid
            for nid, spec in old_snapshot.nodes.items()
            if not (spec.meta is not None and spec.meta.injected_by)
        }
    injected_ids = {
        nid
        for nid, spec in new_snapshot.nodes.items()
        if nid not in base_ids or (spec.meta is not None and bool(spec.meta.injected_by))
    }
    total_injected = len(injected_ids)
    if total_injected > max_injected_nodes:
        issues.append(
            ValidationIssue(
                severity="error",
                node_id=added_node_ids[0] if added_node_ids else None,
                message=(
                    f"Injected node budget exceeded: {total_injected} injected node(s) "
                    f"exceeds max_injected_nodes={max_injected_nodes}"
                ),
            )
        )

    errors = [issue for issue in issues if issue.severity == "error"]
    return SnapshotMutationResult(
        valid=len(errors) == 0,
        issues=issues,
        added_node_ids=added_node_ids,
        rewired_node_ids=rewired_node_ids,
        superseded_failed_node_ids=superseded_failed_node_ids,
        total_injected_nodes=total_injected,
    )


def _format_yaml_input_value(raw_val: Any) -> Any:
    """Format an input value idiomatically for YAML (``$node.port`` for references)."""
    if isinstance(raw_val, NodeRef):
        return f"${raw_val.from_node}.{raw_val.output}"
    if (
        isinstance(raw_val, Mapping)
        and set(raw_val.keys()) == {"from_node", "output"}
        and isinstance(raw_val.get("from_node"), str)
        and isinstance(raw_val.get("output"), str)
    ):
        return f"${raw_val['from_node']}.{raw_val['output']}"
    if isinstance(raw_val, Mapping):
        return {str(k): v for k, v in raw_val.items()}
    if isinstance(raw_val, list):
        return list(raw_val)
    return raw_val


def apply_graph_patch_to_yaml(
    raw_yaml_bytes: bytes,
    patch: GraphPatchPayload,
    *,
    injected_by: str,
    default_stage: str = DEFAULT_STAGE_ID,
    superseded_node_ids: Sequence[str] = (),
) -> bytes:
    """Apply ``patch`` to ``raw_yaml_bytes`` via ``ruamel.yaml``, preserving formatting & comments."""
    if not patch.add_nodes and not patch.rewire_inputs:
        raise ValueError("Graph patch must specify at least one of 'add_nodes' or 'rewire_inputs'")

    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(StringIO(raw_yaml_bytes.decode("utf-8")))
    if not isinstance(data, MutableMapping):
        raise ValueError("Workflow snapshot YAML top-level value must be a mapping")

    nodes_map = data.get("nodes")
    if nodes_map is None:
        data["nodes"] = {}
        nodes_map = data["nodes"]
    if not isinstance(nodes_map, MutableMapping):
        raise ValueError("Workflow snapshot 'nodes' must be a mapping")

    for new_nid, raw_spec in patch.add_nodes.items():
        if not NODE_ID_PATTERN.match(new_nid):
            raise ValueError(f"Added node ID {new_nid!r} is invalid: must match ^[a-z][a-z0-9_]*$")
        if new_nid in nodes_map:
            raise ValueError(f"Graph patch 'add_nodes' cannot overwrite existing node {new_nid!r}")
        raw_op = raw_spec.get("op")
        if not isinstance(raw_op, str) or not raw_op.strip():
            raise ValueError(f"Added node {new_nid!r} must specify a non-empty 'op'")

        node_entry: dict[str, Any] = {"op": raw_op.strip()}
        if isinstance(raw_spec.get("title"), str) and str(raw_spec["title"]).strip():
            node_entry["title"] = str(raw_spec["title"]).strip()
        stage_val = raw_spec.get("stage")
        effective_stage = (
            stage_val.strip() if isinstance(stage_val, str) and stage_val.strip() else default_stage
        )
        if effective_stage != DEFAULT_STAGE_ID or "stages" in data:
            node_entry["stage"] = effective_stage
        if isinstance(raw_spec.get("allow_graph_edits"), str):
            node_entry["allow_graph_edits"] = raw_spec["allow_graph_edits"]

        raw_inputs = raw_spec.get("inputs")
        if isinstance(raw_inputs, Mapping) and raw_inputs:
            node_entry["inputs"] = {
                str(port): _format_yaml_input_value(val) for port, val in raw_inputs.items()
            }

        node_entry["meta"] = {
            "injected_by": injected_by,
            "reason": patch.reason,
        }
        nodes_map[new_nid] = node_entry

    for target_nid, port_updates in patch.rewire_inputs.items():
        if target_nid not in nodes_map:
            raise ValueError(f"Graph patch 'rewire_inputs' references unknown node {target_nid!r}")
        target_entry = nodes_map[target_nid]
        if not isinstance(target_entry, MutableMapping):
            raise ValueError(f"Node entry {target_nid!r} in snapshot is invalid")
        if "inputs" not in target_entry or not isinstance(target_entry["inputs"], MutableMapping):
            target_entry["inputs"] = {}
        inputs_entry = target_entry["inputs"]
        for port, val in port_updates.items():
            inputs_entry[str(port)] = _format_yaml_input_value(val)

    superseded_label = ", ".join(patch.add_nodes.keys()) if patch.add_nodes else injected_by
    for sup_nid in superseded_node_ids:
        if sup_nid in nodes_map and isinstance(nodes_map[sup_nid], MutableMapping):
            sup_entry = nodes_map[sup_nid]
            if "meta" not in sup_entry or not isinstance(sup_entry["meta"], MutableMapping):
                sup_entry["meta"] = {}
            sup_entry["meta"]["superseded_by"] = superseded_label

    buf = StringIO()
    yaml.dump(data, buf)
    return buf.getvalue().encode("utf-8")


def prepare_and_validate_patch(
    *,
    raw_yaml_bytes: bytes,
    old_snapshot: Workflow,
    patch: GraphPatchPayload,
    injected_by: str,
    default_stage: str,
    registry: OpRegistry,
    node_statuses: Mapping[str, NodeStatus] | None = None,
    max_injected_nodes: int = 3,
    baseline_node_ids: set[str] | None = None,
    run_inputs: dict[str, Any] | None = None,
) -> tuple[SnapshotMutationResult, bytes | None, Workflow | None]:
    """Apply ``patch`` in-memory, parse, and validate against ``validate_snapshot_mutation``.

    Returns ``(mutation_result, candidate_yaml_bytes, candidate_workflow)``.
    """
    try:
        candidate_bytes = apply_graph_patch_to_yaml(
            raw_yaml_bytes,
            patch,
            injected_by=injected_by,
            default_stage=default_stage,
        )
        candidate_wf = parse_workflow_yaml(
            candidate_bytes,
            default_name=old_snapshot.name or None,
        )
    except (ValidationError, ValueError) as exc:
        err_issue = ValidationIssue(severity="error", message=str(exc))
        return (
            SnapshotMutationResult(
                valid=False,
                issues=[err_issue],
                added_node_ids=[],
                rewired_node_ids=[],
                superseded_failed_node_ids=[],
                total_injected_nodes=0,
            ),
            None,
            None,
        )

    res = validate_snapshot_mutation(
        old_snapshot,
        candidate_wf,
        registry,
        node_statuses,
        max_injected_nodes=max_injected_nodes,
        baseline_node_ids=baseline_node_ids,
        run_inputs=run_inputs,
    )
    if not res.valid:
        return res, None, None

    if res.superseded_failed_node_ids:
        candidate_bytes = apply_graph_patch_to_yaml(
            raw_yaml_bytes,
            patch,
            injected_by=injected_by,
            default_stage=default_stage,
            superseded_node_ids=res.superseded_failed_node_ids,
        )
        candidate_wf = parse_workflow_yaml(
            candidate_bytes,
            default_name=old_snapshot.name or None,
        )

    return res, candidate_bytes, candidate_wf


__all__ = [
    "SnapshotMutationResult",
    "apply_graph_patch_to_yaml",
    "compute_ancestors",
    "prepare_and_validate_patch",
    "validate_snapshot_mutation",
]
