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
