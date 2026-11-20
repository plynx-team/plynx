"""SQLite state store and run directory creation (PROTOCOL.md sections 7 & 8)."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from plynx.api_models import (
    CheckpointState,
    NodeRunState,
    NodeStatus,
    NodeStatusData,
    RunState,
    RunStatus,
    RunStatusData,
    RunSummary,
    StageGateState,
    StageGateStatus,
)
from plynx.store.event_log import EventLog

USER_VERSION: Final[int] = 1
PLYNX_VERSION: Final[str] = "2.0.0"

SCHEMA_SQL: Final[str] = """
CREATE TABLE runs (
  id TEXT PRIMARY KEY, workflow_path TEXT NOT NULL, workflow_sha256 TEXT NOT NULL,
  status TEXT NOT NULL, run_inputs_json TEXT NOT NULL DEFAULT '{}',
  owner_pid INTEGER, cancel_requested INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, started_at REAL, finished_at REAL, error TEXT
);
CREATE TABLE node_runs (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, node_id TEXT NOT NULL,
  status TEXT NOT NULL, cache_hit INTEGER NOT NULL DEFAULT 0, cache_key TEXT,
  attempt INTEGER NOT NULL DEFAULT 0, exit_code INTEGER, error TEXT,
  started_at REAL, finished_at REAL, PRIMARY KEY (run_id, node_id)
);
CREATE TABLE checkpoints (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, node_id TEXT NOT NULL,
  checkpoint_id TEXT NOT NULL, question TEXT NOT NULL, options_json TEXT,
  allow_freeform INTEGER NOT NULL DEFAULT 0,
  answer TEXT, created_at REAL NOT NULL, answered_at REAL,
  PRIMARY KEY (run_id, node_id, checkpoint_id)
);
CREATE TABLE stage_gates (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, stage_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('WAITING','APPROVED')),
  created_at REAL NOT NULL, decided_at REAL, PRIMARY KEY (run_id, stage_id)
);
CREATE TABLE cache_index (
  cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL,
  created_at REAL NOT NULL, last_accessed_at REAL NOT NULL
);
"""


class StoreError(RuntimeError):
    """Base error raised by ``RunStore``."""


class StoreVersionError(StoreError):
    """Raised when ``.plynx/plynx.db`` has an unknown ``PRAGMA user_version``."""


class RunNotFoundError(StoreError):
    """Raised when a run ID or prefix does not match any run."""


class RunOwnershipError(StoreError):
    """Raised when attempting to resume a run owned by another live process."""


class AmbiguousRunIdError(StoreError):
    """Raised when a run ID prefix matches multiple runs."""

    def __init__(self, prefix: str, candidates: list[str]) -> None:
        self.prefix = prefix
        self.candidates = candidates
        joined = ", ".join(candidates)
        super().__init__(f"Ambiguous run ID prefix {prefix!r}: matches {joined}")


def generate_run_id(now: float | None = None) -> str:
    """Generate a UTC run ID matching ``YYYYMMDD_HHMMSS_<6 hex>``."""
    ts = time.time() if now is None else now
    dt = datetime.fromtimestamp(ts, tz=UTC)
    return f"{dt.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"


def atomic_write_bytes(target: Path, data: bytes) -> None:
    """Atomically write ``data`` to ``target`` via a temporary file and ``os.replace``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(target: Path, text: str) -> None:
    """Atomically write UTF-8 ``text`` (with ``\\n`` newlines and no BOM) to ``target``."""
    normalized = text.replace("\r\n", "\n")
    atomic_write_bytes(target, normalized.encode("utf-8"))


