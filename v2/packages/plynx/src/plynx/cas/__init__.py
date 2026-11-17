"""CAS (Content-Addressed Storage) package."""

from plynx.cas.blob_store import (
    BlobStore,
    hash_bytes,
    hash_file,
    link_or_copy,
    make_readonly,
    make_writable,
)
from plynx.cas.ingest import (
    compute_tree_hash,
    ingest_directory,
    ingest_file,
    ingest_outputs,
    materialize_directory,
    write_result_manifest,
)

__all__ = [
    "BlobStore",
    "compute_tree_hash",
    "hash_bytes",
    "hash_file",
    "ingest_directory",
    "ingest_file",
    "ingest_outputs",
    "link_or_copy",
    "make_readonly",
    "make_writable",
    "materialize_directory",
    "write_result_manifest",
]
