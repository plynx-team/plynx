"""Port annotation markers, ``Directory``, and semantic media aliases (PROTOCOL.md section 3).

Standard library only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final


@dataclass(frozen=True)
class Media:
    """MIME type annotation marker for ``Annotated[Path, Media("<mime>")]``."""

    mime: str

    def __post_init__(self) -> None:
        if not isinstance(self.mime, str) or not self.mime.strip():
            raise ValueError("Media.mime must be a non-empty string")


@dataclass(frozen=True)
class Range:
    """Numeric bounds annotation marker for ``Annotated[int | float, Range(min, max)]``."""

    min: int | float
    max: int | float
    step: int | float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.min, bool) or not isinstance(self.min, (int, float)):
            raise ValueError("Range.min must be a number")
        if isinstance(self.max, bool) or not isinstance(self.max, (int, float)):
            raise ValueError("Range.max must be a number")
        if not (math.isfinite(float(self.min)) and math.isfinite(float(self.max))):
            raise ValueError("Range bounds must be finite numbers")
        if self.min > self.max:
            raise ValueError(f"Range.min ({self.min}) cannot exceed Range.max ({self.max})")
        if self.step is not None:
            if isinstance(self.step, bool) or not isinstance(self.step, (int, float)):
                raise ValueError("Range.step must be a number")
            if not math.isfinite(float(self.step)) or self.step <= 0:
                raise ValueError("Range.step must be a positive finite number")


@dataclass(frozen=True)
class DirectoryMarker:
    """Internal annotation marker distinguishing ``Directory`` from ``Path`` at runtime."""


Directory = Annotated[Path, DirectoryMarker()]

PdfFile = Annotated[Path, Media("application/pdf")]
AudioWav = Annotated[Path, Media("audio/wav")]
MidiFile = Annotated[Path, Media("audio/midi")]
MarkdownFile = Annotated[Path, Media("text/markdown")]
JsonFile = Annotated[Path, Media("application/json")]
ImageFile = Annotated[Path, Media("image/png")]
CsvFile = Annotated[Path, Media("text/csv")]
TextFile = Annotated[Path, Media("text/plain")]

SEMANTIC_MEDIA_ALIASES: Final[dict[str, str]] = {
    "PdfFile": "application/pdf",
    "AudioWav": "audio/wav",
    "MidiFile": "audio/midi",
    "MarkdownFile": "text/markdown",
    "JsonFile": "application/json",
    "ImageFile": "image/png",
    "CsvFile": "text/csv",
    "TextFile": "text/plain",
}

__all__ = [
    "SEMANTIC_MEDIA_ALIASES",
    "AudioWav",
    "CsvFile",
    "Directory",
    "DirectoryMarker",
    "ImageFile",
    "JsonFile",
    "MarkdownFile",
    "Media",
    "MidiFile",
    "PdfFile",
    "Range",
    "TextFile",
]
