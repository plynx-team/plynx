"""Tests for R0.2 and R0.3: lockfile isolation, packs, root discovery, and plynx init."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from plynx.cli import main as cli_main
from plynx.config import load_workspace_config
from plynx.registry import discover_packs, find_workspace_root


def _setup_custom_pack(
    pack_dir: Path,
    pack_name: str,
    sdk_dir: Path,
) -> None:
    src_dir = pack_dir / "src" / pack_name
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "greet.py").write_text(
        """from typing import TypedDict
from plynx_sdk import Op

class Greet(Op):
    \"\"\"Custom greet operation.\"\"\"
    TITLE = "Greet"

    class Outputs(TypedDict):
        msg: str

    def run(self, name: str = "world") -> Outputs:
        return {"msg": f"hello {name}"}
""",
        encoding="utf-8",
    )
    sdk_path_str = sdk_dir.as_posix()
    pyproject = f"""[project]
name = "{pack_name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_path_str}", editable = true }}

[build-system]
requires = ["uv_build>=0.9.0,<0.10"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "{pack_name}"
"""
    (pack_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")


def test_r02_unrelated_root_uv_lock_and_custom_pack_runs_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accept R0.2: repo has unrelated root uv.lock; custom pack in custom_packs runs cleanly."""
    root_dir = tmp_path / "user_repo"
    root_dir.mkdir()
    monkeypatch.chdir(root_dir)
    # Unrelated, completely bogus root uv.lock that would fail if parsed by uv --frozen
    (root_dir / "uv.lock").write_text("bogus lock file\n", encoding="utf-8")
    (root_dir / "pyproject.toml").write_text(
        '[project]\nname = "user-repo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    pack_dir = root_dir / "custom_packs" / "my_pack"
    extra_pack_dir = root_dir / "extra_packs" / "alt_pack"
    sdk_dir = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk"
    _setup_custom_pack(pack_dir, "my_pack", sdk_dir)
    _setup_custom_pack(extra_pack_dir, "alt_pack", sdk_dir)

    # Configure custom pack dirs via plynx.yaml packs entry (including a non-default directory)
    (root_dir / "plynx.yaml").write_text(
        "workflows: workflows\npacks:\n  - custom_packs\n  - extra_packs\n",
        encoding="utf-8",
    )

    # Create workflow using both custom_packs and extra_packs
    wf_dir = root_dir / "workflows"
    wf_dir.mkdir(parents=True)
    wf_file = wf_dir / "greet.yaml"
    wf_file.write_text(
        """version: 1
name: greet_flow
nodes:
  g:
    op: my_pack/greet:Greet
    inputs:
      name: "alice"
  g2:
    op: alt_pack/greet:Greet
    inputs:
      name: $g.msg
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    # 1. plynx validate must succeed
    val_res = runner.invoke(cli_main, ["validate", str(wf_file)])
    assert val_res.exit_code == 0, f"output={val_res.output}"

    # 2. plynx run must succeed without trying to read the unrelated root uv.lock
    run_res = runner.invoke(cli_main, ["run", str(wf_file), "--non-interactive"])
    assert run_res.exit_code == 0, f"output={run_res.output}"


def test_r02_duplicate_pack_names_rejected_with_clear_error(tmp_path: Path) -> None:
    """Duplicate pack name from two different directories raises ValueError."""
    sdk_dir = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk"
    dir1 = tmp_path / "packs_a" / "colliding_pack"
    dir2 = tmp_path / "packs_b" / "colliding_pack"
    _setup_custom_pack(dir1, "colliding_pack", sdk_dir)
    _setup_custom_pack(dir2, "colliding_pack", sdk_dir)

    with pytest.raises(ValueError, match="Duplicate pack name 'colliding_pack'"):
        discover_packs(tmp_path, custom_pack_dirs=[dir1, dir2])


def test_r03_find_workspace_root_priority_and_nested_pack(tmp_path: Path) -> None:
    """Accept R0.3: find_workspace_root priority order and ignoring nested pack pyproject.toml."""
    repo_root = tmp_path / "outer_repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / ".plynx").mkdir()

    pack_dir = repo_root / "custom_packs" / "my_pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pyproject.toml").write_text('[project]\nname="my_pack"\n', encoding="utf-8")

    # Scanning from inside custom_packs/my_pack resolves outer_repo
    resolved = find_workspace_root(pack_dir)
    assert resolved == repo_root

    # Even without .plynx, .git resolves outer_repo
    (repo_root / ".plynx").rmdir()
    resolved_git = find_workspace_root(pack_dir)
    assert resolved_git == repo_root

    # Without any markers, falls back to start directory
    bare_dir = tmp_path / "bare_workspace"
    bare_dir.mkdir()
    assert find_workspace_root(bare_dir) == bare_dir.resolve()


def test_r03_plynx_init_sets_up_working_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accept R0.3: running plynx init sets up workspace; ops inside pack resolves root."""
    repo = tmp_path / "test_init_repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".gitignore").write_text("*.pyc\n", encoding="utf-8")

    runner = CliRunner()
    init_res = runner.invoke(cli_main, ["init", str(repo)])
    assert init_res.exit_code == 0, init_res.output

    assert (repo / ".plynx").is_dir()
    assert (repo / "workflows").is_dir()
    assert (repo / "custom_packs").is_dir()
    assert (repo / "custom_packs" / ".gitkeep").is_file()
    assert (repo / "plynx.yaml").is_file()

    gi_text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert ".plynx/" in gi_text

    # Set up a pack inside custom_packs
    sdk_dir = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk"
    pack_dir = repo / "custom_packs" / "pack_init"
    _setup_custom_pack(pack_dir, "pack_init", sdk_dir)

    # Invoke plynx ops with cwd inside pack_dir
    monkeypatch.chdir(pack_dir)
    ops_res = runner.invoke(cli_main, ["ops", "--json"])
    assert ops_res.exit_code == 0, ops_res.output
    assert "pack_init/greet:Greet" in ops_res.output


def test_load_workspace_config_reads_defaults_and_custom(tmp_path: Path) -> None:
    """load_workspace_config handles default and customized plynx.yaml."""
    # Defaults on empty directory
    cfg_default = load_workspace_config(tmp_path)
    assert cfg_default.workflows == ["workflows"]
    assert cfg_default.packs == []
    assert cfg_default.db == ".plynx/plynx.db"
    assert cfg_default.concurrency is None

    # Custom settings
    (tmp_path / "plynx.yaml").write_text(
        """workflows:
  - flows
  - test_flows
packs:
  - custom_packs
  - my_plugins
db: .plynx/custom.db
concurrency: 8
env_passthrough:
  - API_KEY
  - AWS_*
cache:
  max_size: 5GB
""",
        encoding="utf-8",
    )
    cfg_custom = load_workspace_config(tmp_path)
    assert cfg_custom.workflows == ["flows", "test_flows"]
    assert len(cfg_custom.packs) == 2
    assert cfg_custom.db == ".plynx/custom.db"
    assert cfg_custom.concurrency == 8
    assert cfg_custom.env_passthrough == ["API_KEY", "AWS_*"]
    assert cfg_custom.cache_max_size == 5 * (1024**3)
