"""Tests for garbage collection and plynx clean (PLAN.md task 3.7)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.cas.blob_store import BlobStore
from plynx.cas.clean import clean
from plynx.cli import main
from plynx.store.run_store import RunStore, generate_run_id
from plynx_sdk.protocol import (
    DirectoryEntry,
    InputsManifest,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ResultValue,
)


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


def _create_node_run_files(
    run_dir: Path,
    node_id: str,
    *,
    result_manifest: ResultManifest | None = None,
    inputs_manifest: InputsManifest | None = None,
) -> None:
    node_dir = run_dir / "nodes" / node_id
    node_dir.mkdir(parents=True, exist_ok=True)
    if result_manifest is not None:
        (node_dir / "result.json").write_text(result_manifest.to_json(), encoding="utf-8")
    if inputs_manifest is not None:
        (node_dir / "inputs.json").write_text(inputs_manifest.to_json(), encoding="utf-8")


def test_clean_removes_unreferenced_blobs_and_stale_cache_entries(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()
    old_time = now - (20 * 86400)  # 20 days ago

    # 1. Store blobs
    sha_unreferenced, _ = blob_store.put_bytes(b"orphan-blob")
    sha_old_run_out, _ = blob_store.put_bytes(b"old-run-output")
    sha_fresh_run_out, _ = blob_store.put_bytes(b"fresh-run-output")
    sha_fresh_cache_out, _ = blob_store.put_bytes(b"fresh-cache-output")
    sha_stale_cache_out, _ = blob_store.put_bytes(b"stale-cache-output")

    # 2. Old unpinned run (20 days old)
    old_run_id = generate_run_id(now=old_time)
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
            VALUES (?, 'wf.yaml', 'sha_wf', 'SUCCESS', ?, 0)
            """,
            (old_run_id, old_time),
        )
    old_run_dir = store.run_dir(old_run_id)
    _create_node_run_files(
        old_run_dir,
        "n1",
        result_manifest=_make_result_manifest(
            outputs={
                "out": ResultFileValue(
                    sha256=sha_old_run_out,
                    size_bytes=14,
                    media=None,
                    filename="out.txt",
                )
            }
        ),
    )

    # 3. Fresh unpinned run (created now)
    fresh_run_id = generate_run_id(now=now)
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
            VALUES (?, 'wf.yaml', 'sha_wf', 'SUCCESS', ?, 0)
            """,
            (fresh_run_id, now),
        )
    fresh_run_dir = store.run_dir(fresh_run_id)
    _create_node_run_files(
        fresh_run_dir,
        "n2",
        result_manifest=_make_result_manifest(
            outputs={
                "out": ResultFileValue(
                    sha256=sha_fresh_run_out,
                    size_bytes=16,
                    media=None,
                    filename="out.txt",
                )
            }
        ),
    )

    # 4. Cache index entries
    fresh_manifest = _make_result_manifest(
        outputs={
            "res": ResultFileValue(
                sha256=sha_fresh_cache_out,
                size_bytes=18,
                media=None,
                filename="f.txt",
            )
        }
    )
    stale_manifest = _make_result_manifest(
        outputs={
            "res": ResultFileValue(
                sha256=sha_stale_cache_out,
                size_bytes=18,
                media=None,
                filename="s.txt",
            )
        }
    )

    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO cache_index (cache_key, result_json, created_at, last_accessed_at)
            VALUES (?, ?, ?, ?)
            """,
            ("key_fresh", fresh_manifest.to_json(), now, now),
        )
        conn.execute(
            """
            INSERT INTO cache_index (cache_key, result_json, created_at, last_accessed_at)
            VALUES (?, ?, ?, ?)
            """,
            ("key_stale", stale_manifest.to_json(), old_time, old_time),
        )

    # Run clean with 14 days cutoff
    result = clean(tmp_path, days=14, store=store, blob_store=blob_store)

    assert result.runs_deleted == 1
    assert result.cache_entries_deleted == 1
    # Blobs deleted: orphan, old_run_out, stale_cache_out (total 3)
    assert result.blobs_deleted == 3
    assert not result.dry_run

    # Check database state
    with store._connect() as conn:
        runs = [r["id"] for r in conn.execute("SELECT id FROM runs").fetchall()]
        assert old_run_id not in runs
        assert fresh_run_id in runs

        cache_rows = conn.execute("SELECT cache_key FROM cache_index").fetchall()
        cache_keys = [r["cache_key"] for r in cache_rows]
        assert "key_stale" not in cache_keys
        assert "key_fresh" in cache_keys

    # Check run directory state
    assert not old_run_dir.exists()
    assert fresh_run_dir.exists()

    # Check blob existence
    assert not blob_store.blob_path(sha_unreferenced).exists()
    assert not blob_store.blob_path(sha_old_run_out).exists()
    assert not blob_store.blob_path(sha_stale_cache_out).exists()
    assert blob_store.blob_path(sha_fresh_run_out).exists()
    assert blob_store.blob_path(sha_fresh_cache_out).exists()


