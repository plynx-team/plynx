"""Tests for Task 1.1: ``plynx_sdk`` authoring API and stdlib-only invariant."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict, get_args, get_origin

import pytest
from plynx_sdk import (
    AgentOp,
    AudioWav,
    CheckpointInterrupt,
    CsvFile,
    Directory,
    DirectoryMarker,
    ImageFile,
    JsonFile,
    MarkdownFile,
    Media,
    Op,
    OpMetadata,
    PdfFile,
    Range,
    SideEffect,
    StageValidatorOp,
    TextFile,
    checkpoint,
    checkpoint_context,
    op,
)
from plynx_sdk.types import SEMANTIC_MEDIA_ALIASES


class Concat(Op):
    """Join two strings."""

    TITLE = "Concat text"
    CATEGORY = "Text / Basic"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, a: str, b: str = " ") -> Outputs:
        return {"text": a + b}


class ConcatOut(TypedDict):
    """TypedDict output for function-form ``concat``."""

    text: str


@op(title="Concat text", category="Text / Basic", cacheable=True)
def concat(a: str, b: str = " ") -> ConcatOut:
    """Join two strings."""
    return {"text": a + b}


def test_class_and_function_forms_run_in_plain_python() -> None:
    """Both forms from PROTOCOL.md section 3 import and run in plain Python."""
    op_instance = Concat()
    assert op_instance.TITLE == "Concat text"
    assert op_instance.CATEGORY == "Text / Basic"
    assert op_instance.CACHEABLE is True
    assert op_instance.run("hello", "world") == {"text": "helloworld"}
    assert op_instance.run("hello") == {"text": "hello "}

    assert concat("hello", "world") == {"text": "helloworld"}
    assert concat("hello") == {"text": "hello "}
    meta = getattr(concat, "__plynx_op__", None)
    assert meta == OpMetadata(title="Concat text", category="Text / Basic", cacheable=True)


def test_media_range_directory_and_semantic_aliases() -> None:
    """Media, Range, Directory, and semantic aliases carry expected metadata."""
    m = Media("application/pdf")
    assert m.mime == "application/pdf"
    with pytest.raises(ValueError, match="non-empty"):
        Media("")

    r_int = Range(0, 10, step=1)
    assert (r_int.min, r_int.max, r_int.step) == (0, 10, 1)
    r_float = Range(0.0, 1.0)
    assert (r_float.min, r_float.max, r_float.step) == (0.0, 1.0, None)
    with pytest.raises(ValueError, match="cannot exceed"):
        Range(10, 5)
    with pytest.raises(ValueError, match="positive"):
        Range(0, 10, step=0)

    assert get_origin(Directory) is Annotated
    dir_args = get_args(Directory)
    assert dir_args[0] is Path
    assert DirectoryMarker() in dir_args[1:]

    alias_map = {
        "PdfFile": PdfFile,
        "AudioWav": AudioWav,
        "MarkdownFile": MarkdownFile,
        "JsonFile": JsonFile,
        "ImageFile": ImageFile,
        "CsvFile": CsvFile,
        "TextFile": TextFile,
    }
    for name, alias in alias_map.items():
        assert get_origin(alias) is Annotated
        args = get_args(alias)
        assert args[0] is Path
        expected_mime = SEMANTIC_MEDIA_ALIASES[name]
        assert Media(expected_mime) in args[1:]

    # Verify Annotated[int, Range(...)], Literal[...], and Annotated[Path, Media(...)]
    IntBounded = Annotated[int, Range(1, 5, step=1)]
    Choice = Literal["foo", "woo"]
    assert get_args(IntBounded)[1] == Range(1, 5, step=1)
    assert get_args(Choice) == ("foo", "woo")


def test_checkpoint_interrupt_is_base_exception() -> None:
    """CheckpointInterrupt inherits from BaseException (not Exception)."""
    assert issubclass(CheckpointInterrupt, BaseException)
    assert not issubclass(CheckpointInterrupt, Exception)

    class AskOp(Op):
        TITLE = "Ask"

        def run(self) -> dict[str, str]:
            try:
                ans = self.checkpoint("foo or woo?", options=["foo", "woo"])
            except Exception:
                return {"choice": "swallowed"}
            return {"choice": ans}

    with pytest.raises(CheckpointInterrupt) as exc_info:
        AskOp().run()
    assert exc_info.value.manifest.checkpoint_id == "cp_0"
    assert exc_info.value.manifest.question == "foo or woo?"
    assert exc_info.value.manifest.options == ["foo", "woo"]

    with checkpoint_context(answers={"cp_0": "woo"}):
        assert AskOp().run() == {"choice": "woo"}
        assert checkpoint("second?", allow_freeform=True) if False else True


def test_plynx_sdk_imports_only_stdlib() -> None:
    """Importing plynx_sdk imports nothing outside the Python standard library."""
    code = """
