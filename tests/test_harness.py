"""Tests for Task 1.2: ``python -m plynx_sdk.harness`` execution and exit codes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from plynx_sdk.protocol import (
    InputFileValue,
    InputsManifest,
    OutputDirectoryValue,
    OutputFileValue,
    OutputsManifest,
    ScalarValue,
)

SDK_SRC = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk" / "src"

FIXTURE_MODULE_CODE = '''"""Fixture ops for testing plynx_sdk.harness."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from plynx_sdk import Directory, MarkdownFile, Op, op


class ConcatOp(Op):
    """Join two strings."""

    TITLE = "Concat text"

    class Outputs(TypedDict):
        text: str

    def run(self, a: str, b: str = " ") -> Outputs:
        return {"text": a + b}


class FileAndDirOp(Op):
    """Read an input file and produce a markdown file and a directory."""

    TITLE = "File and dir op"

    class Outputs(TypedDict):
        report: MarkdownFile
        bundle: Directory

    def run(self, src: Path) -> Outputs:
        content = src.read_text(encoding="utf-8")
        report_path = Path("report.md")
        report_path.write_text(f"# Report\\n{content}", encoding="utf-8")
        bundle_dir = Path("bundle")
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "item.txt").write_text(content, encoding="utf-8")
        return {"report": report_path, "bundle": bundle_dir}


@op(title="Single return greet")
def greet(name: str) -> str:
    """Return a single string."""
    return f"hello {name}"


class FailingOp(Op):
    """Always raises RuntimeError."""

    TITLE = "Failing op"

    class Outputs(TypedDict):
        text: str

    def run(self, msg: str = "boom") -> Outputs:
        raise RuntimeError(msg)


class BadKeysOp(Op):
    """Returns wrong output dictionary keys."""

    TITLE = "Bad keys"

    class Outputs(TypedDict):
        text: str

    def run(self) -> Outputs:
        return {"wrong_key": "value"}  # type: ignore[typeddict-item]


class BadTypeOp(Op):
    """Returns int instead of declared str."""

    TITLE = "Bad type"

    class Outputs(TypedDict):
        text: str

    def run(self) -> Outputs:
        return {"text": 123}  # type: ignore[typeddict-item]


class MissingOutputFileOp(Op):
    """Returns a file path that was never written to workdir/."""

    TITLE = "Missing file"

    class Outputs(TypedDict):
        report: MarkdownFile

    def run(self) -> Outputs:
        return {"report": Path("does_not_exist.md")}
