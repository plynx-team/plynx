"""Tests for input materialization (PROTOCOL.md section 5, PLAN.md task 3.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from plynx.api_models import InputPortSpec, OpEntry
from plynx.cas import (
    BlobStore,
    compute_tree_hash,
    materialize_input_directory,
    materialize_input_file,
    materialize_inputs,
)
from plynx.registry import FakeRegistry
from plynx.workflow.models import NodeRef, NodeSpec
from plynx_sdk.protocol import (
    DirectoryEntry,
    InputDirectoryValue,
    InputFileValue,
    ResultDirectoryValue,
    ResultFileValue,
    ScalarValue,
)


def test_materialize_input_file_preserves_extension_and_rejects_writes(tmp_path: Path) -> None:
    """Accept: file extension is preserved and writing to the materialized file fails."""
    store = BlobStore(tmp_path / "cache" / "blobs")
    content = b"%PDF-1.4 dummy pdf bytes"
    sha, size = store.put_bytes(content)

    node_dir = tmp_path / "runs" / "run_1" / "nodes" / "inspect"
    filename = "report_v1.final.pdf"

    inp = materialize_input_file(
        dst_node_dir=node_dir,
        port_name="doc",
        sha256=sha,
        size_bytes=size,
        filename=filename,
        blob_store=store,
    )

    assert isinstance(inp, InputFileValue)
    assert inp.path == f"inputs/doc/{filename}"
    assert Path(inp.path).suffix == ".pdf"
    assert inp.sha256 == sha
    assert inp.size_bytes == size

    disk_path = node_dir / inp.path
    assert disk_path.is_file()
    assert disk_path.read_bytes() == content

    # Accept: a node that tries to write to an input fails
    with pytest.raises(PermissionError), open(disk_path, "wb") as f:
        f.write(b"should fail")

    with pytest.raises(PermissionError), open(disk_path, "a") as f:
        f.write("should fail")


def test_materialize_inputs_from_upstream_reference(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")
    content = b"header,val\n1,2\n"
    sha, size = store.put_bytes(content)

    node_dir = tmp_path / "runs" / "run_1" / "nodes" / "process"
    spec = NodeSpec(
        op="custom/ops:Process",
        inputs={
            "data": NodeRef(from_node="extract", output="csv_data"),
            "factor": 10,
        },
    )

    completed_outputs = {
        "extract": {
            "csv_data": ResultFileValue(
                sha256=sha,
                size_bytes=size,
                media="text/csv",
                filename="raw_data.csv",
            ),
        },
    }

    manifest = materialize_inputs(
        node_id="process",
        spec=spec,
        dst_node_dir=node_dir,
        completed_outputs=completed_outputs,
        blob_store=store,
        workspace_root=tmp_path,
    )

    assert "data" in manifest.inputs
    data_inp = manifest.inputs["data"]
    assert isinstance(data_inp, InputFileValue)
    assert data_inp.path == "inputs/data/raw_data.csv"
    assert Path(data_inp.path).suffix == ".csv"

    factor_inp = manifest.inputs["factor"]
    assert isinstance(factor_inp, ScalarValue)
    assert factor_inp.value == 10

    # Verify disk materialization
    disk_file = node_dir / data_inp.path
    assert disk_file.is_file()
    assert disk_file.read_bytes() == content
    with pytest.raises(PermissionError), open(disk_file, "w") as f:
        f.write("fail")


def test_materialize_directory_input(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")
    sha1, size1 = store.put_bytes(b"frame 1")
    sha2, size2 = store.put_bytes(b"frame 2")

    entries = [
        DirectoryEntry(path="0001.png", sha256=sha1, size_bytes=size1),
        DirectoryEntry(path="sub/0002.png", sha256=sha2, size_bytes=size2),
    ]
    tree_sha = compute_tree_hash(entries)
    res_dir = ResultDirectoryValue(tree_sha256=tree_sha, entries=entries)

    node_dir = tmp_path / "runs" / "run_1" / "nodes" / "render"
    inp = materialize_input_directory(
        dst_node_dir=node_dir,
        port_name="frames",
        result_dir=res_dir,
        blob_store=store,
    )

    assert isinstance(inp, InputDirectoryValue)
    assert inp.path == "inputs/frames"
    assert inp.tree_sha256 == tree_sha

    f1 = node_dir / "inputs" / "frames" / "0001.png"
    f2 = node_dir / "inputs" / "frames" / "sub" / "0002.png"
    assert f1.is_file()
    assert f2.is_file()
    assert f1.read_bytes() == b"frame 1"
    assert f2.read_bytes() == b"frame 2"

    with pytest.raises(PermissionError), open(f1, "wb") as f:
        f.write(b"fail")


def test_materialize_literal_file_input(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "cache" / "blobs")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sample_file = workspace / "sample.txt"
    sample_file.write_text("sample workspace file", encoding="utf-8")

    registry = FakeRegistry(
        [
            OpEntry(
                id="standard_io/demo:ReadText",
                pack="standard_io",
                module="demo",
                name="ReadText",
                kind="class",
                title="Read text",
                category="Files",
                cacheable=True,
                description="",
                inputs=[
                    InputPortSpec(
                        name="path",
                        type="file",
                        media="text/plain",
                        required=True,
                    ),
                ],
                outputs=[],
                source="standard_io/demo.py",
                valid=True,
            ),
        ]
    )

    node_dir = tmp_path / "runs" / "run_1" / "nodes" / "reader"
    spec = NodeSpec(
        op="standard_io/demo:ReadText",
        inputs={"path": "sample.txt"},
    )

    manifest = materialize_inputs(
        node_id="reader",
        spec=spec,
        dst_node_dir=node_dir,
        completed_outputs={},
        blob_store=store,
        workspace_root=workspace,
        registry=registry,
    )

    path_inp = manifest.inputs["path"]
    assert isinstance(path_inp, InputFileValue)
    assert path_inp.path == "inputs/path/sample.txt"
    assert Path(path_inp.path).suffix == ".txt"

    disk_file = node_dir / path_inp.path
    assert disk_file.is_file()
    with pytest.raises(PermissionError), open(disk_file, "a") as f:
        f.write("fail")


def test_harness_fails_when_op_attempts_write_to_input(tmp_path: Path) -> None:
    """Accept: a node (executed via harness) that tries to write to an input fails with exit 1."""
    import os
    import subprocess
    import sys

    pack_dir = tmp_path / "custom_pack"
    pack_dir.mkdir()
    fixture_code = """
