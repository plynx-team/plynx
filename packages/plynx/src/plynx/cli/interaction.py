"""Interactive terminal prompting and answer loading helpers (PROTOCOL.md section 11)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
import threading
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, TextIO, TypeVar

import click
from plynx_sdk.protocol import CheckpointManifest

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
) -> dict[str, str]:
    """Load pre-supplied checkpoint answers from ``--answers`` JSON file and ``--answer`` flags.

    ``--answer`` entries override entries from ``--answers``.
    """
    answers: dict[str, str] = {}
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
            answers[str(key)] = str(val)

    for pair in answer_pairs:
        key, val = parse_key_value_pair(pair, flag="--answer")
        answers[key] = val

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
    "read_line_async",
    "run_with_cancel_signals",
]
