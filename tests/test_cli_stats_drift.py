"""Tests for Phase 4.7:
- `plynx runs --stats [--workflow] [--json]` & `GET /api/v1/runs/stats`
- Baseline drift detection (K=3 of last N=5 runs) in CLI `plynx runs` and `GET /api/v1/runs`
- REST node endpoints (`/logs/stdout`, `/outputs/summary`, `/agent-turns`) accepting `__stage_validator__<stage_id>`
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from plynx.api_models import NodeStatus, RunStatus
from plynx.cas import write_result_manifest
from plynx.cli import main as cli_main
from plynx.server import create_app
from plynx.store import RunStore
from plynx.workflow.models import stage_validator_node_id
from plynx_sdk.protocol import (
    AgentProvider,
    AgentTurnRecord,
    AgentTurnsManifest,
    AgentTurnStatus,
    GraphPatchPayload,
    ResultManifest,
    ScalarValue,
)

BASELINE_YAML = (
    b"version: 1\n"
    b"name: drift_demo\n"
    b"stages:\n"
    b"  s1:\n"
    b"    title: Ingest\n"
    b"  s2:\n"
    b"    title: Summarize\n"
    b"nodes:\n"
    b"  ingest:\n"
    b"    op: standard_io/demo:ReadText\n"
    b"    stage: s1\n"
    b"    inputs:\n"
    b"      text: bonjour\n"
    b"  summarize:\n"
    b"    op: standard_io/demo:Echo\n"
    b"    stage: s2\n"
    b"    inputs:\n"
    b"      text: $ingest.text\n"
)

SPLICED_YAML = (
    b"version: 1\n"
    b"name: drift_demo\n"
    b"stages:\n"
    b"  s1:\n"
    b"    title: Ingest\n"
    b"  s2:\n"
    b"    title: Summarize\n"
    b"nodes:\n"
    b"  ingest:\n"
    b"    op: standard_io/demo:ReadText\n"
    b"    stage: s1\n"
    b"    inputs:\n"
    b"      text: bonjour\n"
    b"  tr_fr:\n"
    b"    op: demo_pack/ops:TranslateFr\n"
    b"    stage: s1\n"
    b"    meta:\n"
    b"      injected_by: __stage_validator__s1\n"
    b"      reason: Translate French text\n"
    b"    inputs:\n"
    b"      text: $ingest.text\n"
    b"  summarize:\n"
    b"    op: standard_io/demo:Echo\n"
    b"    stage: s2\n"
    b"    inputs:\n"
    b"      text: $tr_fr.text\n"
)


def test_baseline_drift_detection_cli_stats_and_rest_endpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recurring splice in 3 of 5 runs triggers drift alert in CLI and REST, plus stats & validator routes."""
    monkeypatch.chdir(tmp_path)
    store = RunStore(tmp_path)
    val_id = stage_validator_node_id("s1")

    # Create 5 runs of `workflows/drift_demo.yaml`: 3 with the `TranslateFr` splice, 2 clean
    spliced_flags = [True, False, True, False, True]
    last_run_id = ""
    for idx, is_spliced in enumerate(spliced_flags):
        rid = f"20261126_12000{idx}_aa000{idx}"
        last_run_id = rid
        node_ids = ["ingest", val_id, "summarize"] + (["tr_fr"] if is_spliced else [])
        store.create_run(
            workflow_path="workflows/drift_demo.yaml",
            workflow_bytes=BASELINE_YAML,
            node_ids=node_ids,
            run_id=rid,
            created_at=1700000000.0 + idx * 10,
            status=RunStatus.SUCCESS,
        )
        store.update_node_status(
            rid,
            "ingest",
            NodeStatus.SUCCESS,
            attempt=1,
            started_at=10.0,
            finished_at=11.5,
            warnings=["lang=fr"] if is_spliced else [],
        )
        store.update_node_status(
            rid,
            val_id,
            NodeStatus.SUCCESS,
            attempt=1 if is_spliced else 0,
            started_at=11.5,
            finished_at=12.0,
        )
        store.update_node_status(
            rid,
            "summarize",
            NodeStatus.SUCCESS,
            cache_hit=not is_spliced,
            attempt=0 if not is_spliced else 1,
            started_at=12.0,
            finished_at=12.5,
        )
        if is_spliced:
            store.update_workflow_snapshot(rid, SPLICED_YAML)
            store.update_node_status(
                rid,
                "tr_fr",
                NodeStatus.SUCCESS,
                attempt=1,
                started_at=11.6,
                finished_at=11.9,
            )

    # Populate logs, result.json, and agent_turns.json on `__stage_validator__s1` for `last_run_id`
    logs_dir = store.run_dir(last_run_id) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / f"{val_id}.stdout.log").write_text(
        "Supervisor checked Stage s1\n", encoding="utf-8"
    )

    val_dir = store.node_dir(last_run_id, val_id)
    write_result_manifest(
        val_dir,
        ResultManifest(
            status="SUCCESS",
            cache_key="val-key",
            cache_hit=False,
            started_at=11.5,
            finished_at=12.0,
            outputs={"summary": ScalarValue(value="Spliced TranslateFr cleanly.")},
        ),
    )

    turns_json = AgentTurnsManifest(
        turns=[
            AgentTurnRecord(
                turn_index=0,
                provider=AgentProvider.MOCK,
                model="mock-v1",
                session_id="val_sess_99",
                status=AgentTurnStatus.PROPOSE_PATCH,
                started_at=11.5,
                finished_at=12.0,
                graph_patch=GraphPatchPayload(
                    reason="Translate French text",
                    add_nodes={"tr_fr": {"op": "demo_pack/ops:TranslateFr"}},
                    rewire_inputs={"summarize": {"text": "$tr_fr.text"}},
                ),
            )
        ]
    ).to_json()
    (val_dir / "agent_turns.json").write_text(turns_json, encoding="utf-8")

    runner = CliRunner()

    # 1. `plynx runs` shows Baseline Drift banner
    res_list = runner.invoke(cli_main, ["runs"])
    assert res_list.exit_code == 0, res_list.output
    assert "Baseline Drift" in res_list.output
    assert "demo_pack/ops:TranslateFr" in res_list.output

    # 2. `plynx runs --stats` human table and `--json`
    res_stats = runner.invoke(
        cli_main, ["runs", "--stats", "--workflow", "workflows/drift_demo.yaml"]
    )
    assert res_stats.exit_code == 0, res_stats.output
    assert "ingest" in res_stats.output
    assert "tr_fr" in res_stats.output
    assert "demo_pack/ops:TranslateFr" in res_stats.output

    res_stats_json = runner.invoke(
        cli_main,
        ["runs", "--stats", "--workflow", "workflows/drift_demo.yaml", "--json"],
    )
    assert res_stats_json.exit_code == 0, res_stats_json.output
    stats_payload = json.loads(res_stats_json.output)
    assert stats_payload["total_runs"] == 5
    assert len(stats_payload["drift_alerts"]) == 1
    alert = stats_payload["drift_alerts"][0]
    assert alert["injected_op"] == "demo_pack/ops:TranslateFr"
    assert alert["upstream_op"] == "standard_io/demo:ReadText"
    assert alert["downstream_op"] == "standard_io/demo:Echo"
    assert alert["occurrences"] == 3
    assert alert["window_runs"] == 5

    nodes_by_id = {n["node_id"]: n for n in stats_payload["nodes"]}
    assert nodes_by_id["tr_fr"]["dynamic_injections"] == 3
    assert nodes_by_id["summarize"]["cache_hits"] == 2

    # 3. FastAPI REST endpoints: `/runs`, `/runs/stats`, and `__stage_validator__s1` node routes
    app = create_app(tmp_path)
    with TestClient(app) as client:
        r_runs = client.get("/api/v1/runs", params={"workflow_path": "workflows/drift_demo.yaml"})
        assert r_runs.status_code == 200
        runs_body = r_runs.json()
        assert len(runs_body["runs"]) == 5
        assert len(runs_body["drift_alerts"]) == 1
        assert runs_body["drift_alerts"][0]["injected_op"] == "demo_pack/ops:TranslateFr"

        r_stats = client.get(
            "/api/v1/runs/stats",
            params={"workflow_path": "workflows/drift_demo.yaml"},
        )
        assert r_stats.status_code == 200
        assert r_stats.json()["total_runs"] == 5

        # Reserved `__stage_validator__s1` node ID must pass RUNTIME_NODE_ID_PATTERN validation!
        r_logs = client.get(f"/api/v1/runs/{last_run_id}/nodes/{val_id}/logs/stdout")
        assert r_logs.status_code == 200
        assert "Supervisor checked Stage s1" in r_logs.text

        r_out = client.get(f"/api/v1/runs/{last_run_id}/nodes/{val_id}/outputs/summary")
        assert r_out.status_code == 200
        assert r_out.json() == {"kind": "scalar", "value": "Spliced TranslateFr cleanly."}

        r_turns = client.get(f"/api/v1/runs/{last_run_id}/nodes/{val_id}/agent-turns")
        assert r_turns.status_code == 200
        assert r_turns.json()["turns"][0]["session_id"] == "val_sess_99"
