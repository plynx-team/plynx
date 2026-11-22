"""Output ingestion into the blob store and result manifest generation (PROTOCOL.md section 5)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from plynx_sdk.protocol import (
    DirectoryEntry,
    OutputDirectoryValue,
    OutputFileValue,
    OutputValue,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ResultValue,
    ScalarValue,
)

from plynx.cas.blob_store import BlobStore, hash_bytes
from plynx.store.run_store import atomic_write_text


def compute_tree_hash(entries: Sequence[DirectoryEntry]) -> str:
    """Compute tree_sha256 per PROTOCOL.md section 5.

    tree_sha256 = SHA-256 of the UTF-8 text made of one line "<sha256> <path>\\n"
    per entry, sorted by path.
    """
    sorted_entries = sorted(entries, key=lambda e: e.path)
    tree_text = "".join(f"{entry.sha256} {entry.path}\n" for entry in sorted_entries)
    return hash_bytes(tree_text.encode("utf-8"))


def ingest_file(
    source: Path,
    blob_store: BlobStore,
    *,
    media: str | None = None,
    filename: str | None = None,
) -> ResultFileValue:
    """Ingest a single output file into the blob store."""
    if not source.is_file():
        if source.is_dir():
            raise IsADirectoryError(f"Expected file, got directory: {source}")
        raise FileNotFoundError(f"Output file does not exist: {source}")

    sha256, size_bytes = blob_store.put_file(source)
    fname = filename or source.name
    return ResultFileValue(
        sha256=sha256,
        size_bytes=size_bytes,
        media=media,
        filename=fname,
    )


def ingest_directory(
    dir_path: Path,
    blob_store: BlobStore,
    *,
    allow_hardlink: bool = True,
) -> ResultDirectoryValue:
    """Ingest a directory of files into the blob store as a tree of blobs."""
    if not dir_path.is_dir():
        if dir_path.exists():
            raise NotADirectoryError(f"Expected directory, got file: {dir_path}")
        raise FileNotFoundError(f"Output directory does not exist: {dir_path}")

    entries: list[DirectoryEntry] = []
    for root, _, files in os.walk(dir_path):
        for f in files:
            file_path = Path(root) / f
            rel_path = file_path.relative_to(dir_path).as_posix()
            sha256, size_bytes = blob_store.put_file(
                file_path,
                allow_hardlink=allow_hardlink,
            )
            entries.append(
                DirectoryEntry(
                    path=rel_path,
                    sha256=sha256,
                    size_bytes=size_bytes,
                )
            )

    entries.sort(key=lambda e: e.path)
    tree_sha = compute_tree_hash(entries)
    return ResultDirectoryValue(tree_sha256=tree_sha, entries=entries)


def materialize_directory(
    result_dir: ResultDirectoryValue,
    target_dir: Path,
    blob_store: BlobStore,
) -> None:
    """Materialize a directory output from the blob store at target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in result_dir.entries:
        dest_file = target_dir / entry.path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        blob_store.materialize(entry.sha256, dest_file)


def ingest_outputs(
    outputs: Mapping[str, OutputValue],
    *,
    node_dir: Path,
    blob_store: BlobStore,
) -> dict[str, ResultValue]:
    """Ingest all outputs of a node into the blob store, returning result values."""
    result_outputs: dict[str, ResultValue] = {}
    for port_name, out_val in outputs.items():
        if isinstance(out_val, ScalarValue):
            result_outputs[port_name] = ScalarValue(value=out_val.value)
        elif isinstance(out_val, OutputFileValue):
            file_path = node_dir / out_val.path
            result_outputs[port_name] = ingest_file(
                file_path,
                blob_store,
                media=out_val.media,
                filename=file_path.name,
            )
        elif isinstance(out_val, OutputDirectoryValue):
            dir_path = node_dir / out_val.path
            result_outputs[port_name] = ingest_directory(dir_path, blob_store)
        else:
            raise TypeError(f"Unsupported OutputValue kind: {type(out_val).__name__}")
    return result_outputs


def write_result_manifest(
    node_dir: Path,
    manifest: ResultManifest,
) -> Path:
    """Write ``result.json`` atomically into the node directory."""
    manifest.validate()
    target = node_dir / "result.json"
    atomic_write_text(target, manifest.to_json())
    return target
