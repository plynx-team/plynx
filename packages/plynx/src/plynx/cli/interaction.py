"""Interactive terminal prompting and answer loading helpers (PROTOCOL.md section 11)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import signal
import sys
import threading
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, TextIO, TypeVar

import click
from plynx_sdk.protocol import (
    AnswerValue,
    CheckpointAnswer,
    CheckpointManifest,
    CheckpointQuestion,
)

from plynx.api_models import WorkflowInputSpec

CheckpointPromptCallback = Callable[[str, str, CheckpointManifest], Awaitable[str | None]]
StagePromptCallback = Callable[[str, str], Awaitable[bool]]
StageInputsPromptCallback = Callable[
    [str, str, list[WorkflowInputSpec]],
    Awaitable[dict[str, Any] | None],
]
_T = TypeVar("_T")


def is_non_interactive(flag: bool) -> bool:
    """Return True if ``--non-interactive`` was passed or ``CI=true`` is set."""
    if flag:
        return True
    return os.environ.get("CI", "").strip().lower() == "true"


_BATCH_ANSWER_KEY_RE = re.compile(r"^(?P<cp>.+\.cp_[0-9]+)\.(?P<qid>[A-Za-z_][A-Za-z0-9_]*)$")


def parse_key_value_pair(pair: str, *, flag: str) -> tuple[str, str]:
    """Parse a ``KEY=VALUE`` CLI option value."""
    if "=" not in pair:
        raise click.BadParameter(f"Expected KEY=VALUE for {flag}, got {pair!r}")
    key, _, value = pair.partition("=")
    if not key.strip():
        raise click.BadParameter(f"Empty key in {pair!r} for {flag}")
    return key.strip(), value


def load_cli_answers(
    answers_file: Path | None,
    answer_pairs: Sequence[str],
) -> dict[str, CheckpointAnswer]:
    """Load pre-supplied checkpoint answers from ``--answers`` JSON file and ``--answer`` flags.

    Keys are ``<node>.cp_<n>``. A single-question checkpoint takes a string. A batch checkpoint
    takes an object mapping question id to ``str`` or ``list[str]`` in the JSON file, or
    ``<node>.cp_<n>.<question_id>=value`` flags (repeat a flag to build a ``multi_select`` list).
    ``--answer`` entries override entries from ``--answers``.
    """
    answers: dict[str, CheckpointAnswer] = {}
    flag_values: dict[str, dict[str, list[str]]] = {}
    if answers_file is not None:
        if not answers_file.is_file():
            raise click.ClickException(f"answers file not found: {answers_file}")
        try:
            loaded = json.loads(answers_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise click.ClickException(
                f"failed to read --answers file {answers_file}: {exc}"
            ) from exc
        if not isinstance(loaded, dict):
            raise click.ClickException("--answers file must contain a JSON object")
        for key, val in loaded.items():
            if isinstance(val, dict):
                answers[str(key)] = {
                    str(qid): [str(v) for v in item] if isinstance(item, list) else str(item)
                    for qid, item in val.items()
                }
            else:
                answers[str(key)] = str(val)

    for pair in answer_pairs:
        key, val = parse_key_value_pair(pair, flag="--answer")
        match = _BATCH_ANSWER_KEY_RE.match(key)
        if match is None:
            answers[key] = val
            flag_values.pop(key, None)
            continue
        cp_key, qid = match.group("cp"), match.group("qid")
        flag_values.setdefault(cp_key, {}).setdefault(qid, []).append(val)

    for cp_key, per_question in flag_values.items():
        answers[cp_key] = {
            qid: values[0] if len(values) == 1 else values for qid, values in per_question.items()
        }

    return answers


async def read_line_async(stream: TextIO) -> str | None:
    """Read one line from ``stream`` in a daemon thread; return ``None`` on EOF."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str | None] = loop.create_future()

    def _reader() -> None:
        try:
            line = stream.readline()
        except (OSError, ValueError):
            line = ""
        if not loop.is_closed() and not fut.done():
            loop.call_soon_threadsafe(fut.set_result, line if line != "" else None)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    return await fut


def parse_checkpoint_input(raw: str, cp: CheckpointManifest) -> tuple[bool, str | None, str | None]:
    """Validate and interpret one line of terminal input for ``cp``.

    Returns ``(ok, answer, error_message)``.
    """
    entry = raw.strip()
    options = cp.options or []

    if options:
        if entry.isdigit():
            idx = int(entry)
            if 1 <= idx <= len(options):
                return True, options[idx - 1], None
        if entry in options:
            return True, entry, None
        if cp.allow_freeform:
            if entry:
                return True, entry, None
            return False, None, f"Please enter [1-{len(options)}] or freeform text."
        return (
            False,
            None,
            f"Invalid selection {entry!r}. Enter a number in [1-{len(options)}].",
        )

    return True, entry, None


