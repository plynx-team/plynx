"""Tests for cache size budget and LRU eviction (PROTOCOL.md section 12, PLAN.md task 3.8)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from plynx.cas.blob_store import BlobStore
from plynx.cas.budget import (
    enforce_cache_budget,
    load_cache_max_size,
    parse_size_bytes,
)
from plynx.store.run_store import RunStore, generate_run_id
from plynx_sdk.protocol import ResultFileValue, ResultManifest, ResultValue


def _make_result_manifest(
    outputs: dict[str, ResultValue],
    cache_key: str = "key",
) -> ResultManifest:
    now = time.time()
    return ResultManifest(
        status="SUCCESS",
        cache_key=cache_key,
        cache_hit=False,
        started_at=now,
        finished_at=now,
        outputs=outputs,
    )


def test_parse_size_bytes() -> None:
    assert parse_size_bytes(1024) == 1024
    assert parse_size_bytes(1024.0) == 1024
    assert parse_size_bytes("1024") == 1024
    assert parse_size_bytes("1024B") == 1024
    assert parse_size_bytes("1024 bytes") == 1024
    assert parse_size_bytes("100KB") == 100 * 1024
    assert parse_size_bytes("100 KiB") == 100 * 1024
    assert parse_size_bytes("500MB") == 500 * 1024**2
    assert parse_size_bytes("10GB") == 10 * 1024**3
    assert parse_size_bytes("10gb") == 10 * 1024**3
    assert parse_size_bytes("1.5GB") == int(1.5 * 1024**3)
    assert parse_size_bytes("2TB") == 2 * 1024**4

    with pytest.raises(ValueError, match="Invalid size string"):
        parse_size_bytes("invalid_size")

    with pytest.raises(ValueError, match="Unknown size unit"):
        parse_size_bytes("10PB")

    with pytest.raises(ValueError, match="non-negative"):
        parse_size_bytes(-5)


def test_load_cache_max_size(tmp_path: Path) -> None:
    # No file
    assert load_cache_max_size(tmp_path) is None

    # plynx.yaml with cache.max_size
    cfg = tmp_path / "plynx.yaml"
    cfg.write_text("cache:\n  max_size: 10GB\n", encoding="utf-8")
    assert load_cache_max_size(tmp_path) == 10 * 1024**3

    # Inline mapping
    cfg.write_text("cache: { max_size: 500MB }\n", encoding="utf-8")
    assert load_cache_max_size(tmp_path) == 500 * 1024**2

    # String scalar
    cfg.write_text("cache: 100KB\n", encoding="utf-8")
    assert load_cache_max_size(tmp_path) == 100 * 1024

    # No cache key
    cfg.write_text("concurrency: 4\n", encoding="utf-8")
    assert load_cache_max_size(tmp_path) is None


def test_budget_oldest_unreferenced_blobs_go_first(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()

    # Create 3 unreferenced blobs of 100 bytes each
    sha1, _ = blob_store.put_bytes(b"1" * 100)
    sha2, _ = blob_store.put_bytes(b"2" * 100)
    sha3, _ = blob_store.put_bytes(b"3" * 100)

    # Set distinct mtimes: sha1 (t - 300), sha2 (t - 200), sha3 (t - 100)
    p1 = blob_store.blob_path(sha1)
    p2 = blob_store.blob_path(sha2)
    p3 = blob_store.blob_path(sha3)
    os.utime(p1, (now - 300, now - 300))
    os.utime(p2, (now - 200, now - 200))
    os.utime(p3, (now - 100, now - 100))

    # Create 1 referenced blob of 100 bytes, referenced by an active run, even older mtime
    sha_ref, size_ref = blob_store.put_bytes(b"R" * 100)
    p_ref = blob_store.blob_path(sha_ref)
    os.utime(p_ref, (now - 500, now - 500))

    run_id = generate_run_id(now=now)
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
            VALUES (?, 'wf.yaml', 'sha_wf', 'SUCCESS', ?, 0)
            """,
            (run_id, now),
        )
    run_dir = store.run_dir(run_id)
    node_dir = run_dir / "nodes" / "n1"
    node_dir.mkdir(parents=True, exist_ok=True)
    res_manifest = _make_result_manifest(
        outputs={
            "out": ResultFileValue(
                sha256=sha_ref,
                size_bytes=size_ref,
                media=None,
                filename="r.txt",
            )
        }
    )
    (node_dir / "result.json").write_text(res_manifest.to_json(), encoding="utf-8")

    # Total size = 400 bytes.
    # Set budget = 250 bytes (requires evicting 2 unreferenced blobs of 100 bytes each)
    res = enforce_cache_budget(
        tmp_path,
        max_size=250,
        store=store,
        blob_store=blob_store,
    )

    assert res.blobs_evicted == 2
    assert res.bytes_reclaimed == 200
    assert res.total_size_before == 400
    assert res.total_size_after == 200

    # Oldest unreferenced blobs (sha1 and sha2) must be gone
    assert not p1.exists()
    assert not p2.exists()

    # Newest unreferenced blob (sha3) must survive
    assert p3.exists()

    # Referenced blob must survive despite being oldest of all!
    assert p_ref.exists()


