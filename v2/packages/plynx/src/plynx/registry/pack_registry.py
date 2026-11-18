"""Pack discovery and mtime-based registry caching (PROTOCOL.md sections 3, 4, 12).

Discovers wheel-shipped, built-in, and custom packs, and caches parsed operation
manifests in ``.plynx/registry_cache.json`` keyed by source file path and mtime.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from plynx.api_models import OpEntry
from plynx.registry.extractor import extract_ops_from_file
from plynx.store.run_store import atomic_write_text


def find_workspace_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor containing ``.plynx/`` or ``pyproject.toml``, or ``start``."""
    base = (start or Path.cwd()).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".plynx").is_dir() or (candidate / "pyproject.toml").is_file():
            return candidate
    return base


def discover_builtin_packs_dirs() -> list[Path]:
    """Return candidate directories containing built-in packs."""
    dirs: list[Path] = []
    # 1. Check workspace repo ancestor directories (development mode)
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / "pyproject.toml").is_file() and ancestor.name != "plynx":
            candidate = ancestor / "builtin_packs"
            if candidate.is_dir() and candidate not in dirs:
                dirs.append(candidate)

    # 2. Check inside installed plynx package (e.g. when distributed in a wheel)
    wheel_builtin = Path(__file__).resolve().parent.parent / "builtin_packs"
    if wheel_builtin.is_dir() and wheel_builtin not in dirs:
        dirs.append(wheel_builtin)

    # 3. Check any other repo ancestor directories
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "builtin_packs"
        if candidate.is_dir() and candidate not in dirs:
            dirs.append(candidate)
    return dirs


