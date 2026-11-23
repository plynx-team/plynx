"""Hatchling build hook to bundle ``builtin_packs/standard_io`` declaratively."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import (  # type: ignore[import-not-found]
    BuildHookInterface,
)

_IGNORED_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
_IGNORED_SUFFIXES = (".pyc", ".pyo")


class CustomBuildHook(BuildHookInterface):  # type: ignore[misc]
    """Include ``builtin_packs/standard_io`` in sdist and wheel without manual staging."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Populate ``force_include`` with clean ``standard_io`` files when building dists."""
        if version == "editable":
            return

        root = Path(self.root)
        force_include: dict[str, str] = build_data.setdefault("force_include", {})

        # Bundle docs/AGENT_GUIDE.md so `plynx agent-guide` works in wheel installs.
        in_pkg_guide = root / "src" / "plynx" / "AGENT_GUIDE.md"
        repo_guide = root.parent.parent / "docs" / "AGENT_GUIDE.md"
        if not in_pkg_guide.is_file() and repo_guide.is_file():
            guide_dest = (
                "src/plynx/AGENT_GUIDE.md"
                if self.target_name == "sdist"
                else "plynx/AGENT_GUIDE.md"
            )
            force_include[str(repo_guide)] = guide_dest

        # When building a wheel from an unpacked sdist, standard_io is already inside src/plynx.
        in_pkg = root / "src" / "plynx" / "builtin_packs" / "standard_io"
        if in_pkg.is_dir():
            return

        repo_pack = root.parent.parent / "builtin_packs" / "standard_io"
        if not repo_pack.is_dir():
            return

        dest_prefix = (
            "src/plynx/builtin_packs/standard_io"
            if self.target_name == "sdist"
            else "plynx/builtin_packs/standard_io"
        )
        for path in sorted(repo_pack.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_pack)
            if any(part in _IGNORED_DIR_NAMES for part in rel.parts):
                continue
            if path.suffix in _IGNORED_SUFFIXES or path.name == "uv.lock":
                continue
            force_include[str(path)] = f"{dest_prefix}/{rel.as_posix()}"
