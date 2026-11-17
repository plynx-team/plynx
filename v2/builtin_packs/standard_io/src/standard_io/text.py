"""Text operations in the built-in ``standard_io`` pack (PROTOCOL.md section 3)."""

from __future__ import annotations

from typing import TypedDict

from plynx_sdk import Op


class Concat(Op):
    """Join two strings."""

    TITLE = "Concat text"
    CATEGORY = "Text / Basic"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, a: str, b: str = " ") -> Outputs:
        return {"text": a + b}


__all__ = ["Concat"]