def test_budget_lru_by_last_accessed_at_from_cache_index(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()

    # Blob A and Blob B
    sha_a, _ = blob_store.put_bytes(b"blob-a-content" * 10)  # 140 bytes
    sha_b, _ = blob_store.put_bytes(b"blob-b-content" * 10)  # 140 bytes

    # Blob A was accessed more recently (now - 10) in cache_index
    # Blob B was accessed longer ago (now - 1000) in cache_index
    manifest_a = _make_result_manifest(
        outputs={"out": ResultFileValue(sha256=sha_a, size_bytes=140, media=None, filename="a.txt")}
    )
    manifest_b = _make_result_manifest(
        outputs={"out": ResultFileValue(sha256=sha_b, size_bytes=140, media=None, filename="b.txt")}
    )

    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO cache_index (cache_key, result_json, created_at, last_accessed_at)
            VALUES (?, ?, ?, ?)
            """,
            ("key_a", manifest_a.to_json(), now - 10, now - 10),
        )
        conn.execute(
            """
            INSERT INTO cache_index (cache_key, result_json, created_at, last_accessed_at)
            VALUES (?, ?, ?, ?)
            """,
            ("key_b", manifest_b.to_json(), now - 1000, now - 1000),
        )

    # Budget allows only 1 blob (~150 bytes)
    res = enforce_cache_budget(tmp_path, max_size=150, store=store, blob_store=blob_store)

    assert res.blobs_evicted == 1
    # Blob B was older in cache_index -> evicted
    assert not blob_store.blob_path(sha_b).exists()
    # Blob A was accessed more recently -> survived
    assert blob_store.blob_path(sha_a).exists()

    # Cache index row for B was cleaned up; row for A remains
    with store._connect() as conn:
        rows = conn.execute("SELECT cache_key FROM cache_index").fetchall()
        keys = [r["cache_key"] for r in rows]
        assert "key_b" not in keys
        assert "key_a" in keys


def test_budget_dry_run_leaves_files_intact(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)

    sha, _ = blob_store.put_bytes(b"dry-run-blob" * 10)
    p = blob_store.blob_path(sha)

    res = enforce_cache_budget(
        tmp_path,
        max_size=10,
        dry_run=True,
        store=store,
        blob_store=blob_store,
    )
    assert res.dry_run is True
    assert res.blobs_evicted == 1
    assert p.exists()


@pytest.mark.anyio
async def test_scheduler_enforces_cache_max_size_from_plynx_yaml(tmp_path: Path) -> None:
    from plynx.engine import Scheduler, SchedulerOptions
    from plynx.workflow.models import NodeSpec, Workflow

    from tests.fakes import FakeExecutor, FakeRegistry

    # Write plynx.yaml with a 50-byte cache limit
    (tmp_path / "plynx.yaml").write_text("cache:\n  max_size: 50B\n", encoding="utf-8")

    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)

    # Pre-populate an orphan unreferenced blob of 100 bytes
    orphan_sha, _ = blob_store.put_bytes(b"old-orphan-data" * 7)
    p_orphan = blob_store.blob_path(orphan_sha)
    assert p_orphan.exists()

    # Run a workflow through Scheduler
    registry = FakeRegistry()
    executor = FakeExecutor()
    scheduler = Scheduler(store, executor, registry=registry, blob_store=blob_store)

    wf = Workflow(
        nodes={
            "n1": NodeSpec(
                op="standard_io/demo:Echo",
                inputs={"text": "hello"},
            )
        }
    )
    res_state = await scheduler.run(wf, options=SchedulerOptions(non_interactive=True))
    assert res_state.status.value == "SUCCESS"

    # The orphan blob exceeding budget should have been evicted automatically
    assert not p_orphan.exists()
