"""Op authoring API: ``Op`` base class and ``@op`` decorator (PROTOCOL.md section 3).

Standard library only.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

from plynx_sdk.checkpoint import checkpoint as _checkpoint

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True)
class OpMetadata:
    """Metadata attached to functions decorated with ``@op(...)``."""

    title: str
    category: str = "Uncategorized"
    cacheable: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("op title must be a non-empty string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("op category must be a non-empty string")
        if not isinstance(self.cacheable, bool):
            raise ValueError("op cacheable must be a bool")


class Op:
    """Base class for class-form PLynx operations."""

    TITLE: ClassVar[str] = ""
    CATEGORY: ClassVar[str] = "Uncategorized"
    CACHEABLE: ClassVar[bool] = True

    def checkpoint(
        self,
        question: str,
        options: Sequence[str] | None = None,
        allow_freeform: bool = False,
    ) -> str:
        """Ask a checkpoint question or return the replayed answer for this attempt."""
        return _checkpoint(question, options=options, allow_freeform=allow_freeform)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the operation. Subclasses must override this method."""
        raise NotImplementedError("Op subclasses must implement run()")


def op(
    title: str,
    category: str = "Uncategorized",
    cacheable: bool = True,
) -> Callable[[F], F]:
    """Decorate a function as a PLynx operation."""
    metadata = OpMetadata(title=title, category=category, cacheable=cacheable)

    def _decorator(func: F) -> F:
        func_any: Any = func
        func_any.__plynx_op__ = metadata
        return func

    return _decorator


__all__ = [
    "Op",
    "OpMetadata",
    "op",
]
