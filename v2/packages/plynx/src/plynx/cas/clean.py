"""Garbage collection and clean command (PROTOCOL.md sections 10 & 11, PLAN.md task 3.7)."""

from __future__ import annotations

import contextlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from plynx_sdk.protocol import (
    InputFileValue,
    InputsManifest,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
)

from plynx.cas.blob_store import BlobStore, hash_file, make_writable
from plynx.cas.materialize import safe_rmtree
from plynx.store.run_store import RunStore

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class CleanResult:
    """Summary of clean execution."""

    runs_deleted: int = 0
    cache_entries_deleted: int = 0
    blobs_deleted: int = 0
    bytes_reclaimed: int = 0
    dry_run: bool = False


def _extract_shas_from_result_json(raw_json: str) -> Iterable[str]:
    """Parse a result_json string and yield all referenced blob sha256 hashes."""
    try:
        manifest = ResultManifest.from_json(raw_json)
        for out in manifest.outputs.values():
            if isinstance(out, ResultFileValue):
                yield out.sha256
            elif isinstance(out, ResultDirectoryValue):
                for entry in out.entries:
                    yield entry.sha256
    except Exception:
        pass


def clean(
    workspace_root: Path,
    *,
    days: int = 14,
    dry_run: bool = False,
    store: RunStore | None = None,
    blob_store: BlobStore | None = None,
) -> CleanResult:
    """Perform mark-and-sweep cleanup on runs, cache_index, and content-addressed blobs."""
    active_store = store or RunStore(workspace_root)
    active_blob_store = blob_store or BlobStore.from_workspace(workspace_root)
    cutoff_ts = time.time() - (days * 86400.0)

    # 1. Identify old unpinned runs
    old_unpinned_runs: list[str] = []
    with active_store._connect() as conn:
        rows = conn.execute(
            "SELECT id FROM runs WHERE pinned = 0 AND created_at < ?",
            (cutoff_ts,),
        ).fetchall()
        old_unpinned_runs = [str(r["id"]) for r in rows]

    runs_deleted = len(old_unpinned_runs)
    if not dry_run:
        for run_id in old_unpinned_runs:
            run_dir = active_store.run_dir(run_id)
            if run_dir.exists():
                safe_rmtree(run_dir)
            active_store.delete_run(run_id)

    # 2. Identify stale cache_index rows (older than cutoff_ts)
    stale_cache_keys: list[str] = []
    with active_store._connect() as conn:
        c_rows = conn.execute(
            "SELECT cache_key FROM cache_index WHERE last_accessed_at < ?",
            (cutoff_ts,),
        ).fetchall()
        stale_cache_keys = [str(r["cache_key"]) for r in c_rows]

    cache_entries_deleted = len(stale_cache_keys)
    if not dry_run:
        for key in stale_cache_keys:
            active_store.delete_cache_entry(key)

    # 3. Mark phase: collect all referenced blob sha256 hashes
    referenced_shas: set[str] = set()

    # Mark from surviving cache_index rows (i.e. not stale)
    with active_store._connect() as conn:
        surviving_cache = conn.execute(
            "SELECT result_json FROM cache_index WHERE last_accessed_at >= ?",
            (cutoff_ts,),
        ).fetchall()
        for r in surviving_cache:
            for sha in _extract_shas_from_result_json(str(r["result_json"])):
                referenced_shas.add(sha)

    # Mark from surviving runs (pinned OR created_at >= cutoff_ts)
    surviving_run_ids: set[str] = set()
    with active_store._connect() as conn:
        surv_rows = conn.execute(
            "SELECT id FROM runs WHERE pinned = 1 OR created_at >= ?",
            (cutoff_ts,),
        ).fetchall()
        surviving_run_ids = {str(r["id"]) for r in surv_rows}

    if active_store.runs_dir.is_dir():
        for run_dir in active_store.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            if run_dir.name not in surviving_run_ids:
                continue
            nodes_dir = run_dir / "nodes"
            if not nodes_dir.is_dir():
                continue
            for node_dir in nodes_dir.iterdir():
                if not node_dir.is_dir():
                    continue
                # Result manifest
                res_file = node_dir / "result.json"
                if res_file.is_file():
                    with contextlib.suppress(Exception):
                        text = res_file.read_text(encoding="utf-8")
                        for sha in _extract_shas_from_result_json(text):
                            referenced_shas.add(sha)
                # Inputs manifest
                inp_file = node_dir / "inputs.json"
                if inp_file.is_file():
                    with contextlib.suppress(Exception):
                        inp_manifest = InputsManifest.from_json(inp_file.read_bytes())
                        for inp_val in inp_manifest.inputs.values():
                            if isinstance(inp_val, InputFileValue):
                                referenced_shas.add(inp_val.sha256)
                # Any materialized inputs on disk
                inp_dir = node_dir / "inputs"
                if inp_dir.is_dir():
                    for root, _, files in os.walk(inp_dir):
                        for f in files:
                            fp = Path(root) / f
                            with contextlib.suppress(Exception):
                                sha, _ = hash_file(fp)
                                referenced_shas.add(sha)

    # 4. Sweep phase: delete unreferenced blobs
    blobs_deleted = 0
    bytes_reclaimed = 0

    if active_blob_store.blobs_dir.is_dir():
        for prefix_dir in sorted(active_blob_store.blobs_dir.iterdir()):
            if not prefix_dir.is_dir():
                continue
            for blob_file in sorted(prefix_dir.iterdir()):
                if not blob_file.is_file():
                    continue
                sha = blob_file.name
                if sha not in referenced_shas:
                    blobs_deleted += 1
                    size = blob_file.stat().st_size
                    bytes_reclaimed += size
                    if not dry_run:
                        make_writable(blob_file)
                        blob_file.unlink()

            if not dry_run:
                with contextlib.suppress(OSError):
                    prefix_dir.rmdir()

    return CleanResult(
        runs_deleted=runs_deleted,
        cache_entries_deleted=cache_entries_deleted,
        blobs_deleted=blobs_deleted,
        bytes_reclaimed=bytes_reclaimed,
        dry_run=dry_run,
    )
