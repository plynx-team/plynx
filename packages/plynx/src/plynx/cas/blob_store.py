"""Content-addressed blob store and utilities (PROTOCOL.md section 8)."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import time
from pathlib import Path
from typing import BinaryIO


def hash_file(path: Path) -> tuple[str, int]:
    """Compute the SHA-256 hex digest and size in bytes of a file.

    Reads the file in 64 KiB chunks to avoid loading large files into memory.
    """
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def hash_bytes(data: bytes) -> str:
    """Return lowercase hex SHA-256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def make_readonly(path: Path) -> None:
    """Set file permissions to read-only (0o444).

    Removes write permissions for owner, group, and others so subsequent writes fail.
    """
    current_mode = path.stat().st_mode
    readonly_mode = (current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)) | stat.S_IRUSR
    os.chmod(path, readonly_mode)


def make_writable(path: Path) -> None:
    """Add write permission for the owner to allow deletion or overwriting."""
    current_mode = path.stat().st_mode
    os.chmod(path, current_mode | stat.S_IWUSR)


def link_or_copy(
    source: Path,
    target: Path,
    *,
    make_target_readonly: bool = True,
    allow_hardlink: bool = True,
) -> None:
    """Link source to target with os.link (when allowed), falling back to atomic copy."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if allow_hardlink:
        try:
            os.link(source, target)
            if make_target_readonly:
                make_readonly(target)
            return
        except FileExistsError:
            return
        except OSError:
            pass

    # Copy via temporary file in target directory for atomic write
    temp_target = target.parent / f".tmp.{target.name}.{os.getpid()}.{time.time_ns()}"
    try:
        shutil.copy2(source, temp_target)
        if target.is_file():
            return
        try:
            os.replace(temp_target, target)
        except OSError:
            if target.is_file():
                return
            raise
        if make_target_readonly:
            make_readonly(target)
    finally:
        if temp_target.is_file():
            try:
                make_writable(temp_target)
                temp_target.unlink()
            except OSError:
                pass


class BlobStore:
    """Content-Addressed Storage (CAS) for file blobs.

    Stored files are located at ``<blobs_dir>/<first 2 hex>/<sha256>`` and marked read-only.
    """

    def __init__(self, blobs_dir: Path) -> None:
        self.blobs_dir = blobs_dir.resolve()

    @classmethod
    def from_workspace(cls, workspace_root: Path) -> BlobStore:
        """Create a BlobStore using the default workspace location ``.plynx/cache/blobs``."""
        return cls(workspace_root / ".plynx" / "cache" / "blobs")

    @classmethod
    def from_cache_dir(cls, cache_dir: Path) -> BlobStore:
        """Create a BlobStore rooted in ``<cache_dir>/blobs``."""
        return cls(cache_dir / "blobs")

    def blob_path(self, sha256: str) -> Path:
        """Return the absolute path for a blob: ``blobs/<ab>/<sha256>``."""
        if len(sha256) < 2:
            raise ValueError(f"Invalid sha256: {sha256}")
        return self.blobs_dir / sha256[:2] / sha256

    def exists(self, sha256: str) -> bool:
        """Check if a blob exists in the store."""
        return self.blob_path(sha256).is_file()

    def get_size(self, sha256: str) -> int:
        """Return the size in bytes of a stored blob."""
        path = self.blob_path(sha256)
        if not path.is_file():
            raise FileNotFoundError(f"Blob not found: {sha256}")
        return path.stat().st_size

    def open(self, sha256: str) -> BinaryIO:
        """Open a stored blob for binary reading."""
        path = self.blob_path(sha256)
        if not path.is_file():
            raise FileNotFoundError(f"Blob not found: {sha256}")
        return open(path, "rb")

    def read_bytes(self, sha256: str) -> bytes:
        """Read and return all bytes of a stored blob."""
        path = self.blob_path(sha256)
        if not path.is_file():
            raise FileNotFoundError(f"Blob not found: {sha256}")
        return path.read_bytes()

    def put_file(
        self,
        source: Path,
        sha256: str | None = None,
        *,
        allow_hardlink: bool = True,
    ) -> tuple[str, int]:
        """Store a file in the blob store.

        Returns ``(sha256, size_bytes)``. If duplicate content is already stored,
        it is not copied or linked again. Pass ``allow_hardlink=False`` for external
        user/workspace files so PLynx never marks them read-only or shares their inode.
        """
        if not source.is_file():
            if source.is_dir():
                raise IsADirectoryError(f"Cannot store directory as a single blob: {source}")
            raise FileNotFoundError(f"Source file does not exist: {source}")

        if sha256 is None:
            file_sha256, size_bytes = hash_file(source)
        else:
            file_sha256 = sha256
            size_bytes = source.stat().st_size

        target = self.blob_path(file_sha256)
        if target.is_file():
            return file_sha256, target.stat().st_size

        link_or_copy(
            source,
            target,
            make_target_readonly=True,
            allow_hardlink=allow_hardlink,
        )
        return file_sha256, size_bytes

    def put_bytes(self, data: bytes) -> tuple[str, int]:
        """Store bytes in the blob store. Returns ``(sha256, size_bytes)``."""
        data_sha256 = hash_bytes(data)
        target = self.blob_path(data_sha256)
        if target.is_file():
            return data_sha256, target.stat().st_size

        target.parent.mkdir(parents=True, exist_ok=True)
        temp_target = target.parent / f".tmp.{data_sha256}.{os.getpid()}.{time.time_ns()}"
        try:
            temp_target.write_bytes(data)
            if target.is_file():
                return data_sha256, target.stat().st_size
            try:
                os.replace(temp_target, target)
            except OSError:
                if target.is_file():
                    return data_sha256, target.stat().st_size
                raise
            make_readonly(target)
            return data_sha256, len(data)
        finally:
            if temp_target.is_file():
                try:
                    make_writable(temp_target)
                    temp_target.unlink()
                except OSError:
                    pass

    def materialize(self, sha256: str, target: Path) -> None:
        """Materialize a stored blob at the target path as read-only."""
        source = self.blob_path(sha256)
        if not source.is_file():
            raise FileNotFoundError(f"Blob not found: {sha256}")
        link_or_copy(source, target, make_target_readonly=True)
