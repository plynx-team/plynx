"""Tests for static AST extraction of operations (Tasks 2.1, 2.2 & 2.3)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from plynx.api_models import InputPortSpec, OutputPortSpec
from plynx.registry import extract_ops_from_file, extract_ops_from_source

from tests.fakes import default_fake_ops

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "extractor"
UNINSTALLED_FIXTURE = FIXTURES_DIR / "uninstalled_import_op.py"
PAIRED_CLASS_FIXTURE = FIXTURES_DIR / "paired_class_op.py"
PAIRED_FUNC_FIXTURE = FIXTURES_DIR / "paired_func_op.py"
INVALID_COMPUTED_TITLE_FIXTURE = FIXTURES_DIR / "invalid_computed_title.py"
INVALID_CUSTOM_BASE_FIXTURE = FIXTURES_DIR / "invalid_custom_base.py"
INVALID_UNKNOWN_ANNOTATION_FIXTURE = FIXTURES_DIR / "invalid_unknown_annotation.py"


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
    assert op.description == (
        "Process data with uninstalled dependencies.\n\n"
        "This multi-line markdown docstring is fully preserved in description."
    )
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
    """Extraction of standard_io/demo.py matches all 3 demo ops in FakeRegistry."""
    demo_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "demo.py"
    extracted = extract_ops_from_file(demo_py)
    assert len(extracted) == 3

    fake_ops = {op.id: op for op in default_fake_ops() if op.module == "demo"}
    assert len(fake_ops) == 3

    for op in extracted:
        assert op.id in fake_ops
        assert op == fake_ops[op.id]


def test_extract_standard_io_data_matches_default_fake_ops() -> None:
    """Extraction of standard_io/data.py matches all 5 data ops in FakeRegistry."""
    data_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "data.py"
    extracted = extract_ops_from_file(data_py)
    assert len(extracted) == 5

    fake_ops = {op.id: op for op in default_fake_ops() if op.module == "data"}
    assert len(fake_ops) == 5

    for op in extracted:
        assert op.id in fake_ops
        assert op == fake_ops[op.id]


def test_extract_standard_io_files_matches_default_fake_ops() -> None:
    """Extraction of standard_io/files.py matches all 3 file ops in FakeRegistry."""
    files_py = ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "files.py"
    extracted = extract_ops_from_file(files_py)
    assert len(extracted) == 3

    fake_ops = {op.id: op for op in default_fake_ops() if op.module == "files"}
    assert len(fake_ops) == 3

    for op in extracted:
        assert op.id in fake_ops
        assert op == fake_ops[op.id]


def test_extract_standard_io_interactive_matches_default_fake_ops() -> None:
    """Extraction of standard_io/interactive.py matches the AskChoice op in FakeRegistry."""
    interactive_py = (
        ROOT / "builtin_packs" / "standard_io" / "src" / "standard_io" / "interactive.py"
    )
    extracted = extract_ops_from_file(interactive_py)
    assert len(extracted) == 1

    fake_ops = {op.id: op for op in default_fake_ops() if op.module == "interactive"}
    assert len(fake_ops) == 1

    for op in extracted:
        assert op.id in fake_ops
        assert op == fake_ops[op.id]


def test_extract_toy_ops() -> None:
    """Extraction of tests/fixtures/toy_ops.py extracts AskFooOrWoo, SecretCodeChallenge, MultiStepQuestionnaire."""
    toy_py = ROOT / "tests" / "fixtures" / "toy_ops.py"
    extracted = extract_ops_from_file(toy_py)
    assert len(extracted) == 3
    names = {op.name for op in extracted}
    assert names == {"AskFooOrWoo", "SecretCodeChallenge", "MultiStepQuestionnaire"}


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


def test_class_and_function_fixtures_produce_equal_registry_entries() -> None:
    """Class and function fixtures for the same op produce equal registry entries."""
    class_ops = extract_ops_from_file(
        PAIRED_CLASS_FIXTURE,
        pack="demo_pack",
        module="paired_op",
    )
    func_ops = extract_ops_from_file(
        PAIRED_FUNC_FIXTURE,
        pack="demo_pack",
        module="paired_op",
    )

    assert len(class_ops) == 1
    assert len(func_ops) == 1

    class_op = class_ops[0]
    func_op = func_ops[0]

    # Verify kinds match their respective forms
    assert class_op.kind == "class"
    assert func_op.kind == "function"

    # Verify all functional fields are identical
    assert class_op.id == func_op.id
    assert class_op.name == func_op.name
    assert class_op.pack == func_op.pack
    assert class_op.module == func_op.module
    assert class_op.title == func_op.title == "Comprehensive Paired Op"
    assert class_op.category == func_op.category == "Testing / Paired"
    assert class_op.cacheable == func_op.cacheable is True
    assert (
        class_op.description
        == func_op.description
        == (
            "Process diverse data with rich annotations and aliases.\n\n"
            "Second line of docstring that is preserved in full description."
        )
    )
    assert class_op.valid == func_op.valid is True
    assert class_op.error == func_op.error is None
    assert class_op.inputs == func_op.inputs
    assert class_op.outputs == func_op.outputs

    # Excluding 'kind' and 'source' file path, full serialized schemas match exactly
    assert class_op.model_dump(exclude={"kind", "source"}) == func_op.model_dump(
        exclude={"kind", "source"}
    )


def test_function_op_positional_decorator_arguments() -> None:
    """The @op decorator supports positional arguments (title, category, cacheable)."""
    src = '''
from plynx_sdk import op

@op("Custom Title", "Custom Cat", False)
def my_func(x: str) -> str:
    """A custom function op."""
    return x
'''
    ops = extract_ops_from_source(src, pack="p", module="m")
    assert len(ops) == 1
    op = ops[0]
    assert op.title == "Custom Title"
    assert op.category == "Custom Cat"
    assert op.cacheable is False
    assert op.description == "A custom function op."
    assert op.kind == "function"
    assert op.outputs == [OutputPortSpec(name="result", type="str")]


# ---------------------------------------------------------------------------
# Task 2.3: Invalid ops (yield valid: False with documented reasons, never crash)
# ---------------------------------------------------------------------------


def test_invalid_computed_title_fixture() -> None:
    """Fixture for computed TITLE yields valid: False and documented reason (Task 2.3 Accept)."""
    ops = extract_ops_from_file(INVALID_COMPUTED_TITLE_FIXTURE)
    assert len(ops) == 1
    op = ops[0]

    assert op.valid is False
    assert op.error is not None
    assert "Computed metadata is not supported" in op.error
    assert "TITLE must be a string literal" in op.error


def test_invalid_custom_base_fixture() -> None:
    """Fixture for custom base class yields valid: False and documented reason (Task 2.3 Accept)."""
    ops = extract_ops_from_file(INVALID_CUSTOM_BASE_FIXTURE)
    assert len(ops) == 1
    op = ops[0]

    assert op.valid is False
    assert op.error is not None
    assert "custom base class is not supported" in op.error.lower()
    assert "must inherit directly from Op" in op.error


def test_invalid_unknown_annotation_fixture() -> None:
    """Fixture for unknown annotation yields valid: False and documented reason."""
    ops = extract_ops_from_file(INVALID_UNKNOWN_ANNOTATION_FIXTURE)
    assert len(ops) == 1
    op = ops[0]

    assert op.valid is False
    assert op.error is not None
    assert "Unknown or unsupported port annotation" in op.error
    assert "UnknownPortType" in op.error


def test_invalid_syntax_error_yields_valid_false_never_crashes() -> None:
    """Files with Python syntax errors produce valid: False and never crash."""
    ops = extract_ops_from_source(
        "class BrokenSyntax(:\n    def broken(\n",
        pack="bad_pack",
        module="bad_mod",
        source_path="bad_pack/bad_mod.py",
    )
    assert len(ops) == 1
    op = ops[0]
    assert op.valid is False
    assert op.error is not None
    assert "syntax error" in op.error.lower()


def test_invalid_missing_title_and_missing_run() -> None:
    """Class ops missing TITLE or run method yield valid: False with clear reasons."""
    src_no_title = """
