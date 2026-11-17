"""Cache LRU size budget enforcement (PROTOCOL.md section 12, PLAN.md task 3.8)."""

from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from plynx.cas.blob_store import BlobStore, hash_file, make_writable
from plynx.cas.clean import _extract_shas_from_result_json
from plynx.store.run_store import RunStore

if TYPE_CHECKING:
    pass

_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]*)\s*$")

_SIZE_UNITS: dict[str, int] = {
    "": 1,
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "k": 1024,
    "kb": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
    "tib": 1024**4,
}


@dataclass
class BudgetResult:
    """Summary of cache size budget enforcement."""

    blobs_evicted: int = 0
    bytes_reclaimed: int = 0
    total_size_before: int = 0
    total_size_after: int = 0
    max_size: int = 0
    dry_run: bool = False


def parse_size_bytes(val: str | int | float) -> int:
    """Parse a size representation into integer bytes.

    Supports integer bytes or strings with unit suffixes (e.g. '10GB', '500MB', '100KB').
    """
    if isinstance(val, (int, float)):
        if val < 0:
            raise ValueError(f"Size must be non-negative, got {val}")
        return int(val)

    match = _SIZE_RE.match(val)
    if not match:
        raise ValueError(f"Invalid size string: {val!r}")

    number_str, unit_str = match.groups()
    unit = unit_str.lower()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit {unit_str!r} in {val!r}")

    bytes_per_unit = _SIZE_UNITS[unit]
    number = float(number_str)
    return int(number * bytes_per_unit)


def load_cache_max_size(workspace_root: Path) -> int | None:
    """Read ``cache.max_size`` from ``<workspace_root>/plynx.yaml`` if present."""
    cfg_path = workspace_root / "plynx.yaml"
    if not cfg_path.is_file():
        return None
    yaml = YAML(typ="safe")
    try:
        parsed = yaml.load(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(parsed, Mapping):
        return None
    raw_cache = parsed.get("cache")
    if isinstance(raw_cache, Mapping):
        max_size_val = raw_cache.get("max_size")
        if max_size_val is not None:
            try:
                return parse_size_bytes(max_size_val)
            except ValueError:
                return None
    elif isinstance(raw_cache, (str, int)):
        try:
            return parse_size_bytes(raw_cache)
        except ValueError:
            return None
    return None


def _collect_run_referenced_shas(store: RunStore) -> set[str]:
    """Collect all blob sha256 hashes referenced by existing runs on disk."""
    referenced: set[str] = set()
    if not store.runs_dir.is_dir():
        return referenced

    from plynx_sdk.protocol import InputFileValue, InputsManifest

    for run_dir in store.runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        nodes_dir = run_dir / "nodes"
        if not nodes_dir.is_dir():
            continue
        for node_dir in nodes_dir.iterdir():
            if not node_dir.is_dir():
                continue
            res_file = node_dir / "result.json"
            if res_file.is_file():
                with contextlib.suppress(Exception):
                    text = res_file.read_text(encoding="utf-8")
                    for sha in _extract_shas_from_result_json(text):
                        referenced.add(sha)
            inp_file = node_dir / "inputs.json"
            if inp_file.is_file():
                with contextlib.suppress(Exception):
                    inp_manifest = InputsManifest.from_json(inp_file.read_bytes())
                    for inp_val in inp_manifest.inputs.values():
                        if isinstance(inp_val, InputFileValue):
                            referenced.add(inp_val.sha256)
            inp_dir = node_dir / "inputs"
            if inp_dir.is_dir():
                for root, _, files in os.walk(inp_dir):
                    for f in files:
                        fp = Path(root) / f
                        with contextlib.suppress(Exception):
                            sha, _ = hash_file(fp)
                            referenced.add(sha)
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