'''


def _write_fixture_pack(base_dir: Path) -> Path:
    pack_src = base_dir / "fixture_pack"
    pkg_dir = pack_src / "demo_pack"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "ops.py").write_text(FIXTURE_MODULE_CODE, encoding="utf-8")
    return pack_src


def _run_harness_subprocess(
    pack_src: Path,
    op_spec: str,
    node_dir: Path,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    pythonpath_parts = [str(SDK_SRC), str(pack_src)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "plynx_sdk.harness",
            "--op",
            op_spec,
            "--dir",
            str(node_dir),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_harness_success_class_and_function_ops(tmp_path: Path) -> None:
    """Harness runs class and function ops directly (no uv), writes outputs.json, exits 0."""
    pack_src = _write_fixture_pack(tmp_path)

    # 1. Class op (ConcatOp)
    node_dir_1 = tmp_path / "node_concat"
    node_dir_1.mkdir()
    inputs_1 = InputsManifest(
        inputs={
            "a": ScalarValue(value="foo"),
            "b": ScalarValue(value="bar"),
        }
    )
    (node_dir_1 / "inputs.json").write_text(inputs_1.to_json(), encoding="utf-8")

    proc_1 = _run_harness_subprocess(pack_src, "demo_pack.ops:ConcatOp", node_dir_1)
    assert proc_1.returncode == 0, f"stderr={proc_1.stderr}"
    outputs_1 = OutputsManifest.from_json((node_dir_1 / "outputs.json").read_text(encoding="utf-8"))
    assert outputs_1.outputs == {"text": ScalarValue(value="foobar")}
    assert outputs_1.finished_at >= outputs_1.started_at

    # 2. Function op with single return annotation -> 'result'
    node_dir_2 = tmp_path / "node_greet"
    node_dir_2.mkdir()
    inputs_2 = InputsManifest(inputs={"name": ScalarValue(value="world")})
    (node_dir_2 / "inputs.json").write_text(inputs_2.to_json(), encoding="utf-8")

    proc_2 = _run_harness_subprocess(pack_src, "demo_pack/ops:greet", node_dir_2)
    assert proc_2.returncode == 0, f"stderr={proc_2.stderr}"
    outputs_2 = OutputsManifest.from_json((node_dir_2 / "outputs.json").read_text(encoding="utf-8"))
    assert outputs_2.outputs == {"result": ScalarValue(value="hello world")}

    # 3. File and directory op
    node_dir_3 = tmp_path / "node_files"
    in_file = node_dir_3 / "inputs" / "src" / "note.txt"
    in_file.parent.mkdir(parents=True)
    in_file.write_text("hello from file", encoding="utf-8")
    inputs_3 = InputsManifest(
        inputs={
            "src": InputFileValue(
                path="inputs/src/note.txt",
                sha256="abc123",
                size_bytes=15,
            )
        }
    )
    (node_dir_3 / "inputs.json").write_text(inputs_3.to_json(), encoding="utf-8")

    proc_3 = _run_harness_subprocess(pack_src, "demo_pack.ops:FileAndDirOp", node_dir_3)
    assert proc_3.returncode == 0, f"stderr={proc_3.stderr}"
    outputs_3 = OutputsManifest.from_json((node_dir_3 / "outputs.json").read_text(encoding="utf-8"))
    assert outputs_3.outputs == {
        "report": OutputFileValue(path="workdir/report.md", media="text/markdown"),
        "bundle": OutputDirectoryValue(path="workdir/bundle"),
    }
    assert (node_dir_3 / "workdir" / "report.md").is_file()
    assert (node_dir_3 / "workdir" / "bundle" / "item.txt").read_text(encoding="utf-8") == (
        "hello from file"
    )


def test_harness_op_exception_exits_1(tmp_path: Path) -> None:
    """When an op raises an unhandled exception, harness prints traceback and exits 1."""
    pack_src = _write_fixture_pack(tmp_path)
    node_dir = tmp_path / "node_fail"
    node_dir.mkdir()
    inputs = InputsManifest(inputs={"msg": ScalarValue(value="expected failure")})
    (node_dir / "inputs.json").write_text(inputs.to_json(), encoding="utf-8")

    proc = _run_harness_subprocess(pack_src, "demo_pack.ops:FailingOp", node_dir)
    assert proc.returncode == 1
    assert "RuntimeError: expected failure" in proc.stderr
    assert not (node_dir / "outputs.json").exists()


def test_harness_bad_outputs_exits_2(tmp_path: Path) -> None:
    """When an op returns bad keys, bad types, or missing files, harness exits 2."""
    pack_src = _write_fixture_pack(tmp_path)

    for idx, op_name in enumerate(("BadKeysOp", "BadTypeOp", "MissingOutputFileOp")):
        node_dir = tmp_path / f"node_bad_{idx}"
        node_dir.mkdir()
        (node_dir / "inputs.json").write_text(InputsManifest().to_json(), encoding="utf-8")

        proc = _run_harness_subprocess(pack_src, f"demo_pack.ops:{op_name}", node_dir)
        assert proc.returncode == 2, f"op={op_name} stderr={proc.stderr}"
        assert not (node_dir / "outputs.json").exists()


def test_harness_missing_op_or_bad_inputs_exits_2(tmp_path: Path) -> None:
    """Missing module, missing op symbol, or missing inputs.json exits 2."""
    pack_src = _write_fixture_pack(tmp_path)
    node_dir = tmp_path / "node_missing"
    node_dir.mkdir()
    (node_dir / "inputs.json").write_text(InputsManifest().to_json(), encoding="utf-8")

    proc_missing_sym = _run_harness_subprocess(pack_src, "demo_pack.ops:NoSuchOp", node_dir)
    assert proc_missing_sym.returncode == 2

    proc_missing_mod = _run_harness_subprocess(pack_src, "no_such_pack.ops:ConcatOp", node_dir)
    assert proc_missing_mod.returncode == 2

    empty_dir = tmp_path / "node_no_inputs"
    empty_dir.mkdir()
    proc_no_inputs = _run_harness_subprocess(pack_src, "demo_pack.ops:ConcatOp", empty_dir)
    assert proc_no_inputs.returncode == 2