from plynx_sdk import Op

class NoTitle(Op):
    def run(self, x: str) -> str:
        return x
"""
    ops1 = extract_ops_from_source(src_no_title)
    assert len(ops1) == 1
    assert ops1[0].valid is False
    assert ops1[0].error is not None
    assert "missing required TITLE" in ops1[0].error

    src_no_run = """
from plynx_sdk import Op

class NoRun(Op):
    TITLE = "No Run"
"""
    ops2 = extract_ops_from_source(src_no_run)
    assert len(ops2) == 1
    assert ops2[0].valid is False
    assert ops2[0].error is not None
    assert "must define a 'run' method" in ops2[0].error


def test_invalid_port_name_and_varargs() -> None:
    """Invalid port names (not snake_case) and varargs/kwargs yield valid: False."""
    src_bad_port = """
from plynx_sdk import Op

class BadPort(Op):
    TITLE = "Bad Port"
    def run(self, NotSnakeCase: str) -> str:
        return NotSnakeCase
"""
    ops1 = extract_ops_from_source(src_bad_port)
    assert len(ops1) == 1
    assert ops1[0].valid is False
    assert ops1[0].error is not None
    assert "must be snake_case" in ops1[0].error

    src_varargs = """
from plynx_sdk import Op

class VarArgs(Op):
    TITLE = "Var Args"
    def run(self, *args: str, **kwargs: str) -> str:
        return ""
