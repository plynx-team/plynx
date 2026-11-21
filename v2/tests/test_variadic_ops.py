"""Tests for variadic operations and dynamic extra inputs (ALLOW_EXTRA_INPUTS)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec
from plynx.cas import compute_cache_key
from plynx.registry import FakeRegistry, extract_ops_from_source
from plynx.workflow.models import NodeSpec, Stage, Workflow
from plynx.workflow.validator import validate_workflow
from plynx_sdk.protocol import (
    InputsManifest,
    OutputsManifest,
    ScalarValue,
)

SDK_SRC = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk" / "src"


def test_extractor_variadic_class_op() -> None:
    """Class op with ALLOW_EXTRA_INPUTS = True extracts allow_extra_inputs and extra_inputs_type."""
    source = """
from plynx_sdk import Op
from plynx_sdk.types import AudioWav

class MergeTracks(Op):
    TITLE = "Merge Tracks"
    CATEGORY = "Audio"
    ALLOW_EXTRA_INPUTS = True

    def run(self, master_gain: float = 1.0, **tracks: AudioWav) -> AudioWav:
        '''Merge arbitrary audio tracks.'''
        return b"merged"
"""
    ops = extract_ops_from_source(source, pack="media_studio", module="audio")
    assert len(ops) == 1
    entry = ops[0]
    assert entry.valid is True
    assert entry.allow_extra_inputs is True
    assert len(entry.inputs) == 1
    assert entry.inputs[0].name == "master_gain"
    assert entry.inputs[0].type == "float"
    assert entry.extra_inputs_type is not None
    assert entry.extra_inputs_type.name == "tracks"
    assert entry.extra_inputs_type.type == "file"
    assert entry.extra_inputs_type.media == "audio/wav"


def test_extractor_variadic_function_op() -> None:
    """Function op with @op(allow_extra_inputs=True) extracts metadata."""
    source = """
from plynx_sdk import op

@op("Format All", category="Text", allow_extra_inputs=True)
def format_all(prefix: str, **fields: str) -> str:
    '''Format fields.'''
    return prefix + ": " + ", ".join(f"{k}={v}" for k, v in fields.items())
"""
    ops = extract_ops_from_source(source, pack="standard_io", module="text")
    assert len(ops) == 1
    entry = ops[0]
    assert entry.valid is True
    assert entry.allow_extra_inputs is True
    assert entry.extra_inputs_type is not None
    assert entry.extra_inputs_type.name == "fields"
    assert entry.extra_inputs_type.type == "str"


def test_extractor_untyped_variadic_op() -> None:
    """Variadic op with untyped **kwargs allows arbitrary input types (extra_inputs_type=None)."""
    source = """
from plynx_sdk import op

@op("Dynamic Collector", allow_extra_inputs=True)
def collect(**kwargs) -> dict:
    return kwargs
"""
    ops = extract_ops_from_source(source, pack="standard_io", module="util")
    assert len(ops) == 1
    entry = ops[0]
    assert entry.valid is True
    assert entry.allow_extra_inputs is True
    assert entry.extra_inputs_type is None


def test_extractor_rejects_varargs_without_allow_extra() -> None:
    """Signature with **kwargs without allow_extra_inputs=True fails extraction."""
    source = """
from plynx_sdk import op

@op("Invalid")
def bad_func(**kwargs) -> str:
    return ""
"""
    ops = extract_ops_from_source(source, pack="test", module="bad")
    assert len(ops) == 1
    assert ops[0].valid is False
    assert "not supported in Op signatures unless allow_extra_inputs=True" in (ops[0].error or "")


def test_extractor_rejects_allow_extra_without_kwargs() -> None:
    """allow_extra_inputs=True without **kwargs in signature fails extraction."""
    source = """
from plynx_sdk import op

@op("Missing Kwargs", allow_extra_inputs=True)
def missing_kwargs(a: int) -> int:
    return a
