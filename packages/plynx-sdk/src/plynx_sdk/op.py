"""Op authoring API: ``Op`` base class and ``@op`` decorator (PROTOCOL.md section 3).

Standard library only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

from plynx_sdk.anomaly import warn as _warn
from plynx_sdk.checkpoint import checkpoint as _checkpoint
from plynx_sdk.checkpoint import checkpoint_batch as _checkpoint_batch
from plynx_sdk.protocol import AnswerValue, CheckpointQuestion, SideEffect

F = TypeVar("F", bound=Callable[..., Any])


def _coerce_side_effects(value: object, *, owner: str) -> SideEffect:
    if isinstance(value, SideEffect):
        return value
    if isinstance(value, str) and not isinstance(value, bool):
        try:
            return SideEffect(value)
        except ValueError as exc:
            allowed = ", ".join(repr(m.value) for m in SideEffect)
            raise ValueError(
                f"{owner} side_effects must be one of {allowed}, got {value!r}"
            ) from exc
    raise ValueError(
        f"{owner} side_effects must be a SideEffect or string literal, got {type(value).__name__}"
    )


@dataclass(frozen=True)
class OpMetadata:
    """Metadata attached to functions decorated with ``@op(...)``."""

    title: str
    category: str = "Uncategorized"
    cacheable: bool = True
    allow_extra_inputs: bool = False
    side_effects: SideEffect = SideEffect.NONE

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("op title must be a non-empty string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("op category must be a non-empty string")
        if not isinstance(self.cacheable, bool):
            raise ValueError("op cacheable must be a bool")
        if not isinstance(self.allow_extra_inputs, bool):
            raise ValueError("op allow_extra_inputs must be a bool")
        coerced_se = _coerce_side_effects(self.side_effects, owner="op")
        object.__setattr__(self, "side_effects", coerced_se)
        if coerced_se == SideEffect.WRITE and self.cacheable is True:
            raise ValueError(
                "op declares side_effects='write' with cacheable=True; "
                "side-effecting write ops must set cacheable=False"
            )


class Op:
    """Base class for class-form PLynx operations."""

    TITLE: ClassVar[str] = ""
    CATEGORY: ClassVar[str] = "Uncategorized"
    CACHEABLE: ClassVar[bool] = True
    ALLOW_EXTRA_INPUTS: ClassVar[bool] = False
    SIDE_EFFECTS: ClassVar[SideEffect] = SideEffect.NONE

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "SIDE_EFFECTS" in cls.__dict__:
            cls.SIDE_EFFECTS = _coerce_side_effects(
                cls.__dict__["SIDE_EFFECTS"],
                owner=cls.__name__,
            )
        if "CACHEABLE" in cls.__dict__ and not isinstance(cls.__dict__["CACHEABLE"], bool):
            raise ValueError(f"{cls.__name__}.CACHEABLE must be a bool")
        if cls.SIDE_EFFECTS == SideEffect.WRITE:
            if "CACHEABLE" in cls.__dict__:
                if cls.__dict__["CACHEABLE"] is True:
                    raise ValueError(
                        f"{cls.__name__} declares SIDE_EFFECTS='write' with CACHEABLE=True; "
                        "side-effecting write ops must set CACHEABLE=False"
                    )
            else:
                cls.CACHEABLE = False

    def checkpoint(
        self,
        question: str,
        options: Sequence[str] | None = None,
        allow_freeform: bool = False,
    ) -> str:
        """Ask a checkpoint question or return the replayed answer for this attempt."""
        return _checkpoint(question, options=options, allow_freeform=allow_freeform)

    def checkpoint_batch(
        self,
        questions: Sequence[CheckpointQuestion | Mapping[str, object]],
    ) -> dict[str, AnswerValue]:
        """Ask several questions in one pause or return the replayed answers by question id."""
        return _checkpoint_batch(questions)

    def warn(self, message: str) -> None:
        """Record a non-fatal anomaly for this attempt (written to ``warnings`` in outputs)."""
        _warn(message)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the operation. Subclasses must override this method."""
        raise NotImplementedError("Op subclasses must implement run()")


def op(
    title: str,
    category: str = "Uncategorized",
    cacheable: bool | None = None,
    allow_extra_inputs: bool = False,
    side_effects: SideEffect | str = SideEffect.NONE,
) -> Callable[[F], F]:
    """Decorate a function as a PLynx operation."""
    coerced_se = _coerce_side_effects(side_effects, owner="op")
    resolved_cacheable = (coerced_se != SideEffect.WRITE) if cacheable is None else cacheable
    metadata = OpMetadata(
        title=title,
        category=category,
        cacheable=resolved_cacheable,
        allow_extra_inputs=allow_extra_inputs,
        side_effects=coerced_se,
    )

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
