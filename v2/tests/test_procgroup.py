"""Tests for Task 1.4: ``plynx.engine.procgroup`` process-tree creation and termination."""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path

from plynx.engine.procgroup import (
    is_pid_alive,
    kill_process_group,
    spawn_process_group,
)


def _wait_until(predicate: object, timeout: float = 5.0) -> bool:
    assert callable(predicate)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return bool(predicate())


def test_kill_process_group_terminates_child_and_grandchild(tmp_path: Path) -> None:
    """Spawns a child that spawns a grandchild; after kill neither is alive."""
    grandchild_pid_file = tmp_path / "grandchild.pid"

    child_code = f"""
import subprocess
import sys
import time
from pathlib import Path

gc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path({str(grandchild_pid_file)!r}).write_text(str(gc.pid), encoding="utf-8")
time.sleep(60)
"""
    proc = spawn_process_group([sys.executable, "-c", child_code])
    try:
        assert _wait_until(grandchild_pid_file.is_file, timeout=5.0)
        grandchild_pid = int(grandchild_pid_file.read_text(encoding="utf-8").strip())
        child_pid = proc.pid

        assert is_pid_alive(child_pid)
        assert is_pid_alive(grandchild_pid)

        kill_process_group(child_pid)
        proc.wait(timeout=5.0)

        assert _wait_until(lambda: not is_pid_alive(child_pid), timeout=5.0)
        assert _wait_until(lambda: not is_pid_alive(grandchild_pid), timeout=5.0)
    finally:
        kill_process_group(proc.pid)
        with contextlib.suppress(Exception):
            proc.wait(timeout=2.0)


def test_is_pid_alive_windows_exact_pid_match() -> None:
    """Windows tasklist CSV parsing matches exact PIDs, not substrings."""
    from plynx.engine.procgroup import _parse_windows_tasklist_csv

    csv_output = '"python.exe","1234","Console","1","12,340 K"\n'
    assert _parse_windows_tasklist_csv(csv_output, 1234) is True
    assert _parse_windows_tasklist_csv(csv_output, 12) is False
    assert _parse_windows_tasklist_csv(csv_output, 234) is False
    assert _parse_windows_tasklist_csv("INFO: No tasks are running.\n", 12) is False


def test_is_pid_alive_posix_uses_no_subprocess(monkeypatch: object) -> None:
    """On POSIX, is_pid_alive uses os.kill(pid, 0) without spawning a ps subprocess."""
    import os
    import subprocess

    import pytest

    if sys.platform == "win32":
        return

    assert isinstance(monkeypatch, pytest.MonkeyPatch)

    def _forbid_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("is_pid_alive must not spawn subprocesses on POSIX")

    monkeypatch.setattr(subprocess, "run", _forbid_subprocess)
    assert is_pid_alive(os.getpid()) is True
    assert is_pid_alive(-1) is False
