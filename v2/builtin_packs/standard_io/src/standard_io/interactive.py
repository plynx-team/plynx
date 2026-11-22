"""Interactive operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

from typing import TypedDict

from plynx_sdk import Op


class AskChoice(Op):
    """Prompt the user with a question and configurable choices or optional freeform entry.

    Args:
        question: Question or prompt presented to the user at the checkpoint.
        options_csv: Comma-separated list of candidate options to select from.
        allow_freeform: Whether the user is permitted to enter freeform text.
    """

    TITLE = "Ask Choice"
    CATEGORY = "Core / Interactive"
    CACHEABLE = False

    class Outputs(TypedDict):
        choice: str

    def run(
        self,
        question: str = "Please choose an option:",
        options_csv: str = "Option A, Option B, Option C",
        allow_freeform: bool = False,
    ) -> Outputs:
        opts = [opt.strip() for opt in options_csv.split(",") if opt.strip()]
        choice = self.checkpoint(
            question,
            options=opts if opts else None,
            allow_freeform=allow_freeform,
        )
        return {"choice": choice}


__all__ = [
    "AskChoice",
]
