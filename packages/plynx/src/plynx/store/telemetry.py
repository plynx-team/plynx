"""Baseline drift detection and node execution telemetry (ENTRYPOINT.md section 2.4.D)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from plynx.api_models import BaselineDriftAlert, NodeExecutionStat, NodeStatus
from plynx.store.run_store import RunStore
from plynx.workflow.models import (
    NodeRef,
    Workflow,
    is_stage_validator_node_id,
    load_workflow,
)

DEFAULT_DRIFT_MIN_OCCURRENCES = 3
DEFAULT_DRIFT_WINDOW_RUNS = 5


@dataclass(frozen=True)
class SpliceSignature:
    """Structural splice tuple ``(injected_op, upstream_op, downstream_op)``."""

    injected_op: str
    upstream_op: str | None
    downstream_op: str | None


def _nearest_baseline_upstream_ops(
    node_id: str,
    snapshot: Workflow,
    baseline_nodes: set[str],
) -> list[str | None]:
    visited: set[str] = set()
    found: list[str] = []
    stack: list[str] = []
    spec = snapshot.nodes.get(node_id)
    if spec is not None:
        for val in spec.inputs.values():
            if isinstance(val, NodeRef) and val.from_node in snapshot.nodes:
                stack.append(val.from_node)

    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        if cur in baseline_nodes:
            op_id = snapshot.nodes[cur].op
            if op_id not in found:
                found.append(op_id)
        else:
            cur_spec = snapshot.nodes.get(cur)
            if cur_spec is not None:
                for val in cur_spec.inputs.values():
                    if isinstance(val, NodeRef) and val.from_node in snapshot.nodes:
                        stack.append(val.from_node)

    out: list[str | None] = [*sorted(found)]
    return out if out else [None]


def _nearest_baseline_downstream_ops(
    node_id: str,
    snapshot: Workflow,
    baseline_nodes: set[str],
) -> list[str | None]:
    reverse_adj: dict[str, list[str]] = {nid: [] for nid in snapshot.nodes}
    for dst_nid, spec in snapshot.nodes.items():
        if spec.meta is not None and spec.meta.superseded_by:
            continue
        for val in spec.inputs.values():
            if isinstance(val, NodeRef) and val.from_node in reverse_adj:
                reverse_adj[val.from_node].append(dst_nid)

    visited: set[str] = set()
    found: list[str] = []
    stack = list(reverse_adj.get(node_id, ()))
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        if cur in baseline_nodes:
            op_id = snapshot.nodes[cur].op
            if op_id not in found:
                found.append(op_id)
        else:
            stack.extend(reverse_adj.get(cur, ()))

    out: list[str | None] = [*sorted(found)]
    return out if out else [None]


def extract_run_splice_signatures(
    baseline: Workflow,
    snapshot: Workflow,
) -> set[SpliceSignature]:
    """Compute unique structural splice tuples comparing ``snapshot`` against ``baseline``."""
    baseline_ids = set(baseline.nodes.keys())
    injected_ids = [
        nid
        for nid, spec in snapshot.nodes.items()
        if nid not in baseline_ids or (spec.meta is not None and bool(spec.meta.injected_by))
    ]
    signatures: set[SpliceSignature] = set()
    for inj_nid in injected_ids:
        inj_op = snapshot.nodes[inj_nid].op
        upstreams = _nearest_baseline_upstream_ops(inj_nid, snapshot, baseline_ids)
        downstreams = _nearest_baseline_downstream_ops(inj_nid, snapshot, baseline_ids)
        for u_op in upstreams:
            for d_op in downstreams:
                signatures.add(
                    SpliceSignature(
                        injected_op=inj_op,
                        upstream_op=u_op,
                        downstream_op=d_op,
                    )
                )
    return signatures


def _load_baseline_workflow_for_run(
    store: RunStore,
    run_id: str,
    workflow_path: str,
) -> Workflow | None:
    canonical = (store.workspace_root / workflow_path).resolve()
    try:
        canonical.relative_to(store.workspace_root)
        if canonical.is_file():
            return load_workflow(canonical)
    except Exception:
        pass
    run_baseline = store.run_dir(run_id) / ".workflow.baseline.yaml"
    if run_baseline.is_file():
        try:
            return load_workflow(run_baseline)
        except Exception:
            return None
    return None


def _load_snapshot_workflow_for_run(store: RunStore, run_id: str) -> Workflow | None:
    snap = store.run_dir(run_id) / "workflow.snapshot.yaml"
    if not snap.is_file():
        return None
    try:
        return load_workflow(snap)
    except Exception:
        return None


def detect_baseline_drift(
    store: RunStore,
    *,
    workflow_path: str | None = None,
    min_occurrences: int = DEFAULT_DRIFT_MIN_OCCURRENCES,
    window_runs: int = DEFAULT_DRIFT_WINDOW_RUNS,
) -> list[BaselineDriftAlert]:
    """Detect recurring structural splice tuples in ``K`` of the last ``N`` runs per workflow."""
    recent_runs = store.list_runs(limit=200, workflow_path=workflow_path)
    by_workflow: dict[str, list[str]] = {}
    for run in recent_runs:
        group = by_workflow.setdefault(run.workflow_path, [])
        if len(group) < window_runs:
            group.append(run.id)

    alerts: list[BaselineDriftAlert] = []
    for wf_path, run_ids in sorted(by_workflow.items()):
        counts: Counter[SpliceSignature] = Counter()
        inspected = 0
        for rid in run_ids:
            snap_wf = _load_snapshot_workflow_for_run(store, rid)
            base_wf = _load_baseline_workflow_for_run(store, rid, wf_path)
            if snap_wf is None or base_wf is None:
                continue
            inspected += 1
            for sig in extract_run_splice_signatures(base_wf, snap_wf):
                counts[sig] += 1

        if inspected < min_occurrences:
            continue

        for sig, occ in sorted(
            counts.items(),
            key=lambda kv: (
                -kv[1],
                kv[0].injected_op,
                kv[0].upstream_op or "",
                kv[0].downstream_op or "",
            ),
        ):
            if occ >= min_occurrences:
                up_label = sig.upstream_op or "(start)"
                down_label = sig.downstream_op or "(end)"
                msg = (
                    f"Baseline Drift Detected in '{wf_path}': '{sig.injected_op}' was spliced "
                    f"between '{up_label}' -> '{down_label}' in {occ} of the last {inspected} "
                    "runs. Consider promoting it into the baseline workflow."
                )
                alerts.append(
                    BaselineDriftAlert(
                        workflow_path=wf_path,
                        injected_op=sig.injected_op,
                        upstream_op=sig.upstream_op,
                        downstream_op=sig.downstream_op,
                        occurrences=occ,
                        window_runs=inspected,
                        message=msg,
                    )
                )
    return alerts


def compute_run_stats(
    store: RunStore,
    *,
    workflow_path: str | None = None,
    limit_runs: int = 200,
) -> tuple[int, list[NodeExecutionStat], list[BaselineDriftAlert]]:
    """Aggregate per-node execution stats and drift alerts from SQLite ``node_runs``."""
    runs = store.list_runs(limit=limit_runs, workflow_path=workflow_path)
    total_runs = len(runs)

    # Keyed by (workflow_path, node_id) or node_id when filtered
    acc: dict[str, dict[str, object]] = {}

    for run in runs:
        state = store.get_run_state(run.id)
        if state is None:
            continue
        snap_wf = state.workflow_snapshot
        base_wf = _load_baseline_workflow_for_run(store, run.id, run.workflow_path)
        base_ids = set(base_wf.nodes.keys()) if base_wf is not None else None

        for nid, nstate in state.nodes.items():
            if is_stage_validator_node_id(nid) and nstate.attempt == 0 and not nstate.cache_hit:
                # Include validator row, still track accurately
                pass
            op_name = ""
            is_injected = False
            if snap_wf is not None:
                nspec = snap_wf.nodes.get(nid)
                if nspec is not None:
                    op_name = nspec.op
                    if (nspec.meta is not None and nspec.meta.injected_by) or (
                        base_ids is not None and nid not in base_ids
                    ):
                        is_injected = True
                elif is_stage_validator_node_id(nid):
                    sid = nid[len("__stage_validator__") :]
                    st_spec = snap_wf.stages.get(sid)
                    if st_spec is not None and st_spec.validator is not None:
                        op_name = st_spec.validator.op

            stat_key = nid if workflow_path else f"{run.workflow_path}:{nid}"
            entry = acc.get(stat_key)
            if entry is None:
                entry = {
                    "workflow_path": run.workflow_path,
                    "node_id": nid,
                    "op": op_name,
                    "executions": 0,
                    "cache_hits": 0,
                    "failures": 0,
                    "dynamic_injections": 0,
                    "durations": [],
                }
                acc[stat_key] = entry
            elif not entry["op"] and op_name:
                entry["op"] = op_name

            entry["executions"] = int(entry["executions"]) + 1  # type: ignore[call-overload]
            if nstate.cache_hit:
                entry["cache_hits"] = int(entry["cache_hits"]) + 1  # type: ignore[call-overload]
            if nstate.status == NodeStatus.FAILED:
                entry["failures"] = int(entry["failures"]) + 1  # type: ignore[call-overload]
            if is_injected:
                entry["dynamic_injections"] = int(entry["dynamic_injections"]) + 1  # type: ignore[call-overload]
            if (
                not nstate.cache_hit
                and nstate.started_at is not None
                and nstate.finished_at is not None
                and nstate.finished_at >= nstate.started_at
            ):
                durations_list: list[float] = entry["durations"]  # type: ignore[assignment]
                durations_list.append(float(nstate.finished_at - nstate.started_at))

    stats_out: list[NodeExecutionStat] = []
    for key in sorted(acc.keys()):
        entry = acc[key]
        exec_count = int(entry["executions"])  # type: ignore[call-overload]
        cache_hits = int(entry["cache_hits"])  # type: ignore[call-overload]
        failures = int(entry["failures"])  # type: ignore[call-overload]
        injections = int(entry["dynamic_injections"])  # type: ignore[call-overload]
        durations: list[float] = entry["durations"]  # type: ignore[assignment]
        avg_dur = (sum(durations) / len(durations)) if durations else None
        hit_rate = (cache_hits / exec_count) if exec_count > 0 else 0.0
        stats_out.append(
            NodeExecutionStat(
                workflow_path=str(entry["workflow_path"]),
                node_id=str(entry["node_id"]),
                op=str(entry["op"]),
                executions=exec_count,
                cache_hits=cache_hits,
                cache_hit_rate=round(hit_rate, 4),
                avg_duration_seconds=round(avg_dur, 4) if avg_dur is not None else None,
                failures=failures,
                dynamic_injections=injections,
            )
        )

    drift_alerts = detect_baseline_drift(store, workflow_path=workflow_path)
    return total_runs, stats_out, drift_alerts


__all__ = [
    "DEFAULT_DRIFT_MIN_OCCURRENCES",
    "DEFAULT_DRIFT_WINDOW_RUNS",
    "SpliceSignature",
    "compute_run_stats",
    "detect_baseline_drift",
    "extract_run_splice_signatures",
]
