"""Demo operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

from typing import TypedDict

from plynx_sdk import Op


class AskFooOrWoo(Op):
    """Ask the user to pick foo or woo."""

    TITLE = "Ask foo or woo"
    CATEGORY = "Demo"
    CACHEABLE = False

    class Outputs(TypedDict):
        choice: str

    def run(self, prompt: str = "foo or woo?") -> Outputs:
        choice = self.checkpoint(
            prompt,
            options=["foo", "woo"],
            allow_freeform=False,
        )
        return {"choice": choice}


class Echo(Op):
    """Echo an input string to its output."""

    TITLE = "Echo text"
    CATEGORY = "Demo"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, text: str) -> Outputs:
        return {"text": text}
