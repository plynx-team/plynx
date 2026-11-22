"""Ops, health, upload, and garbage-collection routes."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile

from plynx.api_models import (
    CleanRequest,
    CleanResponse,
    HealthResponse,
    OpEntry,
    UploadResponse,
)
from plynx.cas import clean
from plynx.server.state import ServerStateDep, error_response

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return server health and version."""
    return HealthResponse()


@router.get("/ops", response_model=list[OpEntry])
async def get_ops(state: ServerStateDep) -> list[OpEntry]:
    """Return all registered operations."""
    if hasattr(state.registry, "refresh"):
        await asyncio.to_thread(state.registry.refresh)
    return await asyncio.to_thread(state.registry.list_ops)


@router.post("/uploads", response_model=UploadResponse, status_code=201)
async def upload_file_endpoint(
    file: UploadFile,
    state: ServerStateDep,
) -> Any:
    """Upload a multipart file into ``.plynx/uploads/``."""
    import plynx.server.app as app_mod

    max_upload_bytes = app_mod.MAX_UPLOAD_SIZE_BYTES
    chunk_size = app_mod.UPLOAD_CHUNK_SIZE

    raw_filename = file.filename or ""
    if (
        not raw_filename
        or "/" in raw_filename
        or "\\" in raw_filename
        or ".." in raw_filename
        or Path(raw_filename).name != raw_filename
    ):
        return error_response(
            400,
            "invalid_filename",
            "Uploaded filename cannot contain path separators or traversal characters",
        )

    uploads_dir = state.workspace_root / ".plynx" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    dest = (uploads_dir / raw_filename).resolve()
    try:
        dest.relative_to(uploads_dir.resolve())
    except ValueError:
        return error_response(
            400,
            "invalid_filename",
            "Uploaded file path must stay inside the uploads directory",
        )

    if dest.exists():
        stem = Path(raw_filename).stem
        suffix = Path(raw_filename).suffix
        counter = 1
        while dest.exists():
            dest = (uploads_dir / f"{stem}-{counter}{suffix}").resolve()
            counter += 1

    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(uploads_dir),
        prefix=f".{dest.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    bytes_written = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise ValueError(
                        f"File size exceeds maximum allowed limit of {max_upload_bytes} bytes"
                    )
                handle.write(chunk)
        os.replace(tmp_path, dest)
    except ValueError as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return error_response(413, "upload_too_large", str(exc))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    rel_path = dest.relative_to(state.workspace_root.resolve()).as_posix()
    return UploadResponse(path=rel_path)


@router.post("/clean", response_model=CleanResponse)
async def clean_endpoint(
    state: ServerStateDep,
    req: CleanRequest | None = None,
) -> Any:
    """Mark-and-sweep garbage collection of old unpinned runs and unreferenced blobs."""
    clean_req = req if req is not None else CleanRequest()
    try:
        res = await asyncio.to_thread(
            clean,
            state.workspace_root,
            days=clean_req.days,
            dry_run=clean_req.dry_run,
        )
    except Exception as exc:
        return error_response(500, "clean_failed", str(exc))

    return CleanResponse(
        deleted_runs=res.runs_deleted,
        deleted_blobs=res.blobs_deleted,
        reclaimed_bytes=res.bytes_reclaimed,
    )
