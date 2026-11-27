"""Non-fatal per-attempt warnings via ``warn()`` (PROTOCOL.md section 5).

Standard library only.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_CURRENT_WARNINGS: ContextVar[list[str] | None] = ContextVar("_plynx_warnings", default=None)


@contextmanager
def warning_context() -> Iterator[list[str]]:
    """Collect ``warn()`` messages for a single op execution attempt."""
    collected: list[str] = []
    token = _CURRENT_WARNINGS.set(collected)
    try:
        yield collected
    finally:
        _CURRENT_WARNINGS.reset(token)


def warn(message: str) -> None:
    """Record a non-fatal anomaly for this attempt; the op keeps running and may exit 0.

    Outside a harness attempt the message is written to stderr instead.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("warn() message must be a non-empty string")
    collected = _CURRENT_WARNINGS.get()
    if collected is None:
        print(f"warning: {message}", file=sys.stderr)
        return
    collected.append(message)


__all__ = ["warn", "warning_context"]
