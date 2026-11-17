"""Tests for CAS BlobStore (PROTOCOL.md section 8, PLAN.md task 3.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from plynx.cas import BlobStore, hash_bytes, hash_file


def test_hash_file_and_bytes(tmp_path: Path) -> None:
    content = b"content for hashing test\n"
    f = tmp_path / "sample.txt"
    f.write_bytes(content)

    h_bytes = hash_bytes(content)
    h_file, size = hash_file(f)

    assert h_bytes == h_file
    assert size == len(content)
    assert len(h_file) == 64
    assert h_file.islower()


def test_blob_store_paths(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")
    sample_sha = "abcdef0123456789" + "0" * 48
    expected = tmp_path / "cache" / "blobs" / "ab" / sample_sha
    assert store.blob_path(sample_sha) == expected

    with pytest.raises(ValueError, match="Invalid sha256"):
        store.blob_path("a")


def test_duplicate_content_stored_once(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    content = b"identical content across files"

    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_bytes(content)
    file2.write_bytes(content)

    sha1, size1 = store.put_file(file1)
    sha2, size2 = store.put_file(file2)

    assert sha1 == sha2
    assert size1 == len(content)
    assert size2 == len(content)

    # Collect all stored blob files in the store
    stored_files = [p for p in store.blobs_dir.rglob("*") if p.is_file()]
    assert len(stored_files) == 1
    assert stored_files[0] == store.blob_path(sha1)


def test_stored_blobs_reject_writes(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    f = tmp_path / "input.txt"
    f.write_bytes(b"immutable payload")

    sha, _ = store.put_file(f)
    blob_path = store.blob_path(sha)

    assert blob_path.is_file()
    with pytest.raises(PermissionError), open(blob_path, "wb") as out:
        out.write(b"should fail")

    with pytest.raises(PermissionError), open(blob_path, "a") as out:
        out.write("should fail")


def test_fallback_on_os_link_error(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    f = tmp_path / "link_failure.txt"
    content = b"fallback on os.link failure content"
    f.write_bytes(content)

    # Force os.link to raise an OSError simulating EXDEV (cross-device link)
    with patch("os.link", side_effect=OSError(18, "Invalid cross-device link")):
        sha, size = store.put_file(f)

    blob_path = store.blob_path(sha)
    assert blob_path.is_file()
    assert size == len(content)
    assert blob_path.read_bytes() == content

    # Ensure copied fallback blob still rejects writes
    with pytest.raises(PermissionError), open(blob_path, "wb") as out:
        out.write(b"fail")


def test_put_bytes_and_read(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    data = b"raw byte buffer"

    sha, size = store.put_bytes(data)
    assert size == len(data)
    assert store.exists(sha)
    assert store.get_size(sha) == len(data)
    assert store.read_bytes(sha) == data

    with store.open(sha) as stream:
        assert stream.read() == data

    # Putting same bytes again returns existing blob
    sha_dup, size_dup = store.put_bytes(data)
    assert sha_dup == sha
    assert size_dup == size


def test_materialize(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")
    data = b"data to materialize"
    sha, _ = store.put_bytes(data)

    target = tmp_path / "dest" / "inputs" / "file.txt"
    store.materialize(sha, target)

    assert target.is_file()
    assert target.read_bytes() == data

    # Materialized target must also be read-only
    with pytest.raises(PermissionError), open(target, "wb") as out:
        out.write(b"fail")


def test_errors_on_missing_or_invalid_inputs(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "blobs")

    missing = tmp_path / "nonexistent.txt"
    with pytest.raises(FileNotFoundError):
        store.put_file(missing)

    directory = tmp_path / "somedir"
    directory.mkdir()
    with pytest.raises(IsADirectoryError):
        store.put_file(directory)

    fake_sha = "00" * 32
    with pytest.raises(FileNotFoundError):
        store.get_size(fake_sha)

    with pytest.raises(FileNotFoundError):
        store.open(fake_sha)

    with pytest.raises(FileNotFoundError):
        store.read_bytes(fake_sha)

    with pytest.raises(FileNotFoundError):
        store.materialize(fake_sha, tmp_path / "target.txt")
