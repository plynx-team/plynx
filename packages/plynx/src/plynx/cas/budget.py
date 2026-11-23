"""Cache LRU size budget enforcement (PROTOCOL.md section 12, PLAN.md task 3.8)."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from plynx.cas.blob_store import BlobStore, make_writable
from plynx.cas.clean import _collect_node_dir_referenced_shas, _extract_shas_from_result_json
from plynx.config import load_workspace_config, parse_size_bytes
from plynx.store.run_store import RunStore

if TYPE_CHECKING:
    pass


@dataclass
class BudgetResult:
    """Summary of cache size budget enforcement."""

    blobs_evicted: int = 0
    bytes_reclaimed: int = 0
    total_size_before: int = 0
    total_size_after: int = 0
    max_size: int = 0
    dry_run: bool = False


def load_cache_max_size(workspace_root: Path) -> int | None:
    """Read ``cache.max_size`` from ``<workspace_root>/plynx.yaml`` if present."""
    return load_workspace_config(workspace_root).cache_max_size


def _collect_run_referenced_shas(store: RunStore) -> set[str]:
    """Collect all blob sha256 hashes referenced by existing run manifests on disk."""
    referenced: set[str] = set()
    if not store.runs_dir.is_dir():
        return referenced

    for run_dir in store.runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        nodes_dir = run_dir / "nodes"
        if not nodes_dir.is_dir():
            continue
        for node_dir in nodes_dir.iterdir():
            if not node_dir.is_dir():
                continue
            referenced.update(_collect_node_dir_referenced_shas(node_dir))
    return referenced


def enforce_cache_budget(
    workspace_root: Path,
    *,
    max_size: int | str | None = None,
    dry_run: bool = False,
    store: RunStore | None = None,
    blob_store: BlobStore | None = None,
) -> BudgetResult:
    """Enforce the LRU cache size budget on unreferenced blobs in the CAS blob store."""
    if max_size is None:
        effective_max_size = load_cache_max_size(workspace_root)
    else:
        effective_max_size = parse_size_bytes(max_size)

    if effective_max_size is None or effective_max_size < 0:
        return BudgetResult()

    active_store = store or RunStore(workspace_root)
    active_blob_store = blob_store or BlobStore.from_workspace(workspace_root)

    # 1. Measure all blobs on disk
    disk_blobs: dict[str, tuple[Path, int]] = {}
    total_size = 0
    if active_blob_store.blobs_dir.is_dir():
        for prefix_dir in active_blob_store.blobs_dir.iterdir():
            if not prefix_dir.is_dir():
                continue
            for blob_file in prefix_dir.iterdir():
                if not blob_file.is_file():
                    continue
                size = blob_file.stat().st_size
                disk_blobs[blob_file.name] = (blob_file, size)
                total_size += size

    total_size_before = total_size
    if total_size <= effective_max_size:
        return BudgetResult(
            total_size_before=total_size_before,
            total_size_after=total_size,
            max_size=effective_max_size,
            dry_run=dry_run,
        )

    # 2. Identify blobs referenced by active runs on disk (protected from eviction)
    run_referenced_shas = _collect_run_referenced_shas(active_store)

    # 3. Collect last_accessed_at and cache_key mapping from cache_index
    cache_access_map: dict[str, float] = {}
    cache_key_map: dict[str, list[str]] = {}
    with active_store._connect() as conn:
        rows = conn.execute(
            "SELECT cache_key, result_json, last_accessed_at FROM cache_index"
        ).fetchall()
        for r in rows:
            ckey = str(r["cache_key"])
            lat = float(r["last_accessed_at"])
            for sha in _extract_shas_from_result_json(str(r["result_json"])):
                cache_access_map[sha] = max(cache_access_map.get(sha, 0.0), lat)
                cache_key_map.setdefault(sha, []).append(ckey)

    # 4. Form unreferenced eviction candidates
    candidates: list[tuple[float, str, int, Path, list[str]]] = []
    for sha, (blob_path, size) in disk_blobs.items():
        if sha in run_referenced_shas:
            continue
        if sha in cache_access_map:
            last_accessed = cache_access_map[sha]
        else:
            last_accessed = blob_path.stat().st_mtime
        candidates.append((last_accessed, sha, size, blob_path, cache_key_map.get(sha, [])))

    # Sort candidates by last_accessed ascending (oldest first), then sha
    candidates.sort(key=lambda item: (item[0], item[1]))

    # 5. Evict until current_size <= effective_max_size
    blobs_evicted = 0
    bytes_reclaimed = 0
    current_size = total_size_before

    for _, _sha, size, blob_path, cache_keys in candidates:
        if current_size <= effective_max_size:
            break
        blobs_evicted += 1
        bytes_reclaimed += size
        current_size -= size
        if not dry_run:
            make_writable(blob_path)
            blob_path.unlink()
            for ckey in cache_keys:
                active_store.delete_cache_entry(ckey)
            with contextlib.suppress(OSError):
                blob_path.parent.rmdir()

    return BudgetResult(
        blobs_evicted=blobs_evicted,
        bytes_reclaimed=bytes_reclaimed,
        total_size_before=total_size_before,
        total_size_after=current_size,
        max_size=effective_max_size,
        dry_run=dry_run,
    )


__all__ = [
    "BudgetResult",
    "enforce_cache_budget",
    "load_cache_max_size",
    "parse_size_bytes",
]
