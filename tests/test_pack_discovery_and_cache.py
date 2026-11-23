"""Tests for pack discovery and mtime-based registry caching (Task 2.4)."""

from __future__ import annotations

import os
from pathlib import Path

from plynx.registry import OpRegistry, PackRegistry, discover_packs

ROOT = Path(__file__).resolve().parent.parent


def _create_mock_pack(
    pack_dir: Path,
    pack_name: str,
    *,
    ops: dict[str, str],
) -> None:
    """Create a mock pack directory with pyproject.toml and Python ops."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{pack_name}"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    src_dir = pack_dir / "src" / pack_name
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")

    for mod_name, code in ops.items():
        (src_dir / f"{mod_name}.py").write_text(code, encoding="utf-8")


OP_A_CODE = '''
from plynx_sdk import Op

class OpA(Op):
    """Operation A docstring."""
    TITLE = "Operation A"

    def run(self, x: str) -> str:
        return x
'''

OP_B_CODE = '''
from plynx_sdk import Op

class OpB(Op):
    """Operation B docstring."""
    TITLE = "Operation B"

    def run(self, count: int = 1) -> int:
        return count + 1
'''


def test_discover_builtin_packs_finds_standard_io() -> None:
    """Pack discovery locates standard_io in the repo built-in packs."""
    packs = discover_packs(ROOT)
    assert "standard_io" in packs
    assert (packs["standard_io"] / "pyproject.toml").is_file()


def test_registry_satisfies_op_registry_protocol(tmp_path: Path) -> None:
    """PackRegistry implements the OpRegistry protocol."""
    reg = PackRegistry(workspace_root=tmp_path)
    assert isinstance(reg, OpRegistry)
    assert issubclass(PackRegistry, OpRegistry)


def test_cold_start_builds_cache_file(tmp_path: Path) -> None:
    """Initial registry scan builds and atomically writes .plynx/registry_cache.json."""
    pack_dir = tmp_path / "custom_packs" / "test_pack"
    _create_mock_pack(pack_dir, "test_pack", ops={"op_a": OP_A_CODE})

    cache_file = tmp_path / ".plynx" / "registry_cache.json"
    assert not cache_file.exists()

    reg = PackRegistry(workspace_root=tmp_path)
    assert cache_file.is_file()
    assert reg.reparsed_count >= 1
    assert any("op_a.py" in f for f in reg.reparsed_files)

    op_entry = reg.get("test_pack/op_a:OpA")
    assert op_entry is not None
    assert op_entry.title == "Operation A"
    assert op_entry.valid is True


def test_touching_one_file_reparses_only_that_file(tmp_path: Path) -> None:
    """Touching one file re-parses only that file (Task 2.4 Accept)."""
    pack_dir = tmp_path / "custom_packs" / "test_pack"
    _create_mock_pack(
        pack_dir,
        "test_pack",
        ops={"op_a": OP_A_CODE, "op_b": OP_B_CODE},
    )

    reg = PackRegistry(workspace_root=tmp_path)
    initial_reparsed = reg.reparsed_files
    assert any("op_a.py" in f for f in initial_reparsed)
    assert any("op_b.py" in f for f in initial_reparsed)

    # Second refresh with no changes: 0 files re-parsed
    reg.refresh()
    assert reg.reparsed_count == 0
    assert reg.reparsed_files == []

    # Touch only op_a.py
    op_a_file = pack_dir / "src" / "test_pack" / "op_a.py"
    current_mtime = op_a_file.stat().st_mtime
    future_mtime = current_mtime + 10.0
    os.utime(op_a_file, (future_mtime, future_mtime))

    reg.refresh()
    # Exactly one file was re-parsed: op_a.py
    assert reg.reparsed_count == 1
    assert any("op_a.py" in f for f in reg.reparsed_files)
    assert not any("op_b.py" in f for f in reg.reparsed_files)


def test_deleting_cache_rebuilds_it(tmp_path: Path) -> None:
    """Deleting the cache rebuilds it (Task 2.4 Accept)."""
    pack_dir = tmp_path / "custom_packs" / "test_pack"
    _create_mock_pack(
        pack_dir,
        "test_pack",
        ops={"op_a": OP_A_CODE, "op_b": OP_B_CODE},
    )

    cache_file = tmp_path / ".plynx" / "registry_cache.json"
    reg = PackRegistry(workspace_root=tmp_path)
    assert cache_file.is_file()

    # Delete cache file
    cache_file.unlink()
    assert not cache_file.exists()

    # Refresh must rebuild the cache and re-parse files
    reg.refresh()
    assert cache_file.is_file()
    assert any("op_a.py" in f for f in reg.reparsed_files)
    assert any("op_b.py" in f for f in reg.reparsed_files)


def test_pruning_deleted_file_from_cache(tmp_path: Path) -> None:
    """Deleting a source file prunes its entry from the registry cache."""
    pack_dir = tmp_path / "custom_packs" / "test_pack"
    _create_mock_pack(
        pack_dir,
        "test_pack",
        ops={"op_a": OP_A_CODE, "op_b": OP_B_CODE},
    )

    reg = PackRegistry(workspace_root=tmp_path)
    assert reg.get("test_pack/op_b:OpB") is not None

    # Remove op_b.py
    op_b_file = pack_dir / "src" / "test_pack" / "op_b.py"
    op_b_file.unlink()

    reg.refresh()
    assert reg.get("test_pack/op_b:OpB") is None
    assert reg.get("test_pack/op_a:OpA") is not None


def test_custom_packs_via_plynx_yaml(tmp_path: Path) -> None:
    """Custom packs directory configured in plynx.yaml is discovered."""
    special_dir = tmp_path / "my_plugins"
    pack_dir = special_dir / "plugin_pack"
    _create_mock_pack(pack_dir, "plugin_pack", ops={"op_plugin": OP_A_CODE})

    (tmp_path / "plynx.yaml").write_text(
        "packs:\n  - my_plugins\n",
        encoding="utf-8",
    )

    reg = PackRegistry(workspace_root=tmp_path)
    assert "plugin_pack" in reg.discovered_packs
    assert reg.get("plugin_pack/op_plugin:OpA") is not None


def test_corrupted_cache_recovers_gracefully(tmp_path: Path) -> None:
    """A corrupted registry_cache.json is gracefully recovered and rewritten."""
    pack_dir = tmp_path / "custom_packs" / "test_pack"
    _create_mock_pack(pack_dir, "test_pack", ops={"op_a": OP_A_CODE})

    cache_file = tmp_path / ".plynx" / "registry_cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{corrupt-json", encoding="utf-8")

    reg = PackRegistry(workspace_root=tmp_path)
    assert reg.get("test_pack/op_a:OpA") is not None
    assert cache_file.is_file()
    # File is now valid JSON
    assert "schema" in cache_file.read_text(encoding="utf-8")
