"""Invalid op fixture with an unknown port type annotation (Task 2.3)."""

from __future__ import annotations

from plynx_sdk import Op


class UnknownAnnotationOp(Op):
    """Op with an unknown port annotation outside the supported subset."""

    TITLE = "Unknown Annotation Op"

    def run(self, data: UnknownPortType) -> str:  # type: ignore # noqa: F821
        return "result"
