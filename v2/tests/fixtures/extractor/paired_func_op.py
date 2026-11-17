"""Function-form fixture for testing equality against class-form op (Task 2.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import Directory, Media, PdfFile, Range, TextFile, op

# Same-file aliases:
CustomData = Annotated[Path, Media("application/x-custom-data")]
SpeedMode = Literal["slow", "medium", "fast"]
QualityLevel = Annotated[int, Range(1, 10, step=1)]
Ratio = Annotated[float, Range(0.0, 1.0)]


class PairedOutputs(TypedDict):
    """Outputs specification."""

    summary: str
    report_pdf: PdfFile
    output_log: TextFile
    artifact: CustomData


@op(
    title="Comprehensive Paired Op",
    category="Testing / Paired",
    cacheable=True,
)
def ComprehensiveOp(
    name: str,
    speed: SpeedMode = "medium",
    quality: QualityLevel = 5,
    ratio: Ratio = 0.5,
    input_pdf: PdfFile = "doc.pdf",
    custom_input: CustomData = "data.bin",
    work_dir: Directory = "work",
    extra_note: str | None = None,
    max_retries: Annotated[int, Range(0, 5)] = 3,
    tag: Literal["v1", "v2"] = "v2",
) -> PairedOutputs:
    """Process diverse data with rich annotations and aliases.

    Second line of docstring that should be ignored for description.
    """
    return {
        "summary": name,
        "report_pdf": Path("doc.pdf"),
        "output_log": Path("log.txt"),
        "artifact": Path("data.bin"),
    }
