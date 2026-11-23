"""Checkpoint interrupt and replay state (PROTOCOL.md section 5).

Standard library only.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from plynx_sdk.protocol import CheckpointManifest


class CheckpointInterrupt(BaseException):
    """Raised when ``checkpoint()`` pauses a node attempt for user input.

    Inherits from ``BaseException`` so ``except Exception:`` inside op code
    does not swallow a checkpoint interrupt.
    """

    def __init__(self, manifest: CheckpointManifest) -> None:
        super().__init__(f"Checkpoint {manifest.checkpoint_id}: {manifest.question}")
        self.manifest = manifest


@dataclass
class _CheckpointState:
    """Per-attempt checkpoint counter, pre-supplied answers, and target node directory."""

    answers: dict[str, str] = field(default_factory=dict)
    node_dir: Path | None = None
    call_index: int = 0


_CURRENT_STATE: ContextVar[_CheckpointState | None] = ContextVar(
    "_plynx_checkpoint_state", default=None
)


def _atomic_write_checkpoint(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


@contextmanager
def checkpoint_context(
    answers: Mapping[str, str] | None = None,
    node_dir: Path | None = None,
) -> Iterator[None]:
    """Bind checkpoint replay answers and ``node_dir`` for a single op execution attempt."""
    state = _CheckpointState(
        answers=dict(answers) if answers is not None else {},
        node_dir=node_dir,
        call_index=0,
    )
    token = _CURRENT_STATE.set(state)
    try:
        yield
    finally:
        _CURRENT_STATE.reset(token)


def checkpoint(
    question: str,
    options: Sequence[str] | None = None,
    allow_freeform: bool = False,
) -> str:
    """Ask a checkpoint question or replay its stored answer.

    Each call within an attempt gets id ``cp_<n>`` where ``n`` starts at 0.
    If ``checkpoint_answers`` contains ``cp_<n>``, returns that string answer.
    Otherwise writes ``checkpoint.json`` (when running in a node directory) and
    raises ``CheckpointInterrupt``.
    """
    state = _CURRENT_STATE.get()
    if state is None:
        idx = 0
        answers: dict[str, str] = {}
        node_dir: Path | None = None
    else:
        idx = state.call_index
        state.call_index += 1
        answers = state.answers
        node_dir = state.node_dir

    cp_id = f"cp_{idx}"
    opt_list = list(options) if options is not None else None
    manifest = CheckpointManifest(
        checkpoint_id=cp_id,
        question=question,
        options=opt_list,
        allow_freeform=allow_freeform,
    )

    if cp_id in answers:
        return answers[cp_id]

    if node_dir is not None:
        _atomic_write_checkpoint(node_dir / "checkpoint.json", manifest.to_json())

    raise CheckpointInterrupt(manifest)


__all__ = [
    "CheckpointInterrupt",
    "checkpoint",
    "checkpoint_context",
]
