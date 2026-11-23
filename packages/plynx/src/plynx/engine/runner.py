"""``LocalExecutor`` implementation for running node attempts in isolated ``uv`` environments."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import BinaryIO, Final

from plynx_sdk.protocol import (
    CheckpointManifest,
    OutputsManifest,
    ProtocolError,
)

from plynx.api_models import NodeStatus
from plynx.cas.materialize import safe_rmtree
from plynx.config import load_workspace_config
from plynx.engine.env import build_child_environment
from plynx.engine.executor import ExecutionRequest, NodeResult
from plynx.engine.procgroup import kill_process_group, spawn_async_process_group
from plynx.registry.pack_registry import (
    discover_packs,
    is_direct_builtin_pack,
)
from plynx.store.run_store import atomic_write_text

ENV_READY_SENTINEL: Final[str] = ".plynx_env_ready"


def _is_env_ready(env_dir: Path) -> bool:
    """Return True only when ``env_dir`` has both ``pyvenv.cfg`` and the ready sentinel."""
    return (env_dir / ENV_READY_SENTINEL).is_file() and (env_dir / "pyvenv.cfg").is_file()


def _acquire_env_file_lock(lock_path: Path) -> BinaryIO:
    """Acquire an exclusive cross-process file lock (POSIX ``flock`` / Windows ``msvcrt``)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except BaseException:
        handle.close()
        raise
    return handle


def _release_env_file_lock(handle: BinaryIO) -> None:
    """Release and close a file lock acquired by ``_acquire_env_file_lock``."""
    try:
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


def _parse_op_spec(op: str) -> tuple[str, str]:
    """Parse ``<pack>/<module>:<Name>`` into ``(pack, module:Name)``."""
    if ":" not in op:
        raise ValueError(f"Invalid op reference {op!r}: missing ':'")
    raw_mod, _, name = op.partition(":")
    raw_mod = raw_mod.strip()
    name = name.strip()
    if not raw_mod or not name:
        raise ValueError(f"Invalid op reference {op!r}")

    if "/" in raw_mod:
        pack_name, _, rest = raw_mod.partition("/")
        module_import = f"{pack_name}.{rest.replace('/', '.')}" if rest else pack_name
    elif "." in raw_mod:
        pack_name, _, _ = raw_mod.partition(".")
        module_import = raw_mod
    else:
        pack_name = raw_mod
        module_import = raw_mod

    return pack_name, f"{module_import}:{name}"


def _find_lock_bytes(pack_dir: Path) -> bytes:
    """Return bytes of ``pack_dir / 'uv.lock'``."""
    direct_lock = pack_dir / "uv.lock"
    if direct_lock.is_file():
        return direct_lock.read_bytes()
    return b""


def _has_lockfile(pack_dir: Path) -> bool:
    return (pack_dir / "uv.lock").is_file()


def _compute_env_hash(pack_dir: Path) -> str:
    pyproject_bytes = (pack_dir / "pyproject.toml").read_bytes()
    lock_bytes = _find_lock_bytes(pack_dir)
    digest = hashlib.sha256(pyproject_bytes + b"\n" + lock_bytes).hexdigest()
    return digest[:12]


def _resolve_logs_dir(node_dir: Path) -> Path:
    if node_dir.parent.name == "nodes":
        return node_dir.parent.parent / "logs"
    return node_dir / "logs"


def _prepare_log_files(logs_dir: Path, node_id: str, attempt: int) -> tuple[Path, Path]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{node_id}.stdout.log"
    stderr_path = logs_dir / f"{node_id}.stderr.log"
    separator = f"--- attempt {attempt} ---\n".encode()

    for path in (stdout_path, stderr_path):
        if attempt > 1 or (path.is_file() and path.stat().st_size > 0):
            with path.open("ab") as handle:
                handle.write(separator)
        elif not path.exists():
            path.write_bytes(b"")

    return stdout_path, stderr_path


