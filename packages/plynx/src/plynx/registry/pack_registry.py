"""Pack discovery and mtime-based registry caching (PROTOCOL.md sections 3, 4, 12).

Discovers wheel-shipped, built-in, and custom packs, and caches parsed operation
manifests in ``.plynx/registry_cache.json`` keyed by source file path and mtime.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from plynx.api_models import OpEntry
from plynx.config import load_workspace_config
from plynx.registry.extractor import extract_ops_from_file
from plynx.store.run_store import atomic_write_text

CACHE_SCHEMA_VERSION = 4


def find_workspace_root(start: Path | None = None) -> Path:
    """Return workspace root by scanning upward in priority order:

    1. Nearest ancestor containing ``.plynx`` or ``plynx.yaml``.
    2. Nearest ancestor containing ``.git``.
    3. Nearest ancestor containing ``pyproject.toml`` (excluding ``custom_packs``).
    4. ``start`` (or ``Path.cwd()``).
    """
    base = (start or Path.cwd()).resolve()
    if base.is_file():
        base = base.parent
    candidates = [base, *base.parents]

    # Priority 1: .plynx or plynx.yaml
    for candidate in candidates:
        if (candidate / ".plynx").exists() or (candidate / "plynx.yaml").is_file():
            return candidate

    # Priority 2: .git
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate

    # Priority 3: pyproject.toml (avoid stopping at custom_packs/<pack>/pyproject.toml)
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file():
            if candidate.parent.name == "custom_packs" or "custom_packs" in candidate.parts:
                continue
            return candidate

    # Priority 4: start (or cwd)
    return base


def discover_builtin_packs_dirs() -> list[Path]:
    """Return candidate directories containing built-in packs."""
    dirs: list[Path] = []
    # 1. Check inside installed plynx package (e.g. when distributed in a wheel)
    wheel_builtin = Path(__file__).resolve().parent.parent / "builtin_packs"
    if wheel_builtin.is_dir():
        dirs.append(wheel_builtin)

    # 2. Check repo ancestor directories (development mode)
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "builtin_packs"
        if candidate.is_dir() and candidate not in dirs:
            dirs.append(candidate)
    return dirs


def _normalize_dist_name(requirement: str) -> str:
    """Extract a PEP 503 normalized distribution name from a PEP 508 requirement string."""
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    if not match:
        return ""
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def is_direct_builtin_pack(pack_dir: Path) -> bool:
    """Return True if ``pack_dir`` is a stdlib-only built-in pack runnable via ``sys.executable``.

    Built-in packs that declare no third-party dependencies beyond ``plynx-sdk`` execute directly
    in the active ``plynx`` Python environment without ``uv sync`` or writes to ``site-packages``.
    """
    resolved = pack_dir.resolve()
    builtin_roots = {d.resolve() for d in discover_builtin_packs_dirs()}
    if resolved.parent not in builtin_roots:
        return False

    pyproject_path = resolved / "pyproject.toml"
    if not pyproject_path.is_file():
        return False

    try:
        parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False

    project = parsed.get("project")
    if not isinstance(project, Mapping):
        return False

    deps = project.get("dependencies", [])
    if not isinstance(deps, list):
        return False

    for dep in deps:
        if not isinstance(dep, str):
            return False
        dist_name = _normalize_dist_name(dep)
        if dist_name and dist_name != "plynx-sdk":
            return False

    return True


def _load_custom_packs_from_config(workspace_root: Path) -> list[Path]:
    """Read custom pack directories from ``<workspace_root>/plynx.yaml`` if present."""
    config = load_workspace_config(workspace_root)
    return [p for p in config.packs if p.is_dir()]


def discover_packs(
    workspace_root: Path,
    *,
    custom_pack_dirs: Sequence[Path] | None = None,
) -> dict[str, Path]:
    """Discover all packs in search order: wheel-shipped, built-in, and custom packs.

    Returns a mapping from pack name to pack root directory containing ``pyproject.toml``.
    Raises ``ValueError`` on duplicate pack name collisions across different directories.
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
            if pack_name in packs:
                if packs[pack_name].resolve() != resolved_root.resolve():
                    msg = (
                        f"Duplicate pack name {pack_name!r} found at '{resolved_root}' "
                        f"and '{packs[pack_name]}'"
                    )
                    raise ValueError(msg)
            else:
                packs[pack_name] = resolved_root
            continue

        # Otherwise inspect immediate subdirectories
        for sub in sorted(resolved_root.iterdir()):
            if sub.is_dir() and (sub / "pyproject.toml").is_file():
                pack_name = sub.name
                resolved_sub = sub.resolve()
                if pack_name in packs:
                    if packs[pack_name].resolve() != resolved_sub:
                        msg = (
                            f"Duplicate pack name {pack_name!r} found at '{resolved_sub}' "
                            f"and '{packs[pack_name]}'"
                        )
                        raise ValueError(msg)
                else:
                    packs[pack_name] = resolved_sub

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
                loaded = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and loaded.get("schema") == CACHE_SCHEMA_VERSION:
                    cache_data = loaded
            except Exception:
                cache_data = {}

        raw_files = cache_data.get("files", {})
        cached_files: dict[str, Any] = raw_files if isinstance(raw_files, dict) else {}
        cache_dirty = force or not cache_data

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

        # Attach workspace agent.models suggestions (if configured in plynx.yaml) to AgentOp model ports
        ws_cfg = load_workspace_config(self.workspace_root)
        if ws_cfg.agent_models:
            model_suggestions = list(ws_cfg.agent_models)
            for op_id, op_entry in list(self._ops.items()):
                if op_entry.agent_role is None:
                    continue
                updated_inputs = [
                    port.model_copy(update={"suggestions": model_suggestions})
                    if port.name == "model" and port.type == "str"
                    else port
                    for port in op_entry.inputs
                ]
                self._ops[op_id] = op_entry.model_copy(update={"inputs": updated_inputs})

        if cache_dirty:
            manifest = {
                "schema": CACHE_SCHEMA_VERSION,
                "files": cached_files,
            }
            atomic_write_text(self.cache_path, json.dumps(manifest, indent=2) + "\n")


__all__ = [
    "PackRegistry",
    "discover_builtin_packs_dirs",
    "discover_packs",
    "find_workspace_root",
    "is_direct_builtin_pack",
]