class RunStore:
    """SQLite state store and run directory manager for a PLynx workspace."""

    def __init__(self, workspace_root: Path, db_path: Path | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.plynx_dir = self.workspace_root / ".plynx"
        self.db_path = (db_path or (self.plynx_dir / "plynx.db")).resolve()
        self.runs_dir = self.plynx_dir / "runs"
        self._ensure_initialized()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
        finally:
            conn.close()

    def _ensure_initialized(self) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                row = conn.execute("PRAGMA user_version;").fetchone()
                version = int(row[0]) if row is not None else 0
                if version == 0:
                    tables = conn.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name NOT LIKE 'sqlite_%';"
                    ).fetchall()
                    if tables:
                        raise StoreVersionError(
                            "Unknown database version 0: delete `.plynx/plynx.db`"
                        )
                    for stmt in SCHEMA_SQL.strip().split(";"):
                        cleaned = stmt.strip()
                        if cleaned:
                            conn.execute(cleaned)
                    conn.execute(f"PRAGMA user_version = {USER_VERSION};")
                elif version != USER_VERSION:
                    raise StoreVersionError(
                        f"Unknown database version {version}: delete `.plynx/plynx.db`"
                    )
                conn.execute("COMMIT;")
            except BaseException:
                conn.execute("ROLLBACK;")
                raise

    def run_dir(self, run_id: str) -> Path:
        """Return the directory path `.plynx/runs/<run_id>`."""
        return self.runs_dir / run_id

    def node_dir(self, run_id: str, node_id: str) -> Path:
        """Return the node directory path `.plynx/runs/<run_id>/nodes/<node_id>`."""
        return self.run_dir(run_id) / "nodes" / node_id

    def event_log(self, run_id: str) -> EventLog:
        """Return the ``EventLog`` for ``run_id``."""
        return EventLog(self.run_dir(run_id) / "events.jsonl")

    def create_run(
        self,
        *,
        workflow_path: str,
        workflow_bytes: bytes,
        node_ids: Sequence[str],
        run_inputs: Mapping[str, Any] | None = None,
        owner_pid: int | None = None,
        run_id: str | None = None,
        layout_bytes: bytes | None = None,
        created_at: float | None = None,
        status: RunStatus = RunStatus.RUNNING,
    ) -> str:
        """Create a run directory on disk and insert initial ``runs`` and ``node_runs`` rows."""
        resolved_run_id = run_id or generate_run_id(created_at)
        now = time.time() if created_at is None else created_at
        pid = os.getpid() if owner_pid is None else owner_pid
        workflow_sha256 = hashlib.sha256(workflow_bytes).hexdigest()
        inputs_dict = dict(run_inputs) if run_inputs is not None else {}
        inputs_json = json.dumps(inputs_dict, ensure_ascii=False, sort_keys=True)

        rdir = self.run_dir(resolved_run_id)
        (rdir / "logs").mkdir(parents=True, exist_ok=True)
        for nid in node_ids:
            ndir = self.node_dir(resolved_run_id, nid)
            (ndir / "inputs").mkdir(parents=True, exist_ok=True)
            (ndir / "workdir").mkdir(parents=True, exist_ok=True)

        atomic_write_bytes(rdir / "workflow.snapshot.yaml", workflow_bytes)
        if layout_bytes is not None:
            atomic_write_bytes(rdir / "layout.snapshot.json", layout_bytes)

        manifest = {
            "schema": 1,
            "run_id": resolved_run_id,
            "workflow_path": workflow_path,
            "workflow_sha256": workflow_sha256,
            "plynx_version": PLYNX_VERSION,
            "created_at": now,
            "run_inputs": inputs_dict,
        }
        atomic_write_text(
            rdir / "run_manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        )
        events_path = rdir / "events.jsonl"
        if not events_path.exists():
            events_path.touch()

        started_at = now if status == RunStatus.RUNNING else None
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                conn.execute(
                    """
                    INSERT INTO runs (
                      id, workflow_path, workflow_sha256, status, run_inputs_json,
                      owner_pid, cancel_requested, pinned, created_at, started_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                    """,
                    (
                        resolved_run_id,
                        workflow_path,
                        workflow_sha256,
                        status.value,
                        inputs_json,
                        pid,
                        now,
                        started_at,
                    ),
                )
                for nid in node_ids:
                    conn.execute(
                        """
                        INSERT INTO node_runs (run_id, node_id, status, cache_hit, attempt)
                        VALUES (?, ?, ?, 0, 0)
                        """,
                        (resolved_run_id, nid, NodeStatus.PENDING.value),
                    )
                conn.execute("COMMIT;")
            except BaseException:
                conn.execute("ROLLBACK;")
                raise

        return resolved_run_id

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        started_at: float | None = None,
        finished_at: float | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status and optional timestamps/error on a ``runs`` row."""
        sets = ["status = ?"]
        params: list[Any] = [status.value]
        if started_at is not None:
            sets.append("started_at = ?")
            params.append(started_at)
        if finished_at is not None:
            sets.append("finished_at = ?")
            params.append(finished_at)
        if error is not None:
            sets.append("error = ?")
            params.append(error)
        params.append(run_id)
        sql = f"UPDATE runs SET {', '.join(sets)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(sql, params)

    def update_node_status(
        self,
        run_id: str,
        node_id: str,
        status: NodeStatus,
        *,
        cache_hit: bool | None = None,
        cache_key: str | None = None,
        attempt: int | None = None,
        exit_code: int | None = None,
        error: str | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
    ) -> None:
        """Update a ``node_runs`` row."""
        sets = ["status = ?"]
        params: list[Any] = [status.value]
        if cache_hit is not None:
            sets.append("cache_hit = ?")
            params.append(1 if cache_hit else 0)
        if cache_key is not None:
            sets.append("cache_key = ?")
            params.append(cache_key)
        if attempt is not None:
            sets.append("attempt = ?")
            params.append(attempt)
        if exit_code is not None:
            sets.append("exit_code = ?")
            params.append(exit_code)
        if error is not None:
            sets.append("error = ?")
            params.append(error)
        if started_at is not None:
            sets.append("started_at = ?")
            params.append(started_at)
        if finished_at is not None:
            sets.append("finished_at = ?")
            params.append(finished_at)
        params.extend([run_id, node_id])
        sql = f"UPDATE node_runs SET {', '.join(sets)} WHERE run_id = ? AND node_id = ?"
        with self._connect() as conn:
            conn.execute(sql, params)

    def reset_node_for_retry(self, run_id: str, node_id: str) -> None:
        """Reset a non-succeeded node to ``PENDING`` while preserving its ``attempt`` counter."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE node_runs
                SET status = 'PENDING', exit_code = NULL, error = NULL, finished_at = NULL
                WHERE run_id = ? AND node_id = ?
                """,
                (run_id, node_id),
            )

    def release_ownership(self, run_id: str, *, expected_pid: int | None = None) -> None:
        """Clear ``owner_pid`` when a run exits cleanly without an active owner (e.g. paused)."""
        with self._connect() as conn:
            if expected_pid is None:
                conn.execute("UPDATE runs SET owner_pid = NULL WHERE id = ?", (run_id,))
            else:
                conn.execute(
                    "UPDATE runs SET owner_pid = NULL WHERE id = ? AND owner_pid = ?",
                    (run_id, expected_pid),
                )

    def claim_run_for_resume(
        self,
        run_id: str,
        *,
        owner_pid: int | None = None,
    ) -> RunState:
        """Take ownership of a failed, waiting, canceled, or orphaned run for resume."""
        pid = os.getpid() if owner_pid is None else owner_pid
        now = time.time()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                row = conn.execute(
                    "SELECT status, owner_pid FROM runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                if row is None:
                    raise RunNotFoundError(f"No run matching {run_id!r}")
                current_status = RunStatus(str(row["status"]))
                existing_pid = row["owner_pid"]

                if current_status == RunStatus.SUCCESS:
                    raise StoreError(f"Run {run_id!r} already succeeded and cannot be resumed")
                if (
                    current_status in (RunStatus.RUNNING, RunStatus.WAITING_FOR_USER)
                    and existing_pid is not None
                    and int(existing_pid) != pid
                ):
                    from plynx.engine.procgroup import is_pid_alive

                    if is_pid_alive(int(existing_pid)):
                        raise RunOwnershipError(
                            f"Run {run_id!r} is currently owned by live process PID {existing_pid}"
                        )

                conn.execute(
                    """
                    UPDATE runs
                    SET status = 'RUNNING',
                        owner_pid = ?,
                        cancel_requested = 0,
                        finished_at = NULL,
                        error = NULL,
                        started_at = COALESCE(started_at, ?)
                    WHERE id = ?
                    """,
                    (pid, now, run_id),
                )
                conn.execute("COMMIT;")
            except BaseException:
                conn.execute("ROLLBACK;")
                raise

        state = self.get_run_state(run_id)
        assert state is not None
        return state

    def reconcile_dead_owners(
        self,
        *,
        is_alive: Callable[[int], bool] | None = None,
    ) -> list[str]:
        """Mark active runs whose ``owner_pid`` is gone as ``FAILED`` (``engine_died``)."""
        if is_alive is None:
            from plynx.engine.procgroup import is_pid_alive

            check_alive: Callable[[int], bool] = is_pid_alive
        else:
            check_alive = is_alive

        with self._connect() as conn:
            candidates = conn.execute(
                """
                SELECT id, owner_pid
                FROM runs
                WHERE status IN ('RUNNING', 'WAITING_FOR_USER') AND owner_pid IS NOT NULL
                """
            ).fetchall()

        reaped: list[str] = []
        now = time.time()
        for cand in candidates:
            run_id = str(cand["id"])
            owner_pid = int(cand["owner_pid"])
            if check_alive(owner_pid):
                continue

            orphaned_nodes: list[tuple[str, int]] = []
            transitioned = False
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    cursor = conn.execute(
                        """
                        UPDATE runs
                        SET status = 'FAILED',
                            error = 'engine_died',
                            finished_at = ?,
                            owner_pid = NULL
                        WHERE id = ? AND owner_pid = ? AND status IN ('RUNNING', 'WAITING_FOR_USER')
                        """,
                        (now, run_id, owner_pid),
                    )
                    if cursor.rowcount == 1:
                        transitioned = True
                        node_rows = conn.execute(
                            """
                            SELECT node_id, attempt
                            FROM node_runs
                            WHERE run_id = ? AND status IN ('RUNNING', 'BUILDING_ENVIRONMENT')
                            """,
                            (run_id,),
                        ).fetchall()
                        for nrow in node_rows:
                            orphaned_nodes.append((str(nrow["node_id"]), int(nrow["attempt"])))
                        if orphaned_nodes:
                            conn.execute(
                                """
                                UPDATE node_runs
                                SET status = 'FAILED',
                                    error = 'engine_died',
                                    finished_at = ?
                                WHERE run_id = ? AND status IN ('RUNNING', 'BUILDING_ENVIRONMENT')
                                """,
                                (now, run_id),
                            )
                    conn.execute("COMMIT;")
                except BaseException:
                    conn.execute("ROLLBACK;")
                    raise

            if transitioned:
                reaped.append(run_id)
                if self.run_dir(run_id).is_dir():
                    event_log = self.event_log(run_id)
                    for nid, attempt in orphaned_nodes:
                        event_log.append(
                            "node_status",
                            NodeStatusData(
                                run_id=run_id,
                                node_id=nid,
                                status=NodeStatus.FAILED,
                                cache_hit=False,
                                attempt=attempt,
                                error="engine_died",
                            ),
                        )
                    event_log.append(
                        "run_status",
                        RunStatusData(
                            run_id=run_id,
                            status=RunStatus.FAILED,
                            error="engine_died",
                        ),
                    )

        return reaped

    def request_cancel(self, run_id: str) -> None:
        """Set ``cancel_requested = 1`` on a run."""
        with self._connect() as conn:
            conn.execute("UPDATE runs SET cancel_requested = 1 WHERE id = ?", (run_id,))

    def is_cancel_requested(self, run_id: str) -> bool:
        """Return whether cancellation has been requested for ``run_id``."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
            return bool(row["cancel_requested"]) if row is not None else False

    def create_checkpoint(
        self,
        run_id: str,
        node_id: str,
        checkpoint_id: str,
        question: str,
        *,
        options: Sequence[str] | None = None,
        allow_freeform: bool = False,
        created_at: float | None = None,
    ) -> CheckpointState:
        """Insert or replace an open checkpoint row in ``checkpoints``."""
        now = time.time() if created_at is None else created_at
        options_list = list(options) if options is not None else None
        options_json = (
            json.dumps(options_list, ensure_ascii=False) if options_list is not None else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (
                  run_id, node_id, checkpoint_id, question, options_json,
                  allow_freeform, answer, created_at, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL)
                ON CONFLICT(run_id, node_id, checkpoint_id) DO UPDATE SET
                  question = excluded.question,
                  options_json = excluded.options_json,
                  allow_freeform = excluded.allow_freeform
                """,
                (
                    run_id,
                    node_id,
                    checkpoint_id,
                    question,
                    options_json,
                    1 if allow_freeform else 0,
                    now,
                ),
            )
        return CheckpointState(
            node_id=node_id,
            checkpoint_id=checkpoint_id,
            question=question,
            options=options_list,
            allow_freeform=allow_freeform,
            answer=None,
            created_at=now,
            answered_at=None,
        )

    def answer_checkpoint(
        self,
        run_id: str,
        node_id: str,
        checkpoint_id: str,
        answer: str,
        *,
        answered_at: float | None = None,
    ) -> bool:
        """Record an answer for an open checkpoint. First answer wins; returns True if applied."""
        now = time.time() if answered_at is None else answered_at
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE checkpoints
                SET answer = ?, answered_at = ?
                WHERE run_id = ? AND node_id = ? AND checkpoint_id = ? AND answer IS NULL
                """,
                (answer, now, run_id, node_id, checkpoint_id),
            )
            return cursor.rowcount == 1

    def get_checkpoint(
        self,
        run_id: str,
        node_id: str,
        checkpoint_id: str,
    ) -> CheckpointState | None:
        """Fetch a single checkpoint state."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT node_id, checkpoint_id, question, options_json, allow_freeform,
                       answer, created_at, answered_at
                FROM checkpoints
                WHERE run_id = ? AND node_id = ? AND checkpoint_id = ?
                """,
                (run_id, node_id, checkpoint_id),
            ).fetchone()
        if row is None:
            return None
        return _row_to_checkpoint(row)

    def create_stage_gate(
        self,
        run_id: str,
        stage_id: str,
        *,
        created_at: float | None = None,
    ) -> StageGateState:
        """Create a ``WAITING`` stage gate row."""
        now = time.time() if created_at is None else created_at
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO stage_gates (run_id, stage_id, status, created_at, decided_at)
                VALUES (?, ?, 'WAITING', ?, NULL)
                ON CONFLICT(run_id, stage_id) DO NOTHING
                """,
                (run_id, stage_id, now),
            )
        return StageGateState(
            stage_id=stage_id,
            status=StageGateStatus.WAITING,
            created_at=now,
            decided_at=None,
        )

    def approve_stage_gate(
        self,
        run_id: str,
        stage_id: str,
        *,
        decided_at: float | None = None,
    ) -> bool:
        """Approve a ``WAITING`` stage gate. Returns True if transitioned to ``APPROVED``."""
        now = time.time() if decided_at is None else decided_at
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE stage_gates
                SET status = 'APPROVED', decided_at = ?
                WHERE run_id = ? AND stage_id = ? AND status = 'WAITING'
                """,
                (now, run_id, stage_id),
            )
            return cursor.rowcount == 1

    def get_stage_gate(self, run_id: str, stage_id: str) -> StageGateState | None:
        """Fetch a single stage gate state."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT stage_id, status, created_at, decided_at
                FROM stage_gates
                WHERE run_id = ? AND stage_id = ?
                """,
                (run_id, stage_id),
            ).fetchone()
        if row is None:
            return None
        return StageGateState(
            stage_id=str(row["stage_id"]),
            status=StageGateStatus(str(row["status"])),
            created_at=float(row["created_at"]),
            decided_at=row["decided_at"],
        )

    def get_run_state(self, run_id: str) -> RunState | None:
        """Return the complete ``RunState`` for ``run_id``, or ``None`` if not found."""
        with self._connect() as conn:
            run_row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run_row is None:
                return None
            node_rows = conn.execute(
                "SELECT * FROM node_runs WHERE run_id = ? ORDER BY rowid", (run_id,)
            ).fetchall()
            cp_rows = conn.execute(
                "SELECT * FROM checkpoints WHERE run_id = ? ORDER BY created_at, checkpoint_id",
                (run_id,),
            ).fetchall()
            gate_rows = conn.execute(
                "SELECT * FROM stage_gates WHERE run_id = ? ORDER BY created_at, stage_id",
                (run_id,),
            ).fetchall()

        nodes = {
            str(r["node_id"]): NodeRunState(
                node_id=str(r["node_id"]),
                status=NodeStatus(str(r["status"])),
                cache_hit=bool(r["cache_hit"]),
                cache_key=r["cache_key"],
                attempt=int(r["attempt"]),
                exit_code=r["exit_code"],
                error=r["error"],
                started_at=r["started_at"],
                finished_at=r["finished_at"],
            )
            for r in node_rows
        }
        checkpoints = [_row_to_checkpoint(r) for r in cp_rows]
        stage_gates = {
            str(r["stage_id"]): StageGateState(
                stage_id=str(r["stage_id"]),
                status=StageGateStatus(str(r["status"])),
                created_at=float(r["created_at"]),
                decided_at=r["decided_at"],
            )
            for r in gate_rows
        }
        run_inputs = json.loads(str(run_row["run_inputs_json"] or "{}"))
        run_id_str = str(run_row["id"])
        workflow_snapshot = None
        snapshot_path = self.run_dir(run_id_str) / "workflow.snapshot.yaml"
        if snapshot_path.is_file():
            try:
                from plynx.workflow.models import load_workflow

                workflow_snapshot = load_workflow(snapshot_path)
            except Exception:
                workflow_snapshot = None
        return RunState(
            id=run_id_str,
            workflow_path=str(run_row["workflow_path"]),
            workflow_sha256=str(run_row["workflow_sha256"]),
            status=RunStatus(str(run_row["status"])),
            run_inputs=run_inputs if isinstance(run_inputs, dict) else {},
            owner_pid=run_row["owner_pid"],
            cancel_requested=bool(run_row["cancel_requested"]),
            pinned=bool(run_row["pinned"]),
            created_at=float(run_row["created_at"]),
            started_at=run_row["started_at"],
            finished_at=run_row["finished_at"],
            error=run_row["error"],
            nodes=nodes,
            checkpoints=checkpoints,
            stage_gates=stage_gates,
            workflow_snapshot=workflow_snapshot,
        )

    def list_runs(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> list[RunSummary]:
        """Return runs ordered newest first."""
        with self._connect() as conn:
            if cursor:
                cursor_row = conn.execute(
                    "SELECT created_at, id FROM runs WHERE id = ?",
                    (cursor,),
                ).fetchone()
                if cursor_row is not None:
                    c_created_at = float(cursor_row["created_at"])
                    c_id = str(cursor_row["id"])
                    rows = conn.execute(
                        """
                        SELECT * FROM runs
                        WHERE created_at < ? OR (created_at = ? AND id < ?)
                        ORDER BY created_at DESC, id DESC LIMIT ?
                        """,
                        (c_created_at, c_created_at, c_id, limit),
                    ).fetchall()
                else:
                    rows = []
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY created_at DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            RunSummary(
                id=str(r["id"]),
                workflow_path=str(r["workflow_path"]),
                workflow_sha256=str(r["workflow_sha256"]),
                status=RunStatus(str(r["status"])),
                owner_pid=r["owner_pid"],
                cancel_requested=bool(r["cancel_requested"]),
                pinned=bool(r["pinned"]),
                created_at=float(r["created_at"]),
                started_at=r["started_at"],
                finished_at=r["finished_at"],
                error=r["error"],
            )
            for r in rows
        ]

    def resolve_run_id(self, prefix: str) -> str:
        """Resolve a unique run ID prefix, or raise RunNotFoundError / AmbiguousRunIdError."""
        cleaned = prefix.strip()
        if not cleaned:
            raise RunNotFoundError("Run ID prefix must not be empty")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM runs WHERE substr(id, 1, length(?)) = ? ORDER BY id",
                (cleaned, cleaned),
            ).fetchall()
        matches = [str(r["id"]) for r in rows]
        if not matches:
            raise RunNotFoundError(f"No run matching {prefix!r}")
        if cleaned in matches:
            return cleaned
        if len(matches) > 1:
            raise AmbiguousRunIdError(cleaned, matches)
        return matches[0]

    def get_cache_entry(self, cache_key: str) -> str | None:
        """Look up result_json by cache_key. Updates last_accessed_at on hit."""
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM cache_index WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE cache_index SET last_accessed_at = ? WHERE cache_key = ?",
                (now, cache_key),
            )
            return str(row["result_json"])

    def put_cache_entry(self, cache_key: str, result_json: str) -> None:
        """Store or update a cached result_json for a cache_key."""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache_index (cache_key, result_json, created_at, last_accessed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                  result_json = excluded.result_json,
                  last_accessed_at = excluded.last_accessed_at
                """,
                (cache_key, result_json, now, now),
            )

    def delete_run(self, run_id: str) -> None:
        """Delete a run from SQLite (cascades to node_runs, checkpoints, stage_gates)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def delete_cache_entry(self, cache_key: str) -> None:
        """Delete a cache_index row by cache_key."""
        with self._connect() as conn:
            conn.execute("DELETE FROM cache_index WHERE cache_key = ?", (cache_key,))


def _row_to_checkpoint(row: sqlite3.Row) -> CheckpointState:
    raw_opts = row["options_json"]
    options = json.loads(str(raw_opts)) if raw_opts is not None else None
    return CheckpointState(
        node_id=str(row["node_id"]),
        checkpoint_id=str(row["checkpoint_id"]),
        question=str(row["question"]),
        options=options,
        allow_freeform=bool(row["allow_freeform"]),
        answer=row["answer"],
        created_at=float(row["created_at"]),
        answered_at=row["answered_at"],
    )