def _extract_stderr_error(stderr_path: Path) -> str | None:
    if not stderr_path.is_file():
        return None
    try:
        text = stderr_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if not line.startswith("--- attempt "):
            return line
    return None


class LocalExecutor:
    """Executes node attempts locally in isolated ``uv`` environments (PROTOCOL.md section 5)."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        *,
        pack_dirs: Sequence[Path] | None = None,
        env_passthrough: Sequence[str] | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        config = load_workspace_config(self.workspace_root)
        if pack_dirs is not None:
            self.pack_dirs: list[Path] | None = [p.resolve() for p in pack_dirs]
        elif config.packs:
            self.pack_dirs = list(config.packs)
        else:
            self.pack_dirs = None
        if env_passthrough is not None:
            self.env_passthrough: list[str] | None = list(env_passthrough)
        elif config.env_passthrough is not None:
            self.env_passthrough = list(config.env_passthrough)
        else:
            self.env_passthrough = None
        self.extra_env: dict[str, str] = dict(extra_env) if extra_env else {}
        self._env_locks: dict[Path, asyncio.Lock] = {}

    def resolve_pack_dir(self, pack_name: str) -> Path | None:
        """Locate the directory containing ``pyproject.toml`` for ``pack_name``."""
        discovered = discover_packs(self.workspace_root, custom_pack_dirs=self.pack_dirs)
        return discovered.get(pack_name)

    def _build_child_env(self, env_dir: Path) -> dict[str, str]:
        return build_child_environment(
            self.workspace_root,
            env_dir,
            env_passthrough=self.env_passthrough,
            extra_env=self.extra_env,
        )

    def _build_direct_child_env(self, pack_dir: Path) -> dict[str, str]:
        """Build child env for stdlib-only built-in packs run directly via ``sys.executable``."""
        child_env = build_child_environment(
            self.workspace_root,
            env_dir=None,
            env_passthrough=self.env_passthrough,
            extra_env=self.extra_env,
        )
        src_root = pack_dir / "src" if (pack_dir / "src").is_dir() else pack_dir
        existing_pypath = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = (
            f"{src_root}{os.pathsep}{existing_pypath}" if existing_pypath else str(src_root)
        )
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        return child_env

    @staticmethod
    def _build_harness_cmd(
        pack_dir: Path,
        harness_op: str,
        node_dir: Path,
        *,
        direct_python: bool,
    ) -> list[str]:
        if direct_python:
            return [
                sys.executable,
                "-B",
                "-m",
                "plynx_sdk.harness",
                "--op",
                harness_op,
                "--dir",
                str(node_dir),
            ]
        cmd: list[str] = ["uv", "run"]
        if _has_lockfile(pack_dir):
            cmd.append("--frozen")
        cmd.extend(
            [
                "--no-dev",
                "--project",
                str(pack_dir),
                "python",
                "-m",
                "plynx_sdk.harness",
                "--op",
                harness_op,
                "--dir",
                str(node_dir),
            ]
        )
        return cmd

    def _get_env_lock(self, env_dir: Path) -> asyncio.Lock:
        lock = self._env_locks.get(env_dir)
        if lock is None:
            lock = asyncio.Lock()
            self._env_locks[env_dir] = lock
        return lock

    async def _resolve_child_env(
        self, pack_name: str, pack_dir: Path
    ) -> tuple[bool, Path | None, dict[str, str]]:
        """Resolve child environment settings and return (direct_python, env_dir, child_env)."""
        direct_python = is_direct_builtin_pack(pack_dir)
        env_dir: Path | None = None
        if direct_python:
            child_env = self._build_direct_child_env(pack_dir)
        else:
            env_hash = await asyncio.to_thread(_compute_env_hash, pack_dir)
            env_dir = (
                self.workspace_root / ".plynx" / "envs" / f"{pack_name}-{env_hash}"
            ).resolve()
            child_env = self._build_child_env(env_dir)
        return direct_python, env_dir, child_env

    async def _ensure_environment(
        self,
        request: ExecutionRequest,
        pack_dir: Path,
        env_dir: Path,
        child_env: Mapping[str, str],
    ) -> tuple[bool, str | None]:
        """Build ``env_dir`` on first use with cross-process locking and atomic readiness."""
        if _is_env_ready(env_dir):
            return True, None

        lock = self._get_env_lock(env_dir)
        async with lock:
            if _is_env_ready(env_dir):
                return True, None
            if request.cancel_event is not None and request.cancel_event.is_set():
                return False, "canceled"

            lock_path = env_dir.parent / f".{env_dir.name}.lock"
            file_lock = await asyncio.to_thread(_acquire_env_file_lock, lock_path)
            try:
                if _is_env_ready(env_dir):
                    return True, None
                if request.cancel_event is not None and request.cancel_event.is_set():
                    return False, "canceled"

                # Remove any partial/interrupted environment left without the ready sentinel.
                if env_dir.exists():
                    await asyncio.to_thread(safe_rmtree, env_dir)

                await request.notify_status(NodeStatus.BUILDING_ENVIRONMENT)
                await asyncio.to_thread(env_dir.parent.mkdir, parents=True, exist_ok=True)

                cmd = ["uv", "sync", "--no-dev", "--project", str(pack_dir)]
                if _has_lockfile(pack_dir):
                    cmd.insert(2, "--frozen")

                proc = await spawn_async_process_group(
                    cmd,
                    cwd=pack_dir,
                    env=child_env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                comm_task: asyncio.Task[tuple[bytes, bytes]] = asyncio.create_task(
                    proc.communicate()
                )
                try:
                    if request.cancel_event is None:
                        _, stderr_bytes = await comm_task
                    else:
                        cancel_task: asyncio.Task[bool] = asyncio.create_task(
                            request.cancel_event.wait()
                        )
                        done, _ = await asyncio.wait(
                            {comm_task, cancel_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if cancel_task in done and comm_task not in done:
                            kill_process_group(proc.pid)
                            await comm_task
                            if env_dir.exists():
                                await asyncio.to_thread(safe_rmtree, env_dir)
                            return False, "canceled"
                        if not cancel_task.done():
                            cancel_task.cancel()
                        _, stderr_bytes = await comm_task
                except BaseException:
                    if not comm_task.done():
                        kill_process_group(proc.pid)
                        with contextlib.suppress(BaseException):
                            await comm_task
                    if env_dir.exists():
                        await asyncio.to_thread(safe_rmtree, env_dir)
                    raise

                if proc.returncode != 0:
                    if env_dir.exists():
                        await asyncio.to_thread(safe_rmtree, env_dir)
                    err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
                    return False, f"Failed to build environment for {pack_dir.name}: {err_msg}"

                await asyncio.to_thread(
                    atomic_write_text,
                    env_dir / ENV_READY_SENTINEL,
                    "ready\n",
                )
                return True, None
            finally:
                await asyncio.to_thread(_release_env_file_lock, file_lock)

    async def run(self, request: ExecutionRequest) -> NodeResult:
        """Execute ``request`` via ``uv run`` and map its exit code per PROTOCOL.md section 5."""
        started_at = time.time()
        node_dir = request.node_dir.resolve()
        workdir = node_dir / "workdir"
        await asyncio.to_thread(workdir.mkdir, parents=True, exist_ok=True)

        # Remove stale manifest files from any earlier attempt on this node directory.
        for stale_name in ("outputs.json", "checkpoint.json"):
            stale_path = node_dir / stale_name
            if stale_path.is_file():
                await asyncio.to_thread(stale_path.unlink)

        await asyncio.to_thread(
            atomic_write_text,
            node_dir / "inputs.json",
            request.inputs.to_json(),
        )

        logs_dir = _resolve_logs_dir(node_dir)
        stdout_path, stderr_path = await asyncio.to_thread(
            _prepare_log_files,
            logs_dir,
            request.node_id,
            request.attempt,
        )

        try:
            pack_name, harness_op = _parse_op_spec(request.op)
        except ValueError as exc:
            await request.notify_status(NodeStatus.RUNNING)
            return NodeResult(
                status=NodeStatus.FAILED,
                exit_code=2,
                started_at=started_at,
                finished_at=time.time(),
                error=str(exc),
            )

        pack_dir = self.resolve_pack_dir(pack_name)
        if pack_dir is None:
            await request.notify_status(NodeStatus.RUNNING)
            msg = f"Pack {pack_name!r} not found for op {request.op!r}"
            await asyncio.to_thread(
                self._append_stderr_line,
                stderr_path,
                msg,
            )
            return NodeResult(
                status=NodeStatus.FAILED,
                exit_code=2,
                started_at=started_at,
                finished_at=time.time(),
                error=msg,
            )

        direct_python, env_dir, child_env = await self._resolve_child_env(pack_name, pack_dir)
        if env_dir is not None:
            ok_env, env_err = await self._ensure_environment(request, pack_dir, env_dir, child_env)
            if not ok_env:
                if request.cancel_event is not None and request.cancel_event.is_set():
                    return NodeResult(
                        status=NodeStatus.CANCELED,
                        exit_code=-9,
                        started_at=started_at,
                        finished_at=time.time(),
                        error="canceled",
                    )
                await request.notify_status(NodeStatus.RUNNING)
                if env_err:
                    await asyncio.to_thread(self._append_stderr_line, stderr_path, env_err)
                return NodeResult(
                    status=NodeStatus.FAILED,
                    exit_code=2,
                    started_at=started_at,
                    finished_at=time.time(),
                    error=env_err or "Environment build failed",
                )

        if request.cancel_event is not None and request.cancel_event.is_set():
            return NodeResult(
                status=NodeStatus.CANCELED,
                exit_code=-9,
                started_at=started_at,
                finished_at=time.time(),
                error="canceled",
            )

        started_at = time.time()
        await request.notify_status(NodeStatus.RUNNING)

        cmd = self._build_harness_cmd(
            pack_dir,
            harness_op,
            node_dir,
            direct_python=direct_python,
        )

        stdout_handle = stdout_path.open("ab")
        stderr_handle = stderr_path.open("ab")
        try:
            proc = await spawn_async_process_group(
                cmd,
                cwd=workdir,
                env=child_env,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            exit_code, killed_by_engine, kill_reason = await self._wait_for_process(
                proc,
                timeout=request.timeout,
                cancel_event=request.cancel_event,
            )
        finally:
            stdout_handle.close()
            stderr_handle.close()

        finished_at = time.time()
        if finished_at < started_at:
            finished_at = started_at

        if killed_by_engine:
            return NodeResult(
                status=NodeStatus.CANCELED,
                exit_code=exit_code,
                started_at=started_at,
                finished_at=finished_at,
                error=kill_reason,
            )

        return await asyncio.to_thread(
            self._interpret_exit,
            exit_code,
            node_dir=node_dir,
            stderr_path=stderr_path,
            started_at=started_at,
            finished_at=finished_at,
        )

    @staticmethod
    def _append_stderr_line(stderr_path: Path, message: str) -> None:
        with stderr_path.open("ab") as handle:
            handle.write((message.rstrip("\n") + "\n").encode("utf-8"))

    async def _wait_for_process(
        self,
        proc: asyncio.subprocess.Process,
        *,
        timeout: float | None,
        cancel_event: asyncio.Event | None,
    ) -> tuple[int, bool, str | None]:
        if cancel_event is not None and cancel_event.is_set():
            kill_process_group(proc.pid)
            rc = await proc.wait()
            return rc, True, "canceled"

        wait_task: asyncio.Task[int] = asyncio.create_task(proc.wait())
        cancel_task: asyncio.Task[bool] | None = (
            asyncio.create_task(cancel_event.wait()) if cancel_event is not None else None
        )
        tasks: set[asyncio.Task[object]] = {wait_task}
        if cancel_task is not None:
            tasks.add(cancel_task)

        try:
            done, _ = await asyncio.wait(
                tasks,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if wait_task in done:
                return wait_task.result(), False, None

            if cancel_task is not None and cancel_task in done:
                kill_process_group(proc.pid)
                rc = await wait_task
                return rc, True, "canceled"

            # Timed out
            kill_process_group(proc.pid)
            rc = await wait_task
            return rc, True, f"timeout after {timeout}s"
        except asyncio.CancelledError:
            kill_process_group(proc.pid)
            await wait_task
            raise
        finally:
            if cancel_task is not None and not cancel_task.done():
                cancel_task.cancel()
            if not wait_task.done():
                wait_task.cancel()

    @staticmethod
    def _interpret_exit(
        exit_code: int,
        *,
        node_dir: Path,
        stderr_path: Path,
        started_at: float,
        finished_at: float,
    ) -> NodeResult:
        if exit_code == 0:
            outputs_path = node_dir / "outputs.json"
            if not outputs_path.is_file():
                return NodeResult(
                    status=NodeStatus.FAILED,
                    exit_code=0,
                    started_at=started_at,
                    finished_at=finished_at,
                    error="protocol error: exit 0 without outputs.json",
                )
            try:
                outputs_manifest = OutputsManifest.from_json(outputs_path.read_bytes())
            except (ProtocolError, OSError) as exc:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    exit_code=0,
                    started_at=started_at,
                    finished_at=finished_at,
                    error=f"protocol error: invalid outputs.json: {exc}",
                )
            return NodeResult(
                status=NodeStatus.SUCCESS,
                exit_code=0,
                started_at=outputs_manifest.started_at,
                finished_at=outputs_manifest.finished_at,
                outputs=outputs_manifest,
            )

        if exit_code == 10:
            checkpoint_path = node_dir / "checkpoint.json"
            if not checkpoint_path.is_file():
                return NodeResult(
                    status=NodeStatus.FAILED,
                    exit_code=10,
                    started_at=started_at,
                    finished_at=finished_at,
                    error="protocol error: exit 10 without checkpoint.json",
                )
            try:
                cp_manifest = CheckpointManifest.from_json(checkpoint_path.read_bytes())
            except (ProtocolError, OSError) as exc:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    exit_code=10,
                    started_at=started_at,
                    finished_at=finished_at,
                    error=f"protocol error: invalid checkpoint.json: {exc}",
                )
            return NodeResult(
                status=NodeStatus.WAITING_FOR_USER,
                exit_code=10,
                started_at=started_at,
                finished_at=finished_at,
                checkpoint=cp_manifest,
            )

        stderr_err = _extract_stderr_error(stderr_path)
        if exit_code == 1:
            err_msg = stderr_err or "op raised an exception (exit 1)"
        elif exit_code == 2:
            err_msg = stderr_err or "protocol error (exit 2)"
        else:
            err_msg = stderr_err or f"process failed with exit code {exit_code}"

        return NodeResult(
            status=NodeStatus.FAILED,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            error=err_msg,
        )

    async def run_in_scratch(
        self,
        node_dir: Path,
        op: str,
        *,
        cancel_event: asyncio.Event | None = None,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
    ) -> int:
        """Re-run a node attempt from ``node_dir`` in a scratch copy without touching SQLite.

        Streams child stdout/stderr via ``on_stdout``/``on_stderr`` and returns a CLI exit code
        (0 success, 1 failure/protocol error, 2 checkpoint, 130 canceled).
        """
        src_dir = node_dir.resolve()
        inputs_json_src = src_dir / "inputs.json"
        if not inputs_json_src.is_file():
            if on_stderr is not None:
                on_stderr(f"error: inputs.json not found in {src_dir}\n")
            return 1

        try:
            pack_name, harness_op = _parse_op_spec(op)
        except ValueError as exc:
            if on_stderr is not None:
                on_stderr(f"error: {exc}\n")
            return 1

        pack_dir = self.resolve_pack_dir(pack_name)
        if pack_dir is None:
            if on_stderr is not None:
                on_stderr(f"error: Pack {pack_name!r} not found for op {op!r}\n")
            return 1

        direct_python, env_dir, child_env = await self._resolve_child_env(pack_name, pack_dir)

        scratch_dir = Path(
            await asyncio.to_thread(
                tempfile.mkdtemp,
                prefix=f"plynx-run-node-{src_dir.name}-",
            )
        )
        try:
            scratch_workdir = scratch_dir / "workdir"
            await asyncio.to_thread(scratch_workdir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(shutil.copy2, inputs_json_src, scratch_dir / "inputs.json")
            src_inputs_dir = src_dir / "inputs"
            if src_inputs_dir.is_dir():
                await asyncio.to_thread(
                    shutil.copytree,
                    src_inputs_dir,
                    scratch_dir / "inputs",
                )

            # Ensure the pack environment exists before running the harness (for uv-managed packs).
            if env_dir is not None and not _is_env_ready(env_dir):
                from plynx_sdk.protocol import InputsManifest

                dummy_req = ExecutionRequest(
                    run_id="scratch",
                    node_id=src_dir.name,
                    op=op,
                    attempt=1,
                    node_dir=scratch_dir,
                    inputs=InputsManifest(),
                    cancel_event=cancel_event,
                )
                ok_env, env_err = await self._ensure_environment(
                    dummy_req,
                    pack_dir,
                    env_dir,
                    child_env,
                )
                if not ok_env:
                    if cancel_event is not None and cancel_event.is_set():
                        return 130
                    if on_stderr is not None and env_err:
                        on_stderr(env_err + "\n")
                    return 1

            cmd = self._build_harness_cmd(
                pack_dir,
                harness_op,
                scratch_dir,
                direct_python=direct_python,
            )

            proc = await spawn_async_process_group(
                cmd,
                cwd=scratch_workdir,
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def _pump(
                reader: asyncio.StreamReader | None,
                sink: Callable[[str], None] | None,
            ) -> None:
                if reader is None:
                    return
                while True:
                    chunk = await reader.read(4096)
                    if not chunk:
                        break
                    if sink is not None:
                        sink(chunk.decode("utf-8", errors="replace"))

            stdout_task = asyncio.create_task(_pump(proc.stdout, on_stdout))
            stderr_task = asyncio.create_task(_pump(proc.stderr, on_stderr))
            exit_code, killed_by_engine, _ = await self._wait_for_process(
                proc,
                timeout=None,
                cancel_event=cancel_event,
            )
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

            if killed_by_engine:
                return 130
            if exit_code == 0:
                outputs_path = scratch_dir / "outputs.json"
                if not outputs_path.is_file():
                    if on_stderr is not None:
                        on_stderr("error: protocol error: exit 0 without outputs.json\n")
                    return 1
                try:
                    OutputsManifest.from_json(outputs_path.read_bytes())
                except (ProtocolError, OSError) as exc:
                    if on_stderr is not None:
                        on_stderr(f"error: protocol error: invalid outputs.json: {exc}\n")
                    return 1
                return 0
            if exit_code == 10:
                cp_path = scratch_dir / "checkpoint.json"
                if cp_path.is_file():
                    with contextlib.suppress(ProtocolError, OSError):
                        cp = CheckpointManifest.from_json(cp_path.read_bytes())
                        if on_stdout is not None:
                            on_stdout(f"\n[checkpoint {cp.checkpoint_id}] {cp.question}\n")
                return 2
            return 1
        finally:
            await asyncio.to_thread(safe_rmtree, scratch_dir)


__all__ = ["LocalExecutor"]
