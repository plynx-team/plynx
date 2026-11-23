"""FastAPI application factory and static UI mounting (PROTOCOL.md sections 9 & 10)."""

from __future__ import annotations

import ipaddress
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from plynx import __version__
from plynx.engine import Executor, create_executor
from plynx.registry import OpRegistry, PackRegistry, find_workspace_root
from plynx.server.routes import ops_router, runs_router, workflows_router
from plynx.server.state import ServerState
from plynx.store import RunStore

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MiB
UPLOAD_CHUNK_SIZE: int = 64 * 1024  # 64 KiB

DEV_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class NonLoopbackHostError(ValueError):
    """Raised when an attempt is made to bind or configure a non-loopback host."""


def is_loopback_host(host: str) -> bool:
    """Return True if host resolves to a loopback address or loopback hostname."""
    h = host.strip().lower()
    if h in {"localhost", "127.0.0.1", "::1", "ip6-localhost", "ip6-loopback"}:
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_loopback
    except ValueError:
        return False


def validate_host(host: str) -> str:
    """Validate that host is a loopback interface, raising NonLoopbackHostError otherwise."""
    if not is_loopback_host(host):
        raise NonLoopbackHostError(
            f"Binding to non-loopback host {host!r} is refused. "
            "PLynx local server only binds to loopback interfaces (e.g. 127.0.0.1, localhost, ::1)."
        )
    return host


def create_app(
    workspace_root: Path | None = None,
    *,
    executor_factory: Callable[[Path | None], Executor] = create_executor,
    registry: OpRegistry | None = None,
    static_dir: Path | None = None,
    dev_mode: bool = True,
    allowed_origins: list[str] | None = None,
    host: str | None = None,
) -> FastAPI:
    """Create and configure the PLynx FastAPI application."""
    if host is not None:
        validate_host(host)
    ws_root = (workspace_root or find_workspace_root()).resolve()
    ui_static_dir = (static_dir or DEFAULT_STATIC_DIR).resolve()
    store = RunStore(ws_root)
    store.reconcile_dead_owners()
    op_registry: OpRegistry = PackRegistry(ws_root) if registry is None else registry

    state = ServerState(
        workspace_root=ws_root,
        store=store,
        registry=op_registry,
        executor_factory=executor_factory,
    )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await state.shutdown_active_runs()

    app = FastAPI(title="PLynx", version=__version__, lifespan=_lifespan)

    origins = allowed_origins if allowed_origins is not None else (DEV_ORIGINS if dev_mode else [])
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.state.server = state
    app.state.workspace_root = ws_root
    app.state.store = store
    app.state.registry = op_registry
    app.state.background_tasks = state.background_tasks

    api_router = APIRouter()
    api_router.include_router(ops_router)
    api_router.include_router(workflows_router)
    api_router.include_router(runs_router)

    app.include_router(api_router)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", response_model=None)
    async def serve_index() -> Any:
        """Serve the built UI index.html at ``/``."""
        index_file = ui_static_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file, media_type="text/html")
        return HTMLResponse(
            content="<!doctype html><html><body><h1>PLynx UI not built</h1></body></html>",
            status_code=404,
        )

    @app.get("/logo.png", response_model=None)
    async def serve_logo() -> Any:
        """Serve the UI header logo at ``/logo.png``."""
        logo_file = ui_static_dir / "logo.png"
        if logo_file.is_file():
            return FileResponse(logo_file, media_type="image/png")
        return Response(status_code=404)

    @app.get("/favicon.png", response_model=None)
    async def serve_favicon() -> Any:
        """Serve the UI favicon at ``/favicon.png``."""
        favicon_file = ui_static_dir / "favicon.png"
        if favicon_file.is_file():
            return FileResponse(favicon_file, media_type="image/png")
        return Response(status_code=404)

    assets_dir = ui_static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    return app
