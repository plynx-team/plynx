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

from plynx_sdk.protocol import (
    SINGLE_QUESTION_ID,
    AnswerValue,
    CheckpointAnswer,
    CheckpointManifest,
    CheckpointQuestion,
    ProtocolError,
    validate_batch_answers,
)


class CheckpointInterrupt(BaseException):
    """Raised when ``checkpoint()`` pauses a node attempt for user input.

    Inherits from ``BaseException`` so ``except Exception:`` inside op code
    does not swallow a checkpoint interrupt.
    """

    def __init__(self, manifest: CheckpointManifest) -> None:
        super().__init__(f"Checkpoint {manifest.checkpoint_id}: {manifest.display_question()}")
        self.manifest = manifest


@dataclass
class _CheckpointState:
    """Per-attempt checkpoint counter, pre-supplied answers, and target node directory."""

    answers: dict[str, CheckpointAnswer] = field(default_factory=dict)
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
    answers: Mapping[str, CheckpointAnswer] | None = None,
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


def _next_slot() -> tuple[str, dict[str, CheckpointAnswer], Path | None]:
    """Allocate the next ``cp_<n>`` id and return it with the replay answers and node dir."""
    state = _CURRENT_STATE.get()
    if state is None:
        return "cp_0", {}, None
    idx = state.call_index
    state.call_index += 1
    return f"cp_{idx}", state.answers, state.node_dir


def _interrupt(manifest: CheckpointManifest, node_dir: Path | None) -> CheckpointInterrupt:
    if node_dir is not None:
        _atomic_write_checkpoint(node_dir / "checkpoint.json", manifest.to_json())
    return CheckpointInterrupt(manifest)


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
    cp_id, answers, node_dir = _next_slot()
    manifest = CheckpointManifest(
        checkpoint_id=cp_id,
        question=question,
        options=list(options) if options is not None else None,
        allow_freeform=allow_freeform,
    )

    if cp_id in answers:
        stored = answers[cp_id]
        if isinstance(stored, str):
            return stored
        single = stored.get(SINGLE_QUESTION_ID)
        if isinstance(single, str):
            return single
        raise ProtocolError(f"{cp_id}: stored answer does not match a single-question checkpoint")

    raise _interrupt(manifest, node_dir)


def checkpoint_batch(
    questions: Sequence[CheckpointQuestion | Mapping[str, object]],
) -> dict[str, AnswerValue]:
    """Ask several questions in one pause, or replay the stored answers.

    Returns a map of question id to answer: ``str`` for ``multi_select=False`` and
    ``list[str]`` for ``multi_select=True``. The id ``"default"`` is reserved for
    single-question ``checkpoint()``.
    """
    parsed = [
        q if isinstance(q, CheckpointQuestion) else CheckpointQuestion.from_dict(q)
        for q in questions
    ]
    if not parsed:
        raise ProtocolError("checkpoint_batch: at least one question is required")
    if any(q.id == SINGLE_QUESTION_ID for q in parsed):
        raise ProtocolError(f"checkpoint_batch: question id {SINGLE_QUESTION_ID!r} is reserved")

    cp_id, answers, node_dir = _next_slot()
    manifest = CheckpointManifest(checkpoint_id=cp_id, questions=parsed)

    if cp_id in answers:
        stored = answers[cp_id]
        if not isinstance(stored, dict):
            raise ProtocolError(f"{cp_id}: stored answer does not match a batch checkpoint")
        return validate_batch_answers(parsed, stored)

    raise _interrupt(manifest, node_dir)


__all__ = [
    "CheckpointInterrupt",
    "checkpoint",
    "checkpoint_batch",
    "checkpoint_context",
]
