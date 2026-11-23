"""Append-only ``events.jsonl`` reader and writer (PROTOCOL.md section 9)."""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from plynx.api_models import EventType, RunEvent

_RUN_EVENT_ADAPTER: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)
_TAIL_CHUNK_SIZE = 4096


@contextmanager
def _file_lock(lock_path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """Acquire an exclusive cross-process OS advisory lock (POSIX ``flock`` / Windows ``msvcrt``).

    OS-managed file locks are released automatically by the kernel if a writer process is killed.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Timed out waiting for event log lock: {lock_path}"
                        ) from None
                    time.sleep(0.005)
        else:
            import fcntl

            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Timed out waiting for event log lock: {lock_path}"
                        ) from None
                    time.sleep(0.005)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                with contextlib.suppress(OSError):
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                with contextlib.suppress(OSError):
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


class EventLog:
    """Append-only ``events.jsonl`` log for a single run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock_path = path.with_name(f"{path.name}.lock")
        self._last_seq: int | None = None
        self._last_size: int | None = None

    def _read_last_seq_from_tail_unlocked(self, file_size: int) -> int:
        """Read the highest ``seq`` from the end of ``events.jsonl`` in O(1) for normal lines."""
        if file_size <= 0 or not self.path.is_file():
            return 0
        with self.path.open("rb") as handle:
            pos = file_size
            buf = b""
            while pos > 0:
                read_size = min(_TAIL_CHUNK_SIZE, pos)
                pos -= read_size
                handle.seek(pos)
                buf = handle.read(read_size) + buf
                # Split lines; if we have at least one complete line (or reached start of file),
                # scan backwards for the last valid JSON object with an int seq.
                lines = buf.splitlines()
                start_idx = 0 if pos == 0 else 1
                for raw_line in reversed(lines[start_idx:]):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        obj = json.loads(stripped.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue
                    seq = obj.get("seq")
                    if isinstance(seq, int):
                        return seq
        return 0

    def _next_seq_unlocked(self) -> int:
        if not self.path.is_file():
            return 1
        file_size = self.path.stat().st_size
        if file_size == 0:
            return 1
        if self._last_seq is not None and self._last_size == file_size:
            return self._last_seq + 1
        return self._read_last_seq_from_tail_unlocked(file_size) + 1

    def append(
        self,
        event_type: EventType,
        data: Mapping[str, Any] | BaseModel,
        *,
        ts: float | None = None,
    ) -> RunEvent:
        """Append one event with the next strictly increasing ``seq`` (starting at 1)."""
        payload_data: dict[str, Any] = (
            data.model_dump(mode="json") if isinstance(data, BaseModel) else dict(data)
        )
        event_ts = time.time() if ts is None else ts
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with _file_lock(self._lock_path):
            seq = self._next_seq_unlocked()
            envelope: dict[str, Any] = {
                "seq": seq,
                "ts": event_ts,
                "type": event_type,
                "data": payload_data,
            }
            event: RunEvent = _RUN_EVENT_ADAPTER.validate_python(envelope)
            serialized = json.dumps(
                event.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                self._last_seq = seq
                self._last_size = handle.tell()
            return event

    def read_after(self, after_seq: int = 0) -> list[RunEvent]:
        """Return all stored events with ``seq > after_seq`` in ``seq`` order."""
        events, _ = self.read_from_offset(0, after_seq=after_seq)
        return events

    def read_from_offset(
        self,
        byte_offset: int = 0,
        *,
        after_seq: int = 0,
    ) -> tuple[list[RunEvent], int]:
        """Read complete JSONL events starting at ``byte_offset`` with ``seq > after_seq``.

        Returns ``(events, next_byte_offset)`` where ``next_byte_offset`` only advances
        past complete newline-terminated lines so partial writes are retried on the next read.
        """
        if not self.path.is_file():
            return [], byte_offset
        events: list[RunEvent] = []
        next_offset = byte_offset
        with self.path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            if file_size < byte_offset:
                byte_offset = 0
                next_offset = 0
            if file_size <= byte_offset:
                return [], next_offset
            handle.seek(byte_offset)
            while True:
                line_start = handle.tell()
                raw_line = handle.readline()
                if not raw_line:
                    break
                if not raw_line.endswith(b"\n"):
                    next_offset = line_start
                    break
                next_offset = handle.tell()
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    raw_obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seq = raw_obj.get("seq")
                if isinstance(seq, int) and seq <= after_seq:
                    continue
                event: RunEvent = _RUN_EVENT_ADAPTER.validate_python(raw_obj)
                events.append(event)
        return events, next_offset
