"""Route modules for the PLynx FastAPI server."""

from plynx.server.routes.ops import router as ops_router
from plynx.server.routes.runs import router as runs_router
from plynx.server.routes.workflows import router as workflows_router

__all__ = [
    "ops_router",
    "runs_router",
    "workflows_router",
]
