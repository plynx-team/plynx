"""OS-specific process group creation and tree termination (ARCHITECTURE.md invariant 13).

POSIX uses ``start_new_session=True`` and ``os.killpg(..., SIGKILL)``.
Windows uses ``CREATE_NEW_PROCESS_GROUP`` and ``taskkill /PID <pid> /T /F``.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_IS_WINDOWS = sys.platform == "win32"
_CREATE_NEW_PROCESS_GROUP: int = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)


def popen_group_kwargs() -> dict[str, Any]:
    """Return platform-specific kwargs to start a child in a new process group."""
    if _IS_WINDOWS:
        return {"creationflags": _CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def spawn_process_group(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> subprocess.Popen[bytes]:
    """Start a synchronous ``subprocess.Popen`` in its own process group."""
    return subprocess.Popen(
        list(args),
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        stdout=stdout,
        stderr=stderr,
        **popen_group_kwargs(),
    )


async def spawn_async_process_group(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> asyncio.subprocess.Process:
    """Start an ``asyncio.subprocess.Process`` in its own process group."""
    return await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        stdout=stdout,
        stderr=stderr,
        **popen_group_kwargs(),
    )


def kill_process_group(pid: int) -> None:
    """Forcefully terminate the process group / process tree rooted at ``pid``."""
    if pid <= 0:
        return
    if _IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    killpg_fn = getattr(os, "killpg", None)
    getpgid_fn = getattr(os, "getpgid", None)
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)

    pgid = pid
    if callable(getpgid_fn):
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            pgid = int(getpgid_fn(pid))

    if callable(killpg_fn):
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            killpg_fn(pgid, sigkill)

    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(pid, sigkill)


def is_pid_alive(pid: int) -> bool:
    """Return ``True`` if a non-zombie process with ``pid`` is currently alive."""
    if pid <= 0:
        return False
    if _IS_WINDOWS:
        res = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in res.stdout

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False

    # On POSIX, check that the process is not a defunct zombie ('Z').
    res = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    stat_str = res.stdout.strip()
    if not stat_str:
        return False
    return not stat_str.upper().startswith("Z")


__all__ = [
    "is_pid_alive",
    "kill_process_group",
    "popen_group_kwargs",
    "spawn_async_process_group",
    "spawn_process_group",
]
