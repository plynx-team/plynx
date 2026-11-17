"""Tests for ``plynx.store`` (``RunStore``, run directories, and ``EventLog``)."""

from __future__ import annotations

import json
import multiprocessing
import sqlite3
from pathlib import Path

import pytest
from plynx.api_models import NodeStatus, RunStatus, StageGateStatus
from plynx.store import (
    AmbiguousRunIdError,
    EventLog,
    RunNotFoundError,
    RunStore,
    StoreVersionError,
)


def _event_writer_worker(events_path_str: str, run_id: str, node_id: str, count: int) -> list[int]:
    """Child process target that appends ``count`` events to ``EventLog``."""
    log = EventLog(Path(events_path_str))
    seqs: list[int] = []
    for i in range(count):
        ev = log.append(
            "node_status",
            {
                "run_id": run_id,
                "node_id": node_id,
                "status": "RUNNING",
                "cache_hit": False,
                "attempt": i + 1,
            },
        )
        assert ev.seq is not None
        seqs.append(ev.seq)
    return seqs


def _wal_node_updater_worker(workspace_str: str, run_id: str, node_ids: list[str]) -> bool:
    """Child process target that updates node statuses while another process accesses WAL DB."""
    store = RunStore(Path(workspace_str))
    for nid in node_ids:
        store.update_node_status(
            run_id,
            nid,
            NodeStatus.RUNNING,
            attempt=1,
            started_at=10.0,
        )
        state = store.get_run_state(run_id)
        assert state is not None
        store.update_node_status(
            run_id,
            nid,
            NodeStatus.SUCCESS,
            attempt=1,
            exit_code=0,
            finished_at=20.0,
        )
    return True


def _checkpoint_answer_worker(workspace_str: str, run_id: str, answer: str) -> tuple[str, bool]:
    """Child process target that attempts to answer a checkpoint."""
    store = RunStore(Path(workspace_str))
    won = store.answer_checkpoint(run_id, "pick", "cp_0", answer)
    return (answer, won)


def test_run_store_creates_directory_and_rows(tmp_path: Path) -> None:
    """create_run builds the run directory tree, snapshots, manifest, and SQLite rows."""
    store = RunStore(tmp_path)
    wf_bytes = b"version: 1\nname: demo\nnodes:\n  pick:\n    op: standard_io/demo:AskFooOrWoo\n"
    layout_bytes = b'{"schema": 1, "nodes": {}, "viewport": {"x": 0, "y": 0, "zoom": 1}}\n'

    run_id = store.create_run(
        workflow_path="workflows/demo.yaml",
        workflow_bytes=wf_bytes,
        node_ids=["pick", "echo"],
        run_inputs={"pick.prompt": "foo or woo?"},
        layout_bytes=layout_bytes,
        run_id="20261116_201500_a1b2c3",
        created_at=1731800000.0,
    )
    assert run_id == "20261116_201500_a1b2c3"

    rdir = store.run_dir(run_id)
    assert (rdir / "logs").is_dir()
    assert (rdir / "nodes" / "pick" / "inputs").is_dir()
    assert (rdir / "nodes" / "pick" / "workdir").is_dir()
    assert (rdir / "nodes" / "echo" / "inputs").is_dir()
    assert (rdir / "nodes" / "echo" / "workdir").is_dir()
    assert (rdir / "workflow.snapshot.yaml").read_bytes() == wf_bytes
    assert (rdir / "layout.snapshot.json").read_bytes() == layout_bytes
    assert (rdir / "events.jsonl").is_file()

    manifest = json.loads((rdir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    assert manifest["run_id"] == run_id
    assert manifest["workflow_path"] == "workflows/demo.yaml"
    assert manifest["run_inputs"] == {"pick.prompt": "foo or woo?"}

    state = store.get_run_state(run_id)
    assert state is not None
    assert state.id == run_id
    assert state.status == RunStatus.RUNNING
    assert set(state.nodes.keys()) == {"pick", "echo"}
    assert state.nodes["pick"].status == NodeStatus.PENDING
    assert state.nodes["echo"].status == NodeStatus.PENDING


def test_unknown_schema_version_fails_with_delete_instruction(tmp_path: Path) -> None:
    """An unknown PRAGMA user_version stops with 'delete `.plynx/plynx.db`'."""
    db_path = tmp_path / ".plynx" / "plynx.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA user_version = 99;")
    conn.close()

    with pytest.raises(StoreVersionError, match=r"delete `\.plynx/plynx\.db`"):
        RunStore(tmp_path)


def test_first_answer_wins(tmp_path: Path) -> None:
    """Only the first answer to a checkpoint succeeds; subsequent answers return False."""
    store = RunStore(tmp_path)
    run_id = store.create_run(
        workflow_path="workflows/foo_or_woo.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["pick"],
    )
    store.create_checkpoint(
        run_id,
        "pick",
        "cp_0",
        "foo or woo?",
        options=["foo", "woo"],
        allow_freeform=False,
    )

    assert store.answer_checkpoint(run_id, "pick", "cp_0", "foo") is True
    assert store.answer_checkpoint(run_id, "pick", "cp_0", "woo") is False

    cp = store.get_checkpoint(run_id, "pick", "cp_0")
    assert cp is not None
    assert cp.answer == "foo"
    assert cp.answered_at is not None


def test_first_answer_wins_across_two_processes(tmp_path: Path) -> None:
    """Two processes racing to answer the same checkpoint result in exactly one winner."""
    store = RunStore(tmp_path)
    run_id = store.create_run(
        workflow_path="workflows/foo_or_woo.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["pick"],
    )
    store.create_checkpoint(
        run_id,
        "pick",
        "cp_0",
        "foo or woo?",
        options=["foo", "woo"],
    )

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=2) as pool:
        r1 = pool.apply_async(_checkpoint_answer_worker, (str(tmp_path), run_id, "foo"))
        r2 = pool.apply_async(_checkpoint_answer_worker, (str(tmp_path), run_id, "woo"))
        outcomes = [r1.get(timeout=15), r2.get(timeout=15)]

    winners = [ans for ans, won in outcomes if won]
    losers = [ans for ans, won in outcomes if not won]
    assert len(winners) == 1
    assert len(losers) == 1

    cp = store.get_checkpoint(run_id, "pick", "cp_0")
    assert cp is not None
    assert cp.answer == winners[0]