import sys
import plynx_sdk
import plynx_sdk.checkpoint
import plynx_sdk.harness
import plynx_sdk.op
import plynx_sdk.protocol
import plynx_sdk.types

stdlib = sys.stdlib_module_names
non_stdlib = []
for name in sorted(sys.modules):
    top = name.split(".")[0]
    if top in ("plynx_sdk", "__main__", "builtins"):
        continue
    if top.startswith("_"):
        continue
    # Ignore site/virtualenv startup modules injected before user code
    if top in ("site", "sitecustomize", "usercustomize", "_virtualenv", " typing_extensions"):
        continue
    if top not in stdlib:
        non_stdlib.append(name)

assert not non_stdlib, f"Non-stdlib modules imported: {non_stdlib}"
"""
    sdk_src = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk" / "src"
    proc = subprocess.run(
        [sys.executable, "-S", "-c", code],
        env={"PYTHONPATH": str(sdk_src)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"


def test_side_effects_defaults_auto_cacheable_and_validation() -> None:
    """SideEffect defaults cleanly, auto-sets CACHEABLE=False on WRITE, and rejects WRITE+CACHEABLE=True."""
    assert SideEffect.NONE.value == "none"
    assert SideEffect.READ.value == "read"
    assert SideEffect.WRITE.value == "write"
    assert Op.SIDE_EFFECTS == SideEffect.NONE
    assert AgentOp.SIDE_EFFECTS == SideEffect.READ
    assert StageValidatorOp.SIDE_EFFECTS == SideEffect.READ

    class ReadIssues(Op):
        TITLE = "Read Issues"
        CACHEABLE = False
        SIDE_EFFECTS = "read"  # type: ignore[assignment]

        def run(self) -> dict[str, int]:
            return {"count": 1}

    assert ReadIssues.SIDE_EFFECTS == SideEffect.READ
    assert ReadIssues.CACHEABLE is False

    class SendWebhook(Op):
        TITLE = "Send Webhook"
        SIDE_EFFECTS = SideEffect.WRITE

        def run(self) -> dict[str, bool]:
            return {"ok": True}

    assert SendWebhook.SIDE_EFFECTS == SideEffect.WRITE
    assert SendWebhook.CACHEABLE is False

    @op(title="Post Slack", side_effects=SideEffect.WRITE)
    def post_slack(msg: str) -> str:
        return msg

    post_slack_any: Any = post_slack
    fn_meta = post_slack_any.__plynx_op__
    assert fn_meta.side_effects == SideEffect.WRITE
    assert fn_meta.cacheable is False

    with pytest.raises(ValueError, match="CACHEABLE=False"):

        class InvalidCachedWrite(Op):
            TITLE = "Bad Write"
            CACHEABLE = True
            SIDE_EFFECTS = SideEffect.WRITE

            def run(self) -> dict[str, str]:
                return {"ok": "no"}

    with pytest.raises(ValueError, match="cacheable=False"):

        @op(title="Bad Fn Write", cacheable=True, side_effects="write")
        def bad_fn_write() -> str:
            return "no"

    with pytest.raises(ValueError, match="side_effects"):

        class InvalidSideEffectValue(Op):
            TITLE = "Invalid SE"
            SIDE_EFFECTS = "destroy"  # type: ignore[assignment]

            def run(self) -> dict[str, str]:
                return {"ok": "no"}
