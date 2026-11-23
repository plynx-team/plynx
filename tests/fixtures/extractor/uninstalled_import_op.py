"""Fixture op that imports uninstalled packages to prove static AST extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, TypedDict

import totally_nonexistent_uninstalled_package_xyz999  # type: ignore
from fake_mystery_library import UnknownSymbol  # type: ignore
from plynx_sdk import Directory, Media, Op, Range, TextFile


class UninstalledImportOp(Op):
    """Process data with uninstalled dependencies.

    This multi-line markdown docstring is fully preserved in description.
    """

    TITLE = "Uninstalled Import Op"
    CATEGORY = "Test / Fixtures"
    CACHEABLE = False

    class Outputs(TypedDict):
        text_out: str
        custom_file: Annotated[Path, Media("application/x-custom")]
        plain_file: TextFile

    def run(
        self,
        query: str,
        metadata: dict,
        tags: list,
        limit: int = 50,
        factor: float = 1.5,
        active: bool = True,
        mode: Literal["fast", "accurate"] = "fast",
        threshold: Annotated[int, Range(0, 100, step=5)] = 25,
        rate: Annotated[float, Range(0.0, 1.0)] = 0.5,
        input_file: Path = "data.txt",
        folder: Directory = "dir_in",
        opt_choice: str | None = None,
    ) -> Outputs:
        # Runtime calls that would fail if executed:
        totally_nonexistent_uninstalled_package_xyz999.call(UnknownSymbol)
        return {
            "text_out": query,
            "custom_file": Path(input_file),
            "plain_file": Path("out.txt"),
        }