def test_clean_pinned_runs_kept_even_if_old(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()
    old_time = now - (30 * 86400)  # 30 days ago

    sha_pinned_out, _ = blob_store.put_bytes(b"pinned-output-data")

    pinned_run_id = generate_run_id(now=old_time)
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
            VALUES (?, 'wf.yaml', 'sha_wf', 'SUCCESS', ?, 1)
            """,
            (pinned_run_id, old_time),
        )
    pinned_run_dir = store.run_dir(pinned_run_id)
    _create_node_run_files(
        pinned_run_dir,
        "n_pinned",
        result_manifest=_make_result_manifest(
            outputs={
                "res": ResultFileValue(
                    sha256=sha_pinned_out,
                    size_bytes=18,
                    media=None,
                    filename="pinned.txt",
                )
            }
        ),
    )

    result = clean(tmp_path, days=14, store=store, blob_store=blob_store)

    assert result.runs_deleted == 0
    assert result.blobs_deleted == 0
    assert pinned_run_dir.exists()
    assert blob_store.blob_path(sha_pinned_out).exists()


def test_clean_dry_run_changes_nothing(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()
    old_time = now - (20 * 86400)

    sha_orphan, _ = blob_store.put_bytes(b"orphan-dry-run")
    old_run_id = generate_run_id(now=old_time)
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
            VALUES (?, 'wf.yaml', 'sha_wf', 'SUCCESS', ?, 0)
            """,
            (old_run_id, old_time),
        )
    old_run_dir = store.run_dir(old_run_id)
    _create_node_run_files(old_run_dir, "n1")

    result = clean(tmp_path, days=14, dry_run=True, store=store, blob_store=blob_store)

    assert result.dry_run is True
    assert result.runs_deleted == 1
    assert result.blobs_deleted == 1
    assert result.bytes_reclaimed > 0

    # Everything must still exist on disk and in db
    assert old_run_dir.exists()
    assert blob_store.blob_path(sha_orphan).exists()
    with store._connect() as conn:
        rows = conn.execute("SELECT id FROM runs WHERE id = ?", (old_run_id,)).fetchall()
        assert len(rows) == 1


def test_clean_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    sha, _ = blob_store.put_bytes(b"some-orphan")

    runner = CliRunner()
    res = runner.invoke(main, ["clean", "--dry-run"])
    assert res.exit_code == 0
    assert "[dry-run]" in res.output
    assert blob_store.blob_path(sha).exists()

    res_real = runner.invoke(main, ["clean", "--days", "0"])
    assert res_real.exit_code == 0
    assert "[dry-run]" not in res_real.output
    assert not blob_store.blob_path(sha).exists()