"""
    ops2 = extract_ops_from_source(src_varargs)
    assert len(ops2) == 1
    assert ops2[0].valid is False
    assert ops2[0].error is not None
    assert "*args and **kwargs are not supported" in ops2[0].error


def test_invalid_function_op_computed_title_and_unknown_annotation() -> None:
    """Function ops with computed @op metadata or unknown annotations yield valid: False."""
    src_computed = """
from plynx_sdk import op

@op(title="Prefix " + "Suffix")
def computed_fn(x: str) -> str:
    return x
"""
    ops1 = extract_ops_from_source(src_computed)
    assert len(ops1) == 1
    assert ops1[0].valid is False
    assert ops1[0].error is not None
    assert "Computed metadata is not supported" in ops1[0].error

    src_unknown = """
from plynx_sdk import op

@op(title="Unknown Ann Fn")
def unknown_fn(x: CompletelyUnknownType) -> str:
    return "ok"
"""
    ops2 = extract_ops_from_source(src_unknown)
    assert len(ops2) == 1
    assert ops2[0].valid is False
    assert ops2[0].error is not None
    assert "Unknown or unsupported port annotation" in ops2[0].error


def test_multiline_markdown_docstring_preserved() -> None:
    """Multi-paragraph Markdown docstrings are fully preserved in OpEntry.description."""
    src = '''
from plynx_sdk import Op

class MarkdownDocOp(Op):
    """# Markdown Header

    This is an extended paragraph explaining the op.
    It includes code examples:

    ```python
    x = 1 + 2
    ```

    - Bullet 1
    - Bullet 2
    """
    TITLE = "Markdown Doc Op"

    def run(self, val: str) -> str:
        return val
'''
    ops = extract_ops_from_source(src, pack="test", module="md")
    assert len(ops) == 1
    op = ops[0]
    assert op.title == "Markdown Doc Op"
    assert "# Markdown Header" in op.description
    assert "```python\nx = 1 + 2\n```" in op.description
    assert "- Bullet 1\n- Bullet 2" in op.description


def test_google_style_args_extracted_to_input_port_descriptions() -> None:
    """Google-style 'Args:' section in run() docstring populates InputPortSpec.description."""
    src = '''
from plynx_sdk import Op

class DocArgsOp(Op):
    """Op with Google-style argument documentation."""
    TITLE = "Doc Args Op"

    def run(
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        debug_mode: bool = False,
    ) -> str:
        """Execute model inference.

        Args:
            prompt: Input text prompt to supply to the LLM model.
            max_tokens (int): Maximum number of tokens to generate
                across multiple continuation lines.
            temperature (float, optional): Sampling temperature between 0.0 and 1.0.
            debug_mode: Whether verbose debugging traces should be emitted.

        Returns:
            Generated text completion.
        """
        return prompt
'''
    ops = extract_ops_from_source(src, pack="test", module="docs")
    assert len(ops) == 1
    op = ops[0]
    inputs_by_name = {inp.name: inp for inp in op.inputs}

    assert inputs_by_name["prompt"].description == "Input text prompt to supply to the LLM model."
    assert (
        inputs_by_name["max_tokens"].description
        == "Maximum number of tokens to generate across multiple continuation lines."
    )
    assert inputs_by_name["temperature"].description == "Sampling temperature between 0.0 and 1.0."
    assert (
        inputs_by_name["debug_mode"].description
        == "Whether verbose debugging traces should be emitted."
    )


def test_builtin_pack_ops_parameter_descriptions() -> None:
    """Builtin packs with Args: docstrings (AudioMixer, TextToSpeech) have input descriptions."""
    from plynx.registry.pack_registry import PackRegistry

    reg = PackRegistry(ROOT)
    mixer_op = reg.get("pedalboard_studio/effects:AudioMixer")
    assert mixer_op is not None
    mixer_inputs = {inp.name: inp for inp in mixer_op.inputs}
    assert mixer_inputs["track_1"].description is not None
    assert "Primary audio track" in mixer_inputs["track_1"].description
    assert mixer_inputs["track_2"].description is not None
    assert "second audio track" in mixer_inputs["track_2"].description
    ducking_val = mixer_inputs["ducking_amount_db"].description
    assert ducking_val is not None
    assert "db" in ducking_val.lower() or "attenuation" in ducking_val.lower()

    tts_op = reg.get("podcast_studio/voice:TextToSpeech")
    assert tts_op is not None
    assert "macOS only" in tts_op.description
    tts_inputs = {inp.name: inp for inp in tts_op.inputs}
    text_desc = tts_inputs["text"].description
    assert text_desc is not None and "Inline speech text" in text_desc
    rate_desc = tts_inputs["rate"].description
    assert rate_desc is not None and "words per minute" in rate_desc


def test_midi_file_semantic_alias_extraction() -> None:
    """Verify MidiFile extracts as file port with media='audio/midi'."""
    from plynx.registry.pack_registry import PackRegistry

    reg = PackRegistry(ROOT)
    chord_op = reg.get("pedalboard_studio/score:ChordProgressionScore")
    assert chord_op is not None
    midi_out = next(out for out in chord_op.outputs if out.name == "midi")
    assert midi_out.type == "file"
    assert midi_out.media == "audio/midi"

    piano_op = reg.get("pedalboard_studio/synth:AcousticPianoSynth")
    assert piano_op is not None
    midi_in = next(inp for inp in piano_op.inputs if inp.name == "midi")
    assert midi_in.type == "file"
    assert midi_in.media == "audio/midi"


def test_function_op_does_not_hijack_unrelated_outputs_typed_dict() -> None:
    """A function op in a module with an unrelated Outputs TypedDict does not inherit its ports."""
    src = """
