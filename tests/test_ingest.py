"""Tests for output ingestion and tree hashing (PROTOCOL.md section 5, PLAN.md task 3.2)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from plynx.cas import (
    BlobStore,
    compute_tree_hash,
    ingest_directory,
    ingest_file,
    ingest_outputs,
    materialize_directory,
    write_result_manifest,
)
from plynx_sdk.protocol import (
    DirectoryEntry,
    OutputDirectoryValue,
    OutputFileValue,
    OutputsManifest,
    ResultDirectoryValue,
    ResultFileValue,
    ResultManifest,
    ScalarValue,
)


def test_tree_sha256_matches_protocol_definition() -> None:
    """Verify tree_sha256 exactly matches PROTOCOL.md definition."""
    sha_b = hashlib.sha256(b"b_content").hexdigest()
    sha_a = hashlib.sha256(b"a_content").hexdigest()

    entry_b = DirectoryEntry(path="b.txt", sha256=sha_b, size_bytes=9)
    entry_a = DirectoryEntry(path="sub/a.txt", sha256=sha_a, size_bytes=9)

    # PROTOCOL.md: sorted by path
    # 'b.txt' comes before 'sub/a.txt' in lexicographical order
    expected_text = f"{sha_b} b.txt\n{sha_a} sub/a.txt\n"
    expected_tree_sha = hashlib.sha256(expected_text.encode("utf-8")).hexdigest()

    # Pass in unsorted order to verify compute_tree_hash sorts by path
    computed = compute_tree_hash([entry_a, entry_b])
    assert computed == expected_tree_sha


def test_directory_with_nested_files_round_trips(tmp_path: Path) -> None:
    """Accept: directory with nested files round-trips."""
    store = BlobStore(tmp_path / "cache" / "blobs")

    source_dir = tmp_path / "workdir" / "frames"
    (source_dir / "meta" / "deep").mkdir(parents=True)

    (source_dir / "0001.png").write_bytes(b"frame 1 data")
    (source_dir / "0002.png").write_bytes(b"frame 2 data")
    (source_dir / "meta" / "info.json").write_bytes(b'{"fps": 30}')
    (source_dir / "meta" / "deep" / "notes.txt").write_bytes(b"deep notes")

    # Ingest directory
    res_dir = ingest_directory(source_dir, store)

    assert isinstance(res_dir, ResultDirectoryValue)
    assert len(res_dir.entries) == 4
    # Check sorting
    paths = [e.path for e in res_dir.entries]
    assert paths == sorted(paths)
    assert paths == ["0001.png", "0002.png", "meta/deep/notes.txt", "meta/info.json"]

    # Verify each file is stored in CAS
    for entry in res_dir.entries:
        assert store.exists(entry.sha256)
        assert store.get_size(entry.sha256) == entry.size_bytes

    # Round-trip: materialize into a fresh directory
    rebuilt_dir = tmp_path / "rebuilt_frames"
    materialize_directory(res_dir, rebuilt_dir, store)

    assert (rebuilt_dir / "0001.png").read_bytes() == b"frame 1 data"
    assert (rebuilt_dir / "0002.png").read_bytes() == b"frame 2 data"
    assert (rebuilt_dir / "meta" / "info.json").read_bytes() == b'{"fps": 30}'
    assert (rebuilt_dir / "meta" / "deep" / "notes.txt").read_bytes() == b"deep notes"

    # Re-ingest rebuilt directory and verify tree_sha256 and entries match exactly
    reingested = ingest_directory(rebuilt_dir, store)
    assert reingested.tree_sha256 == res_dir.tree_sha256
    assert reingested.entries == res_dir.entries


def test_ingest_outputs_and_write_result_manifest(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")
    node_dir = tmp_path / "node_1"
    workdir = node_dir / "workdir"
    workdir.mkdir(parents=True)

    report_file = workdir / "report.md"
    report_file.write_bytes(b"# Markdown Report\n")

    dir_output = workdir / "dataset"
    dir_output.mkdir()
    (dir_output / "sample.csv").write_bytes(b"col1,col2\n1,2\n")

    outputs = OutputsManifest(
        started_at=100.0,
        finished_at=105.0,
        outputs={
            "text": ScalarValue(value="hello"),
            "report": OutputFileValue(path="workdir/report.md", media="text/markdown"),
            "dataset": OutputDirectoryValue(path="workdir/dataset"),
        },
    )

    result_outputs = ingest_outputs(outputs.outputs, node_dir=node_dir, blob_store=store)

    assert isinstance(result_outputs["text"], ScalarValue)
    assert result_outputs["text"].value == "hello"

    assert isinstance(result_outputs["report"], ResultFileValue)
    assert result_outputs["report"].filename == "report.md"
    assert result_outputs["report"].media == "text/markdown"
    assert store.exists(result_outputs["report"].sha256)

    assert isinstance(result_outputs["dataset"], ResultDirectoryValue)
    assert len(result_outputs["dataset"].entries) == 1
    assert result_outputs["dataset"].entries[0].path == "sample.csv"
    assert store.exists(result_outputs["dataset"].entries[0].sha256)

    manifest = ResultManifest(
        status="SUCCESS",
        cache_key="key123",
        cache_hit=False,
        started_at=100.0,
        finished_at=105.0,
        outputs=result_outputs,
    )
    result_path = write_result_manifest(node_dir, manifest)
    assert result_path == node_dir / "result.json"
    assert result_path.is_file()

    loaded = ResultManifest.from_json(result_path.read_bytes())
    assert loaded.status == "SUCCESS"
    assert loaded.cache_key == "key123"
    assert loaded.cache_hit is False
    assert loaded.outputs["text"] == result_outputs["text"]
    assert loaded.outputs["report"] == result_outputs["report"]
    assert loaded.outputs["dataset"] == result_outputs["dataset"]


def test_ingest_empty_directory(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    res = ingest_directory(empty_dir, store)
    assert res.entries == []
    empty_sha = hashlib.sha256(b"").hexdigest()
    assert res.tree_sha256 == empty_sha


def test_ingest_missing_file_or_dir(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")

    with pytest.raises(FileNotFoundError):
        ingest_file(tmp_path / "nonexistent.txt", store)

    with pytest.raises(FileNotFoundError):
        ingest_directory(tmp_path / "nonexistent_dir", store)
