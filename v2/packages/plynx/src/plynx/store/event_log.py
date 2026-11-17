"""Append-only ``events.jsonl`` reader and writer (PROTOCOL.md section 9)."""

from __future__ import annotations

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


@contextmanager
def _file_lock(lock_path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """Acquire an exclusive cross-process lock via atomic ``O_CREAT | O_EXCL``."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for event log lock: {lock_path}") from None
            time.sleep(0.001)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock_path.unlink(missing_ok=True)


class EventLog:
    """Append-only ``events.jsonl`` log for a single run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock_path = path.with_name(f"{path.name}.lock")

    def _read_last_seq_unlocked(self) -> int:
        if not self.path.is_file():
            return 0
        last_seq = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                seq = obj.get("seq")
                if isinstance(seq, int) and seq > last_seq:
                    last_seq = seq
        return last_seq

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
            seq = self._read_last_seq_unlocked() + 1
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
            return event

    def read_after(self, after_seq: int = 0) -> list[RunEvent]:
        """Return all stored events with ``seq > after_seq`` in ``seq`` order."""
        if not self.path.is_file():
            return []
        events: list[RunEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    raw_obj = json.loads(line)
                except json.JSONDecodeError:
                    # Ignore a partial trailing line if a reader races with an active writer.
                    continue
                seq = raw_obj.get("seq")
                if isinstance(seq, int) and seq <= after_seq:
                    continue
                event: RunEvent = _RUN_EVENT_ADAPTER.validate_python(raw_obj)
                events.append(event)
        return events