def test_event_log_seq_ordering_under_two_writers(tmp_path: Path) -> None:
    """Two writer processes appending concurrently produce strictly ordered seq 1..2N."""
    events_path = tmp_path / "events.jsonl"
    per_worker = 25
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=2) as pool:
        res_a = pool.apply_async(
            _event_writer_worker,
            (str(events_path), "run_1", "node_a", per_worker),
        )
        res_b = pool.apply_async(
            _event_writer_worker,
            (str(events_path), "run_1", "node_b", per_worker),
        )
        seqs_a = res_a.get(timeout=20)
        seqs_b = res_b.get(timeout=20)

    total = per_worker * 2
    assert sorted(seqs_a + seqs_b) == list(range(1, total + 1))

    log = EventLog(events_path)
    all_events = log.read_after(0)
    assert len(all_events) == total
    assert [ev.seq for ev in all_events] == list(range(1, total + 1))

    later_events = log.read_after(per_worker)
    assert [ev.seq for ev in later_events] == list(range(per_worker + 1, total + 1))


def test_wal_access_from_two_processes(tmp_path: Path) -> None:
    """Two processes concurrently reading and writing to the WAL SQLite store succeed."""
    store = RunStore(tmp_path)
    nodes_a = [f"a_{i}" for i in range(10)]
    nodes_b = [f"b_{i}" for i in range(10)]
    run_id = store.create_run(
        workflow_path="workflows/foo_or_woo.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=nodes_a + nodes_b,
    )

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=2) as pool:
        p1 = pool.apply_async(_wal_node_updater_worker, (str(tmp_path), run_id, nodes_a))
        p2 = pool.apply_async(_wal_node_updater_worker, (str(tmp_path), run_id, nodes_b))
        assert p1.get(timeout=20) is True
        assert p2.get(timeout=20) is True

    state = store.get_run_state(run_id)
    assert state is not None
    for nid in nodes_a + nodes_b:
        assert state.nodes[nid].status == NodeStatus.SUCCESS
        assert state.nodes[nid].exit_code == 0


def test_stage_gates_and_prefix_resolution(tmp_path: Path) -> None:
    """Stage gates transition WAITING -> APPROVED and prefix resolution handles ambiguity."""
    store = RunStore(tmp_path)
    r1 = store.create_run(
        workflow_path="workflows/a.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        run_id="20261116_201500_aaaaaa",
    )
    r2 = store.create_run(
        workflow_path="workflows/b.yaml",
        workflow_bytes=b"version: 1\n",
        node_ids=["n1"],
        run_id="20261116_201500_bbbbbb",
    )

    store.create_stage_gate(r1, "ask")
    assert store.approve_stage_gate(r1, "ask") is True
    assert store.approve_stage_gate(r1, "ask") is False
    state = store.get_run_state(r1)
    assert state is not None
    assert state.stage_gates["ask"].status == StageGateStatus.APPROVED

    assert store.resolve_run_id("20261116_201500_aaa") == r1
    assert store.resolve_run_id("20261116_201500_bbb") == r2
    with pytest.raises(AmbiguousRunIdError):
        store.resolve_run_id("20261116_201500_")
    with pytest.raises(RunNotFoundError):
        store.resolve_run_id("nonexistent")