def parse_question_input(
    raw: str,
    q: CheckpointQuestion,
) -> tuple[bool, AnswerValue | None, str | None]:
    """Validate one line of terminal input for one question of a batch checkpoint.

    Multi-select input is comma separated (numbers, options, or freeform text).
    Returns ``(ok, answer, error_message)``.
    """
    entry = raw.strip()
    options = q.options
    tokens = [t.strip() for t in entry.split(",")] if q.multi_select else [entry]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False, None, "Please enter an answer."

    resolved: list[str] = []
    for token in tokens:
        if options:
            if token.isdigit() and 1 <= int(token) <= len(options):
                resolved.append(options[int(token) - 1])
                continue
            if token in options or q.allow_freeform:
                resolved.append(token)
                continue
            return (
                False,
                None,
                f"Invalid selection {token!r}. Enter a number in [1-{len(options)}].",
            )
        resolved.append(token)
    return True, (resolved if q.multi_select else resolved[0]), None


def make_terminal_checkpoint_callback(
    *,
    input_stream: TextIO | None = None,
    prompt_lock: asyncio.Lock | None = None,
) -> CheckpointPromptCallback:
    """Return an async callback that prompts the user on the terminal for checkpoints."""
    lock = prompt_lock if prompt_lock is not None else asyncio.Lock()

    async def _prompt(
        node_id: str,
        checkpoint_id: str,
        cp: CheckpointManifest,
    ) -> str | None:
        stream = input_stream if input_stream is not None else sys.stdin
        if cp.is_batch:
            return await _prompt_batch(stream, node_id, checkpoint_id, cp)
        options = cp.options or []
        async with lock:
            click.echo(f"\n[{node_id}.{checkpoint_id}] {cp.question}")
            for idx, opt in enumerate(options, start=1):
                click.echo(f"  {idx}. {opt}")

            while True:
                if options and cp.allow_freeform:
                    prompt_label = f"Select [1-{len(options)}] or enter text: "
                elif options:
                    prompt_label = f"Select [1-{len(options)}]: "
                else:
                    prompt_label = "Answer: "

                click.echo(prompt_label, nl=False)
                sys.stdout.flush()

                raw = await read_line_async(stream)
                if raw is None:
                    return None

                ok, answer, err_msg = parse_checkpoint_input(raw, cp)
                if ok and answer is not None:
                    return answer
                if err_msg:
                    click.echo(err_msg, err=True)

    async def _prompt_batch(
        stream: TextIO,
        node_id: str,
        checkpoint_id: str,
        cp: CheckpointManifest,
    ) -> str | None:
        collected: dict[str, AnswerValue] = {}
        async with lock:
            click.echo(f"\n[{node_id}.{checkpoint_id}] {len(cp.questions)} questions")
            for q in cp.questions:
                title = f"{q.header}: {q.question}" if q.header else q.question
                click.echo(f"\n{q.id}: {title}")
                for idx, opt in enumerate(q.options, start=1):
                    click.echo(f"  {idx}. {opt}")
                while True:
                    hint = "comma separated, " if q.multi_select else ""
                    click.echo(f"Answer ({hint}{q.id}): ", nl=False)
                    sys.stdout.flush()
                    raw = await read_line_async(stream)
                    if raw is None:
                        return None
                    ok, value, err_msg = parse_question_input(raw, q)
                    if ok and value is not None:
                        collected[q.id] = value
                        break
                    if err_msg:
                        click.echo(err_msg, err=True)
        return json.dumps(collected, ensure_ascii=False)

    return _prompt


def make_terminal_stage_approval_callback(
    *,
    input_stream: TextIO | None = None,
    prompt_lock: asyncio.Lock | None = None,
) -> StagePromptCallback:
    """Return an async callback that prompts the user to approve a stage gate."""
    lock = prompt_lock if prompt_lock is not None else asyncio.Lock()

    async def _prompt(stage_id: str, title: str) -> bool:
        stream = input_stream if input_stream is not None else sys.stdin
        async with lock:
            click.echo(f"\n[stage:{stage_id}] Stage '{title}' completed.")
            while True:
                click.echo("Approve & continue? [y/N]: ", nl=False)
                sys.stdout.flush()
                raw = await read_line_async(stream)
                if raw is None:
                    return False
                entry = raw.strip().lower()
                if entry in ("y", "yes"):
                    return True
                if entry in ("", "n", "no"):
                    return False
                click.echo("Please enter 'y' or 'n'.", err=True)

    return _prompt


