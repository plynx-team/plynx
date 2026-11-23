"""Invalid op fixture with computed TITLE (Task 2.3)."""

from __future__ import annotations

from plynx_sdk import Op


class ComputedTitleOp(Op):
    """Op with a computed TITLE instead of a string literal."""

    TITLE = "Computed " + "Title"

    def run(self, text: str) -> str:
        return text