def test_clean_directory_output_entries_survive(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()

    sha_file_a, size_a = blob_store.put_bytes(b"content-a")
    sha_file_b, size_b = blob_store.put_bytes(b"content-b")

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
    _create_node_run_files(
        run_dir,
        "n_dir",
        result_manifest=_make_result_manifest(
            outputs={
                "out_dir": ResultDirectoryValue(
                    tree_sha256="dummy_tree_sha",
                    entries=[
                        DirectoryEntry(path="a.txt", sha256=sha_file_a, size_bytes=size_a),
                        DirectoryEntry(path="sub/b.txt", sha256=sha_file_b, size_bytes=size_b),
                    ],
                )
            }
        ),
    )

    result = clean(tmp_path, days=14, store=store, blob_store=blob_store)
    assert result.blobs_deleted == 0
    assert blob_store.blob_path(sha_file_a).exists()
    assert blob_store.blob_path(sha_file_b).exists()


def test_clean_active_runs_protected_even_if_old(tmp_path: Path) -> None:
    """Active runs (RUNNING, WAITING_FOR_USER, PENDING) are preserved regardless of age."""
    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()
    old_time = now - (30 * 86400)

    active_statuses = ["RUNNING", "WAITING_FOR_USER", "PENDING"]
    blob_shas = []

    for status in active_statuses:
        sha, _ = blob_store.put_bytes(f"active-{status}-data".encode())
        blob_shas.append(sha)
        run_id = generate_run_id(now=old_time)
        with store._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, workflow_path, workflow_sha256, status, created_at, pinned)
                VALUES (?, 'wf.yaml', 'sha_wf', ?, ?, 0)
                """,
                (run_id, status, old_time),
            )
        run_dir = store.run_dir(run_id)
        _create_node_run_files(
            run_dir,
            "n_active",
            result_manifest=_make_result_manifest(
                outputs={
                    "res": ResultFileValue(
                        sha256=sha,
                        size_bytes=10,
                        media=None,
                        filename="out.txt",
                    )
                }
            ),
        )

    res = clean(tmp_path, days=14, store=store, blob_store=blob_store)
    assert res.runs_deleted == 0
    assert res.blobs_deleted == 0
    for sha in blob_shas:
        assert blob_store.blob_path(sha).exists()


def test_clean_rejects_negative_days(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """clean rejects negative days parameter and CLI exits non-zero."""
    with pytest.raises(ValueError, match="non-negative"):
        clean(tmp_path, days=-1)

    monkeypatch.chdir(tmp_path)
    RunStore(tmp_path)
    runner = CliRunner()
    res = runner.invoke(main, ["clean", "--days", "-1"])
    assert res.exit_code != 0


def test_clean_and_budget_use_manifests_without_rehashing_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GC and budget protect file and directory input blobs via manifests without hashing disk."""
    import plynx.cas.blob_store as blob_store_mod
    from plynx.cas.budget import enforce_cache_budget
    from plynx_sdk.protocol import InputDirectoryValue, InputFileValue

    store = RunStore(tmp_path)
    blob_store = BlobStore.from_workspace(tmp_path)
    now = time.time()

    sha_file_in, size_file_in = blob_store.put_bytes(b"input-file-bytes")
    sha_dir_a, size_dir_a = blob_store.put_bytes(b"dir-entry-a")
    sha_orphan, _ = blob_store.put_bytes(b"orphan-to-delete")

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
    _create_node_run_files(
        run_dir,
        "n1",
        inputs_manifest=InputsManifest(
            inputs={
                "doc": InputFileValue(
                    path="inputs/doc/a.txt",
                    sha256=sha_file_in,
                    size_bytes=size_file_in,
                ),
                "frames": InputDirectoryValue(
                    path="inputs/frames",
                    tree_sha256="dummy_tree",
                    entries=[DirectoryEntry(path="a.txt", sha256=sha_dir_a, size_bytes=size_dir_a)],
                ),
            }
        ),
    )
    # Place materialized files in inputs/ to verify they are never hashed during GC/budget.
    mat_dir = run_dir / "nodes" / "n1" / "inputs" / "doc"
    mat_dir.mkdir(parents=True, exist_ok=True)
    (mat_dir / "a.txt").write_bytes(b"input-file-bytes")

    def _forbid_hash_file(*args: object, **kwargs: object) -> object:
        raise AssertionError("hash_file must not be called during clean or budget enforcement")

    monkeypatch.setattr(blob_store_mod, "hash_file", _forbid_hash_file)

    budget_res = enforce_cache_budget(
        tmp_path,
        max_size=1,
        dry_run=True,
        store=store,
        blob_store=blob_store,
    )
    # Only the orphan blob is eligible for eviction; both input blobs are protected.
    assert budget_res.blobs_evicted == 1

    clean_res = clean(tmp_path, days=14, store=store, blob_store=blob_store)
    assert clean_res.blobs_deleted == 1
    assert not blob_store.exists(sha_orphan)
    assert blob_store.exists(sha_file_in)
    assert blob_store.exists(sha_dir_a)
