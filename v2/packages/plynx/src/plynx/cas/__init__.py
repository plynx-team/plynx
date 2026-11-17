"""CAS (Content-Addressed Storage) package."""

from plynx.cas.blob_store import (
    BlobStore,
    hash_bytes,
    hash_file,
    link_or_copy,
    make_readonly,
    make_writable,
)
from plynx.cas.cache_key import (
    canonical_json,
    compute_cache_key,
    compute_cache_key_raw,
    compute_inputs_hash,
    compute_params_hash,
)
from plynx.cas.clean import CleanResult, clean
from plynx.cas.ingest import (
    compute_tree_hash,
    ingest_directory,
    ingest_file,
    ingest_outputs,
    materialize_directory,
    write_result_manifest,
)
from plynx.cas.materialize import (
    materialize_input_directory,
    materialize_input_file,
    materialize_inputs,
    safe_rmtree,
)

__all__ = [
    "BlobStore",
    "CleanResult",
    "canonical_json",
    "clean",
    "compute_cache_key",
    "compute_cache_key_raw",
    "compute_inputs_hash",
    "compute_params_hash",
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
    "materialize_input_directory",
    "materialize_input_file",
    "materialize_inputs",
    "safe_rmtree",
    "write_result_manifest",
]
