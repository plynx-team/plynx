"""Tests for static AST extraction of PLynx class-form operations (Task 2.1)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from plynx.api_models import InputPortSpec, OutputPortSpec
from plynx.registry import default_fake_ops, extract_ops_from_file, extract_ops_from_source

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "extractor"
UNINSTALLED_FIXTURE = FIXTURES_DIR / "uninstalled_import_op.py"


def test_uninstalled_fixture_fails_to_import_in_runtime() -> None:
    """The test fixture genuinely fails to import due to nonexistent dependencies."""
    with pytest.raises(ModuleNotFoundError) as exc_info:
        runpy.run_path(str(UNINSTALLED_FIXTURE))
    assert "totally_nonexistent_uninstalled_package_xyz999" in str(exc_info.value)


def test_extract_from_uninstalled_fixture_without_importing() -> None:
    """AST extraction succeeds without importing uninstalled packages (Task 2.1 Accept)."""
    ops = extract_ops_from_file(
        UNINSTALLED_FIXTURE,
        pack="test_pack",
        module="uninstalled_import_op",
    )
    assert len(ops) == 1
    op = ops[0]

    assert op.id == "test_pack/uninstalled_import_op:UninstalledImportOp"
    assert op.pack == "test_pack"
    assert op.module == "uninstalled_import_op"
    assert op.name == "UninstalledImportOp"
    assert op.kind == "class"
    assert op.title == "Uninstalled Import Op"
    assert op.category == "Test / Fixtures"
    assert op.cacheable is False
    assert op.description == "Process data with uninstalled dependencies."
    assert op.valid is True
    assert op.error is None

    # Outputs
    assert op.outputs == [
        OutputPortSpec(name="text_out", type="str", media=None),
        OutputPortSpec(name="custom_file", type="file", media="application/x-custom"),
        OutputPortSpec(name="plain_file", type="file", media="text/plain"),
    ]

    # Inputs
    inputs_by_name = {inp.name: inp for inp in op.inputs}
    assert set(inputs_by_name.keys()) == {
        "query",
        "metadata",
        "tags",
        "limit",
        "factor",
        "active",
        "mode",
        "threshold",
        "rate",
        "input_file",
        "folder",
        "opt_choice",
    }

    # Positional required
    assert inputs_by_name["query"] == InputPortSpec(
        name="query",
        type="str",
        required=True,
        default=None,
    )
    assert inputs_by_name["metadata"] == InputPortSpec(
        name="metadata",
        type="json",
        required=True,
        default=None,
    )
    assert inputs_by_name["tags"] == InputPortSpec(
        name="tags",
        type="json",
        required=True,
        default=None,
    )

    # Positional with default
    assert inputs_by_name["limit"] == InputPortSpec(
        name="limit",
        type="int",
        required=False,
        default=50,
    )
    assert inputs_by_name["factor"] == InputPortSpec(
        name="factor",
        type="float",
        required=False,
        default=1.5,
    )
    assert inputs_by_name["active"] == InputPortSpec(
        name="active",
        type="bool",
        required=False,
        default=True,
    )

    # Literal choices
    assert inputs_by_name["mode"] == InputPortSpec(
        name="mode",
        type="str",
        options=["fast", "accurate"],
        required=False,
        default="fast",
    )

    # Range bounded
    assert inputs_by_name["threshold"] == InputPortSpec(
        name="threshold",
        type="int",
        min=0,
        max=100,
        step=5,
        required=False,
        default=25,
    )
    assert inputs_by_name["rate"] == InputPortSpec(
        name="rate",
        type="float",
        min=0.0,
        max=1.0,
        step=None,
        required=False,
        default=0.5,
    )

    # File and Directory
    assert inputs_by_name["input_file"] == InputPortSpec(
        name="input_file",
        type="file",
        required=False,
        default="data.txt",
    )
    assert inputs_by_name["folder"] == InputPortSpec(
        name="folder",
        type="directory",
        required=False,
        default="dir_in",
    )

    # Optional
    assert inputs_by_name["opt_choice"] == InputPortSpec(
        name="opt_choice",
        type="str",
        required=False,
        default=None,
    )


def test_extract_standard_io_text_concat_matches_default_fake_ops() -> None:
    """Extraction of standard_io/text.py matches the Concat entry in FakeRegistry."""
    text_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "text.py"
    extracted = extract_ops_from_file(text_py)
    assert len(extracted) == 1

    expected = next(op for op in default_fake_ops() if op.id == "standard_io/text:Concat")
    assert extracted[0] == expected


def test_extract_standard_io_demo_matches_default_fake_ops() -> None:
    """Extraction of standard_io/demo.py matches all 5 demo ops in FakeRegistry."""
    demo_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "demo.py"
    extracted = extract_ops_from_file(demo_py)
    assert len(extracted) == 5

    fake_ops = {op.id: op for op in default_fake_ops() if op.module == "demo"}
    assert len(fake_ops) == 5

    for op in extracted:
        assert op.id in fake_ops
        assert op == fake_ops[op.id]


def test_extract_single_return_named_result() -> None:
    """A single return type annotation that is not a TypedDict yields an output named 'result'."""
    src = '''
from plynx_sdk import Op, TextFile

class Double(Op):
    """Double an integer."""
    TITLE = "Double int"

    def run(self, val: int) -> int:
        return val * 2

class MakeFile(Op):
    """Create a text file."""
    TITLE = "Make file"

    def run(self, content: str) -> TextFile:
        return content
'''
    ops = extract_ops_from_source(src, pack="math_pack", module="ops")
    assert len(ops) == 2

    assert ops[0].outputs == [OutputPortSpec(name="result", type="int")]
    assert ops[0].category == "Uncategorized"
    assert ops[0].cacheable is True
    assert ops[0].description == "Double an integer."

    assert ops[1].outputs == [OutputPortSpec(name="result", type="file", media="text/plain")]


def test_extract_kwonly_arguments_and_negative_defaults() -> None:
    """Extraction handles keyword-only arguments and negative literal values."""
    src = '''
from plynx_sdk import Op

class ComplexSig(Op):
    """Op with kwonly arguments and negative literals."""
    TITLE = "Complex Sig"
    CATEGORY = "Advanced"
    CACHEABLE = True

    def run(self, a: int = -10, *, flag: bool = False, scale: float = -0.5) -> int:
        return a
'''
    ops = extract_ops_from_source(src, pack="p", module="m")
    assert len(ops) == 1
    op = ops[0]
    assert len(op.inputs) == 3
    assert op.inputs[0] == InputPortSpec(name="a", type="int", required=False, default=-10)
    assert op.inputs[1] == InputPortSpec(name="flag", type="bool", required=False, default=False)
    assert op.inputs[2] == InputPortSpec(name="scale", type="float", required=False, default=-0.5)
