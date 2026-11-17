"""CAS (Content-Addressed Storage) package."""

from plynx.cas.blob_store import (
    BlobStore,
    hash_bytes,
    hash_file,
    link_or_copy,
    make_readonly,
    make_writable,
)

__all__ = [
    "BlobStore",
    "hash_bytes",
    "hash_file",
    "link_or_copy",
    "make_readonly",
    "make_writable",
]