def make_terminal_stage_inputs_callback(
    *,
    input_stream: TextIO | None = None,
    prompt_lock: asyncio.Lock | None = None,
) -> StageInputsPromptCallback:
    """Return an async callback that prompts the user on the terminal for deferred stage inputs."""
    lock = prompt_lock if prompt_lock is not None else asyncio.Lock()

    async def _prompt(
        stage_id: str,
        title: str,
        missing_inputs: list[WorkflowInputSpec],
    ) -> dict[str, Any] | None:
        stream = input_stream if input_stream is not None else sys.stdin
        provided: dict[str, Any] = {}
        async with lock:
            click.echo(f"\n[stage:{stage_id}] Stage '{title}' requires inputs:")
            for spec in missing_inputs:
                key = f"{spec.node_id}.{spec.name}"
                while True:
                    click.echo(f"  {key} ({spec.type}): ", nl=False)
                    sys.stdout.flush()
                    raw = await read_line_async(stream)
                    if raw is None:
                        return None
                    val_str = raw.rstrip("\r\n")
                    if spec.type == "str":
                        provided[key] = val_str
                        break
                    trimmed = val_str.strip()
                    if spec.type in ("file", "directory"):
                        if not trimmed:
                            click.echo(f"Please enter a non-empty {spec.type} path.", err=True)
                            continue
                        provided[key] = trimmed
                        break
                    try:
                        parsed = json.loads(trimmed)
                    except json.JSONDecodeError:
                        click.echo(f"Invalid {spec.type} value: {trimmed!r}", err=True)
                        continue
                    if spec.type == "int" and (
                        isinstance(parsed, bool) or not isinstance(parsed, int)
                    ):
                        click.echo(f"Expected int, got {trimmed!r}", err=True)
                        continue
                    if spec.type == "float" and (
                        isinstance(parsed, bool) or not isinstance(parsed, (int, float))
                    ):
                        click.echo(f"Expected float, got {trimmed!r}", err=True)
                        continue
                    if spec.type == "bool" and not isinstance(parsed, bool):
                        click.echo(f"Expected bool (true/false), got {trimmed!r}", err=True)
                        continue
                    if spec.type == "json" and not isinstance(parsed, (dict, list)):
                        click.echo(f"Expected JSON object or array, got {trimmed!r}", err=True)
                        continue
                    provided[key] = parsed
                    break
        return provided

    return _prompt


async def run_with_cancel_signals(
    coro_factory: Callable[[asyncio.Event], Awaitable[_T]],
) -> _T:
    """Run ``coro_factory(cancel_event)``, setting ``cancel_event`` on SIGINT/SIGTERM."""
    loop = asyncio.get_running_loop()
    cancel_event = asyncio.Event()
    registered_loop_sigs: list[int] = []
    saved_sync_sigs: list[tuple[int, Any]] = []

    signals_to_hook: list[int] = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        signals_to_hook.append(signal.SIGTERM)

    def _sync_handler(_signum: int, _frame: Any) -> None:
        if not loop.is_closed():
            loop.call_soon_threadsafe(cancel_event.set)

    for sig in signals_to_hook:
        try:
            loop.add_signal_handler(sig, cancel_event.set)
            registered_loop_sigs.append(sig)
        except NotImplementedError:
            try:
                prev = signal.getsignal(sig)
                signal.signal(sig, _sync_handler)
                saved_sync_sigs.append((sig, prev))
            except (ValueError, OSError):
                pass
        except (ValueError, RuntimeError, OSError):
            pass

    try:
        return await coro_factory(cancel_event)
    finally:
        for sig in registered_loop_sigs:
            with contextlib.suppress(ValueError, RuntimeError, NotImplementedError):
                loop.remove_signal_handler(sig)
        for sig, prev in saved_sync_sigs:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, prev)


__all__ = [
    "CheckpointPromptCallback",
    "StageInputsPromptCallback",
    "StagePromptCallback",
    "is_non_interactive",
    "load_cli_answers",
    "make_terminal_checkpoint_callback",
    "make_terminal_stage_approval_callback",
    "make_terminal_stage_inputs_callback",
    "parse_checkpoint_input",
    "parse_key_value_pair",
    "parse_question_input",
    "read_line_async",
    "run_with_cancel_signals",
]