from typing import TypedDict
from plynx_sdk import op

class Outputs(TypedDict):
    unrelated_a: str
    unrelated_b: int

@op(title="Compute Text")
def compute_text(val: str) -> str:
    return val
"""
    ops = extract_ops_from_source(src, pack="test_pack", module="math_ops")
    assert len(ops) == 1
    op_entry = ops[0]
    assert op_entry.valid is True
    assert len(op_entry.outputs) == 1
    assert op_entry.outputs[0].name == "result"
    assert op_entry.outputs[0].type == "str"


def test_missing_return_annotation_yields_valid_false_error() -> None:
    """Missing return annotations on function or class ops yield valid: False aligned with harness."""
    func_src = """
from plynx_sdk import op

@op(title="No Return Func")
def missing_func(x: int):
    pass
"""
    ops = extract_ops_from_source(func_src, pack="test_pack", module="fn")
    assert len(ops) == 1
    assert ops[0].valid is False
    assert ops[0].error is not None
    assert "missing a return annotation" in ops[0].error

    class_src = """
from plynx_sdk import Op

class NoReturnOp(Op):
    TITLE = "No Return Class"

    def run(self, x: int):
        pass
"""
    class_ops = extract_ops_from_source(class_src, pack="test_pack", module="cls")
    assert len(class_ops) == 1
    assert class_ops[0].valid is False
    assert class_ops[0].error is not None
    assert "has no Outputs TypedDict or return annotation" in class_ops[0].error


def test_non_op_helper_classes_ignored_without_false_positives() -> None:
    """Helper classes, config classes, and non-Op classes with run() do not generate false-positive ops."""
    src = """
from plynx_sdk import Op

class Helper:
    def format_text(self, s: str) -> str:
        return s.strip()

class Config:
    TITLE = "Some Config Document"

class WorkerThread:
    def run(self):
        pass

class RealOp(Op):
    TITLE = "Real Op"

    def run(self, x: int) -> int:
        return x * 2
"""
    ops = extract_ops_from_source(src, pack="test_pack", module="ops")
    assert len(ops) == 1
    assert ops[0].name == "RealOp"
    assert ops[0].valid is True


def test_init_py_clean_module_and_id(tmp_path: Path) -> None:
    """Ops defined in root __init__.py receive clean IDs (pack:Name) without trailing slashes."""
    src = """
from plynx_sdk import Op

class RootOp(Op):
    TITLE = "Root Operation"

    def run(self) -> str:
        return "root"