def _load_custom_packs_from_config(workspace_root: Path) -> list[Path]:
    """Read custom pack directories from ``<workspace_root>/plynx.yaml`` if present."""
    cfg_path = workspace_root / "plynx.yaml"
    if not cfg_path.is_file():
        return []
    yaml = YAML(typ="safe")
    try:
        parsed = yaml.load(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(parsed, Mapping):
        return []
    raw_packs = parsed.get("packs")
    if not isinstance(raw_packs, list):
        return []
    result: list[Path] = []
    for item in raw_packs:
        if isinstance(item, str):
            p = Path(item)
            resolved = p.resolve() if p.is_absolute() else (workspace_root / p).resolve()
            if resolved.is_dir():
                result.append(resolved)
    return result


def discover_packs(
    workspace_root: Path,
    *,
    custom_pack_dirs: Sequence[Path] | None = None,
) -> dict[str, Path]:
    """Discover all packs in search order: wheel-shipped, built-in, and custom packs.

    Returns a mapping from pack name to pack root directory containing ``pyproject.toml``.
    """
    search_roots: list[Path] = []

    # 1. Built-in / wheel-shipped packs
    search_roots.extend(discover_builtin_packs_dirs())
    ws_builtin = workspace_root / "builtin_packs"
    if ws_builtin.is_dir() and ws_builtin not in search_roots:
        search_roots.append(ws_builtin)

    # 2. Workspace custom packs
    if custom_pack_dirs is not None:
        search_roots.extend(custom_pack_dirs)
    else:
        search_roots.extend(_load_custom_packs_from_config(workspace_root))
        ws_custom = workspace_root / "custom_packs"
        if ws_custom.is_dir() and ws_custom not in search_roots:
            search_roots.append(ws_custom)

    packs: dict[str, Path] = {}

    for root in search_roots:
        resolved_root = root.resolve()
        if not resolved_root.is_dir():
            continue

        # If the root itself is a pack
        if (resolved_root / "pyproject.toml").is_file():
            pack_name = resolved_root.name
            if pack_name not in packs:
                packs[pack_name] = resolved_root
            continue

        # Otherwise inspect immediate subdirectories
        for sub in sorted(resolved_root.iterdir()):
            if sub.is_dir() and (sub / "pyproject.toml").is_file():
                pack_name = sub.name
                if pack_name not in packs:
                    packs[pack_name] = sub.resolve()

    return packs


def _find_pack_source_dir(pack_dir: Path, pack_name: str) -> Path:
    """Find the source root directory for a pack (``src/<pack>`` or ``<pack>``)."""
    if (pack_dir / "src" / pack_name).is_dir():
        return pack_dir / "src" / pack_name
    if (pack_dir / pack_name).is_dir():
        return pack_dir / pack_name
    if (pack_dir / "src").is_dir():
        return pack_dir / "src"
    return pack_dir


class PackRegistry:
    """Pack-discovering and mtime-cached PLynx operation registry."""

    def __init__(
        self,
        workspace_root: Path | None = None,
        pack_dirs: Sequence[Path] | None = None,
        cache_path: Path | None = None,
    ) -> None:
        self.workspace_root = (workspace_root or find_workspace_root()).resolve()
        self.pack_dirs = [p.resolve() for p in pack_dirs] if pack_dirs is not None else None
        self.cache_path = (
            cache_path.resolve()
            if cache_path is not None
            else self.workspace_root / ".plynx" / "registry_cache.json"
        )
        self._ops: dict[str, OpEntry] = {}
        self._reparsed_files: list[str] = []
        self._discovered_packs: dict[str, Path] = {}
        self.refresh()

    @property
    def reparsed_files(self) -> list[str]:
        """Return the list of source files parsed or re-parsed in the last refresh."""
        return list(self._reparsed_files)

    @property
    def reparsed_count(self) -> int:
        """Return the number of files parsed or re-parsed in the last refresh."""
        return len(self._reparsed_files)

    @property
    def discovered_packs(self) -> dict[str, Path]:
        """Return the mapping of discovered pack names to their root directories."""
        return dict(self._discovered_packs)

    def get(self, op_id: str) -> OpEntry | None:
        """Return the ``OpEntry`` for ``op_id`` (``<pack>/<module>:<Name>``), or ``None``."""
        return self._ops.get(op_id)

    def list_ops(self) -> list[OpEntry]:
        """Return all registered ``OpEntry`` items in deterministic sorted order."""
        return [self._ops[key] for key in sorted(self._ops.keys())]

    def refresh(self, force: bool = False) -> None:
        """Scan packs, consult ``registry_cache.json``, and parse modified files."""
        self._reparsed_files.clear()
        self._ops.clear()

        cache_data: dict[str, Any] = {}
        if not force and self.cache_path.is_file():
            try:
                cache_data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                cache_data = {}

        raw_files = cache_data.get("files", cache_data)
        cached_files: dict[str, Any] = raw_files if isinstance(raw_files, dict) else {}
        cache_dirty = force or not self.cache_path.is_file()

        self._discovered_packs = discover_packs(
            self.workspace_root,
            custom_pack_dirs=self.pack_dirs,
        )

        scanned_source_paths: set[str] = set()

        for pack_name, pack_dir in self._discovered_packs.items():
            src_dir = _find_pack_source_dir(pack_dir, pack_name)
            for py_path in sorted(src_dir.rglob("*.py")):
                if py_path.name.startswith((".", "#")) or "__pycache__" in py_path.parts:
                    continue

                rel_to_src = py_path.relative_to(src_dir)
                module_parts = list(rel_to_src.with_suffix("").parts)
                if module_parts == ["__init__"]:
                    module_name = ""
                elif module_parts and module_parts[-1] == "__init__":
                    module_parts.pop()
                    module_name = ".".join(module_parts)
                else:
                    module_name = ".".join(module_parts)

                try:
                    rel_source = str(py_path.resolve().relative_to(self.workspace_root)).replace(
                        "\\", "/"
                    )
                except ValueError:
                    rel_source = str(py_path.resolve()).replace("\\", "/")

                scanned_source_paths.add(rel_source)
                current_mtime = py_path.stat().st_mtime

                cached_entry = cached_files.get(rel_source)
                use_cache = False
                if (
                    not force
                    and cached_entry is not None
                    and isinstance(cached_entry, dict)
                    and "mtime" in cached_entry
                    and abs(cached_entry["mtime"] - current_mtime) < 1e-3
                ):
                    try:
                        ops = [
                            OpEntry.model_validate(op_data)
                            for op_data in cached_entry.get("ops", [])
                        ]
                        use_cache = True
                    except Exception:
                        use_cache = False

                if use_cache:
                    for op in ops:
                        self._ops[op.id] = op
                else:
                    self._reparsed_files.append(rel_source)
                    ops = extract_ops_from_file(
                        py_path,
                        pack=pack_name,
                        module=module_name,
                        source_path=rel_source,
                        workspace_root=self.workspace_root,
                    )
                    for op in ops:
                        self._ops[op.id] = op
                    cached_files[rel_source] = {
                        "mtime": current_mtime,
                        "ops": [op.model_dump() for op in ops],
                    }
                    cache_dirty = True

        # Prune dead files from cache
        for cached_rel in list(cached_files.keys()):
            if cached_rel not in scanned_source_paths and (
                not (self.workspace_root / cached_rel).is_file() and not Path(cached_rel).is_file()
            ):
                del cached_files[cached_rel]
                cache_dirty = True

        if cache_dirty:
            manifest = {
                "schema": 1,
                "files": cached_files,
            }
            atomic_write_text(self.cache_path, json.dumps(manifest, indent=2) + "\n")


Registry = PackRegistry

__all__ = [
    "PackRegistry",
    "Registry",
    "discover_builtin_packs_dirs",
    "discover_packs",
    "find_workspace_root",
]
