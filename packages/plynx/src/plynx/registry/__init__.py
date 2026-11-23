"""Operation registry protocol and pack discovery."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from plynx.api_models import OpEntry
from plynx.registry.extractor import extract_ops_from_file, extract_ops_from_source
from plynx.registry.pack_registry import (
    PackRegistry,
    discover_packs,
    find_workspace_root,
    is_direct_builtin_pack,
)


@runtime_checkable
class OpRegistry(Protocol):
    """Protocol for looking up operation definitions."""

    def get(self, op_id: str) -> OpEntry | None:
        """Return the ``OpEntry`` for ``op_id`` (``<pack>/<module>:<Name>``), or ``None``."""
        ...

    def list_ops(self) -> list[OpEntry]:
        """Return all registered ``OpEntry`` items in deterministic order."""
        ...


__all__ = [
    "OpRegistry",
    "PackRegistry",
    "discover_packs",
    "extract_ops_from_file",
    "extract_ops_from_source",
    "find_workspace_root",
    "is_direct_builtin_pack",
]