"""
    ops = extract_ops_from_source(src, pack="test_pack", module="")
    assert len(ops) == 1
    assert ops[0].id == "test_pack:RootOp"
    assert ops[0].module == ""
    assert ops[0].valid is True

    init_file = tmp_path / "custom_packs" / "mypack" / "src" / "mypack" / "__init__.py"
    init_file.parent.mkdir(parents=True, exist_ok=True)
    init_file.write_text(src, encoding="utf-8")

    from plynx.registry.extractor import _deduce_pack_and_module

    deduced_pack, deduced_module, _ = _deduce_pack_and_module(init_file, workspace_root=tmp_path)
    assert deduced_pack == "mypack"
    assert deduced_module == ""


def test_extract_agent_op_choice_a_choice_b_and_stage_validator_under_1ms() -> None:
    """AST extractor discovers Choice A AgentOp, Choice B AgentOp, and StageValidatorOp in <1ms."""
    import time

    from plynx_sdk.protocol import AGENT_PROVIDER_VALUES

    src = '''
from typing import Any, TypedDict
from plynx_sdk import AgentOp, AgentProvider, MarkdownFile, StageValidatorOp, TextFile


class ChoiceAPrompt(AgentOp):
    """Run a domain prompt without overriding run()."""

    TITLE = "Choice A Prompt"
    CATEGORY = "Agents"

    class Outputs(TypedDict):
        response: MarkdownFile
        score: int


class ChoiceBCvMatcher(AgentOp):
    """Compare CV against a job description."""

    TITLE = "CV Matcher"
    CATEGORY = "Agents / HR"

    class Outputs(TypedDict):
        verdict: str
        report: MarkdownFile

    def run(
        self,
        cv: MarkdownFile,
        job_desc: TextFile,
        prompt_file: MarkdownFile | None = None,
        prompt: str = "",
        provider: AgentProvider = AgentProvider.DEFAULT,
        model: str = "",
        **extra: Any,
    ) -> Outputs:
        return self.run_agent(
            prompt_file=prompt_file,
            prompt=prompt,
            provider=provider,
            model=model,
            cv=cv,
            job_desc=job_desc,
            **extra,
        )


class IngestSupervisor(StageValidatorOp):
    """Inspect stage outputs and propose bounded repairs."""

    TITLE = "Ingest Supervisor"
'''
    # Warm up and measure AST extraction time
    extract_ops_from_source(src, pack="standard_io", module="agent")
    t0 = time.perf_counter()
    ops = extract_ops_from_source(src, pack="standard_io", module="agent")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 5.0  # Typically ~0.15ms (<1ms target, generous 5ms CI runner guard)
    assert len(ops) == 3

    choice_a, choice_b, supervisor = ops

    # Choice A
    assert choice_a.valid is True
    assert choice_a.agent_role == "agent"
    assert choice_a.allow_extra_inputs is True
    assert [p.name for p in choice_a.inputs] == ["prompt_file", "prompt", "provider", "model"]
    a_inputs = {p.name: p for p in choice_a.inputs}
    assert a_inputs["prompt_file"].type == "file"
    assert a_inputs["prompt_file"].media == "text/markdown"
    assert a_inputs["prompt_file"].required is False
    assert a_inputs["provider"].options == list(AGENT_PROVIDER_VALUES)
    assert a_inputs["provider"].default == "default"
    assert a_inputs["model"].type == "str"
    assert a_inputs["model"].default == ""
    assert choice_a.outputs == [
        OutputPortSpec(name="response", type="file", media="text/markdown"),
        OutputPortSpec(name="score", type="int"),
    ]

    # Choice B
    assert choice_b.valid is True
    assert choice_b.agent_role == "agent"
    assert choice_b.allow_extra_inputs is True
    assert [p.name for p in choice_b.inputs] == [
        "cv",
        "job_desc",
        "prompt_file",
        "prompt",
        "provider",
        "model",
    ]
    b_inputs = {p.name: p for p in choice_b.inputs}
    assert b_inputs["cv"].required is True
    assert b_inputs["cv"].media == "text/markdown"
    assert b_inputs["job_desc"].required is True
    assert b_inputs["job_desc"].media == "text/plain"
    assert b_inputs["provider"].options == list(AGENT_PROVIDER_VALUES)
    assert b_inputs["provider"].default == "default"

    # StageValidatorOp
    assert supervisor.valid is True
    assert supervisor.agent_role == "validator"
    assert supervisor.allow_extra_inputs is True
    assert supervisor.category == "Agents / Validators"
    assert [p.name for p in supervisor.inputs] == ["prompt_file", "prompt", "provider", "model"]
    assert supervisor.outputs == [OutputPortSpec(name="summary", type="str")]