"""
    ops = extract_ops_from_source(source, pack="test", module="bad")
    assert len(ops) == 1
    assert ops[0].valid is False
    assert "signature is missing **kwargs" in (ops[0].error or "")


def test_workflow_validation_with_variadic_op() -> None:
    """Validator accepts arbitrary inputs on variadic ops and validates their types."""
    concat_op = OpEntry(
        id="test/ops:ConcatMany",
        pack="test",
        module="ops",
        name="ConcatMany",
        kind="class",
        title="Concat Many",
        category="Text",
        cacheable=True,
        description="Join arbitrary strings.",
        inputs=[
            InputPortSpec(name="sep", type="str", required=False, default=","),
        ],
        outputs=[
            OutputPortSpec(name="result", type="str", media=None),
        ],
        allow_extra_inputs=True,
        extra_inputs_type=InputPortSpec(name="parts", type="str", required=False, default=None),
        source="test.py",
        valid=True,
        error=None,
    )

    producer_op = OpEntry(
        id="test/ops:Producer",
        pack="test",
        module="ops",
        name="Producer",
        kind="class",
        title="Producer",
        category="Text",
        cacheable=True,
        description="Produce string.",
        inputs=[],
        outputs=[
            OutputPortSpec(name="text", type="str", media=None),
            OutputPortSpec(name="count", type="int", media=None),
        ],
        source="test.py",
        valid=True,
        error=None,
    )

    reg = FakeRegistry([concat_op, producer_op])

    wf_valid = Workflow(
        version=1,
        name="valid_variadic",
        stages={"main": Stage(title="Main")},
        nodes={
            "p": NodeSpec(op="test/ops:Producer", stage="main", inputs={}),
            "c": NodeSpec(
                op="test/ops:ConcatMany",
                stage="main",
                inputs={
                    "sep": " - ",
                    "item_1": "literal_text",
                    "item_2": {"from_node": "p", "output": "text"},
                },
            ),
        },
    )
    issues = validate_workflow(wf_valid, reg)
    assert len(issues) == 0

    # Type mismatch: item_int wired to integer output
    wf_invalid_type = Workflow(
        version=1,
        name="invalid_type",
        stages={"main": Stage(title="Main")},
        nodes={
            "p": NodeSpec(op="test/ops:Producer", stage="main", inputs={}),
            "c": NodeSpec(
                op="test/ops:ConcatMany",
                stage="main",
                inputs={
                    "item_int": {"from_node": "p", "output": "count"},
                },
            ),
        },
    )
    issues_type = validate_workflow(wf_invalid_type, reg)
    assert any("type mismatch" in issue.message for issue in issues_type)


def test_harness_variadic_op_execution(tmp_path: Path) -> None:
    """Harness executes variadic op with arbitrary dynamic kwargs passed via inputs.json."""
    module_code = '''"""Variadic op fixture."""
from __future__ import annotations
from typing import TypedDict
from plynx_sdk import Op

class VariadicConcatOp(Op):
    TITLE = "Variadic Concat"
    ALLOW_EXTRA_INPUTS = True

    class Outputs(TypedDict):
        result: str

    def run(self, sep: str = " ", **parts: str) -> Outputs:
        sorted_vals = [v for _, v in sorted(parts.items())]
        return {"result": sep.join(sorted_vals)}
'''
    module_file = tmp_path / "fixture_variadic.py"
    module_file.write_text(module_code, encoding="utf-8")

    inputs_manifest = InputsManifest(
        inputs={
            "sep": ScalarValue(value=" | "),
            "part_c": ScalarValue(value="gamma"),
            "part_a": ScalarValue(value="alpha"),
            "part_b": ScalarValue(value="beta"),
        }
    )
    (tmp_path / "inputs.json").write_text(inputs_manifest.to_json(), encoding="utf-8")

    env = {
        **os.environ,
        "PYTHONPATH": f"{SDK_SRC}:{tmp_path}",
    }

    cmd = [
        sys.executable,
        "-m",
        "plynx_sdk.harness",
        "--op",
        "fixture_variadic:VariadicConcatOp",
        "--dir",
        str(tmp_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Harness failed:\nstdout: {proc.stdout}\nstderr: {proc.stderr}"

    outputs_file = tmp_path / "outputs.json"
    assert outputs_file.exists()
    out_manifest = OutputsManifest.from_json(outputs_file.read_text(encoding="utf-8"))
    out_val = out_manifest.outputs["result"]
    assert isinstance(out_val, ScalarValue)
    assert out_val.value == "alpha | beta | gamma"


def test_variadic_cache_key_determinism(tmp_path: Path) -> None:
    """Cache key computation handles dynamic extra inputs deterministically."""
    op_source = tmp_path / "op.py"
    op_source.write_text("class Op: pass", encoding="utf-8")

    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text("lock", encoding="utf-8")

    inputs_1 = InputsManifest(
        inputs={
            "sep": ScalarValue(value=","),
            "track_1": ScalarValue(value="v1"),
            "track_2": ScalarValue(value="v2"),
        }
    )
    inputs_2 = InputsManifest(
        inputs={
            "track_2": ScalarValue(value="v2"),
            "sep": ScalarValue(value=","),
            "track_1": ScalarValue(value="v1"),
        }
    )

    key_1 = compute_cache_key(
        op_entrypoint="pack/mod:VariadicOp",
        op_source_file=op_source,
        inputs=inputs_1,
        pack_dir=tmp_path,
    )
    key_2 = compute_cache_key(
        op_entrypoint="pack/mod:VariadicOp",
        op_source_file=op_source,
        inputs=inputs_2,
        pack_dir=tmp_path,
    )
    assert key_1 == key_2

    # Changing an extra input alters cache key
    inputs_diff = InputsManifest(
        inputs={
            "sep": ScalarValue(value=","),
            "track_1": ScalarValue(value="v1_modified"),
            "track_2": ScalarValue(value="v2"),
        }
    )
    key_diff = compute_cache_key(
        op_entrypoint="pack/mod:VariadicOp",
        op_source_file=op_source,
        inputs=inputs_diff,
        pack_dir=tmp_path,
    )
    assert key_1 != key_diff
