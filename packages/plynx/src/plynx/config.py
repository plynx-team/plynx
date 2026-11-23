"""Workspace configuration loader for ``plynx.yaml`` (PROTOCOL.md section 12)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]*)\s*$")

_SIZE_UNITS: dict[str, int] = {
    "": 1,
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "k": 1024,
    "kb": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
    "tib": 1024**4,
}


def parse_size_bytes(val: str | int | float) -> int:
    """Parse a size representation into integer bytes.

    Supports integer bytes or strings with unit suffixes (e.g. '10GB', '500MB', '100KB').
    """
    if isinstance(val, (int, float)):
        if val < 0:
            raise ValueError(f"Size must be non-negative, got {val}")
        return int(val)

    match = _SIZE_RE.match(val)
    if not match:
        raise ValueError(f"Invalid size string: {val!r}")

    number_str, unit_str = match.groups()
    unit = unit_str.lower()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit {unit_str!r} in {val!r}")

    bytes_per_unit = _SIZE_UNITS[unit]
    number = float(number_str)
    return int(number * bytes_per_unit)


@dataclass(frozen=True)
class WorkspaceConfig:
    """Parsed workspace settings from ``plynx.yaml``."""

    workspace_root: Path
    workflows: list[str] = field(default_factory=lambda: ["workflows"])
    packs: list[Path] = field(default_factory=list)
    db: str = ".plynx/plynx.db"
    concurrency: int | None = None
    env_passthrough: list[str] | None = None
    cache_max_size: int | None = None


def load_workspace_config(workspace_root: Path) -> WorkspaceConfig:
    """Load configuration from ``<workspace_root>/plynx.yaml`` if present."""
    root = workspace_root.resolve()
    cfg_path = root / "plynx.yaml"
    if not cfg_path.is_file():
        return WorkspaceConfig(workspace_root=root)

    yaml = YAML(typ="safe")
    try:
        parsed = yaml.load(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return WorkspaceConfig(workspace_root=root)

    if not isinstance(parsed, Mapping):
        return WorkspaceConfig(workspace_root=root)

    # 1. workflows
    workflows: list[str] = ["workflows"]
    raw_workflows = parsed.get("workflows")
    if isinstance(raw_workflows, str):
        workflows = [raw_workflows]
    elif isinstance(raw_workflows, list):
        workflows = [str(x) for x in raw_workflows if isinstance(x, (str, int))]

    # 2. packs
    packs: list[Path] = []
    raw_packs = parsed.get("packs")
    if isinstance(raw_packs, list):
        for item in raw_packs:
            if isinstance(item, str):
                p = Path(item)
                resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
                if resolved not in packs:
                    packs.append(resolved)

    # 3. db
    raw_db = parsed.get("db")
    db_path = str(raw_db) if isinstance(raw_db, str) else ".plynx/plynx.db"

    # 4. concurrency
    raw_conc = parsed.get("concurrency")
    concurrency = int(raw_conc) if isinstance(raw_conc, int) and raw_conc > 0 else None

    # 5. env_passthrough
    raw_passthrough = parsed.get("env_passthrough")
    env_passthrough: list[str] | None = None
    if isinstance(raw_passthrough, list):
        env_passthrough = [str(item) for item in raw_passthrough if isinstance(item, str)]

    # 6. cache max_size
    cache_max_size: int | None = None
    raw_cache = parsed.get("cache")
    if isinstance(raw_cache, Mapping):
        max_size_val = raw_cache.get("max_size")
        if max_size_val is not None:
            try:
                cache_max_size = parse_size_bytes(max_size_val)
            except ValueError:
                cache_max_size = None
    elif isinstance(raw_cache, (str, int)):
        try:
            cache_max_size = parse_size_bytes(raw_cache)
        except ValueError:
            cache_max_size = None

    return WorkspaceConfig(
        workspace_root=root,
        workflows=workflows,
        packs=packs,
        db=db_path,
        concurrency=concurrency,
        env_passthrough=env_passthrough,
        cache_max_size=cache_max_size,
    )


__all__ = [
    "WorkspaceConfig",
    "load_workspace_config",
    "parse_size_bytes",
]