from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op

class WriteToInputOp(Op):
    TITLE = "Write to input"
    class Outputs(TypedDict):
        out: str
    def run(self, doc: Path) -> Outputs:
        with open(doc, "w") as f:
            f.write("modified")
        return {"out": "ok"}
"""
    (pack_dir / "bad_op.py").write_text(fixture_code, encoding="utf-8")

    store = BlobStore(tmp_path / "cache" / "blobs")
    sha, size = store.put_bytes(b"initial content")

    node_dir = tmp_path / "node_exec"
    workdir = node_dir / "workdir"
    workdir.mkdir(parents=True)

    inp = materialize_input_file(
        dst_node_dir=node_dir,
        port_name="doc",
        sha256=sha,
        size_bytes=size,
        filename="input_data.json",
        blob_store=store,
    )

    from plynx_sdk.protocol import InputsManifest

    inputs_manifest = InputsManifest(inputs={"doc": inp})
    (node_dir / "inputs.json").write_text(inputs_manifest.to_json(), encoding="utf-8")

    sdk_src = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk" / "src"
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{sdk_src}{os.pathsep}{pack_dir}"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "plynx_sdk.harness",
            "--op",
            "bad_op:WriteToInputOp",
            "--dir",
            str(node_dir),
        ],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    # Must exit 1 due to PermissionError
    assert proc.returncode == 1
    assert "PermissionError" in proc.stderr
