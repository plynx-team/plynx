"""Demo operations in the built-in ``standard_io`` pack (PROTOCOL.md sections 2 & 3)."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from plynx_sdk import Op, TextFile


class Echo(Op):
    """Echo an input string to its output."""

    TITLE = "Echo text"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, text: str) -> Outputs:
        return {"text": text}


class ReadText(Op):
    """Read UTF-8 text from a file."""

    TITLE = "Read text file"
    CATEGORY = "Core / Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, path: Path) -> Outputs:
        return {"text": path.read_text(encoding="utf-8")}


class WriteText(Op):
    """Write UTF-8 text to a file."""

    TITLE = "Write text file"
    CATEGORY = "Core / Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        file: TextFile

    def run(self, text: str, filename: str = "out.txt") -> Outputs:
        out_path = Path(filename)
        if out_path.is_absolute() or ".." in out_path.parts or len(out_path.parts) != 1:
            raise ValueError(f"filename must be a single relative file name, got {filename!r}")
        out_path.write_text(text, encoding="utf-8")
        return {"file": out_path}


__all__ = [
    "Echo",
    "ReadText",
    "WriteText",
]
