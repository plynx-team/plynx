"""Invalid op fixture inheriting from a custom base class (Task 2.3)."""

from __future__ import annotations


class CustomBase:
    """A custom base class outside the supported Op hierarchy."""


class CustomBaseOp(CustomBase):
    """Op subclassing CustomBase instead of plynx_sdk.Op."""

    TITLE = "Custom Base Op"

    def run(self, text: str) -> str:
        return text
