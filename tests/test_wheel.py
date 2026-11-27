"""Tests for wheel packaging, declarative bundling, and isolated execution (R0.1 / 7.1)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT / "scripts" / "build.py"


def _venv_bin(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def _snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    """Snapshot relative paths -> (size_bytes, mtime_ns) under ``root``."""
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        st = path.lstat()
        rel = path.relative_to(root).as_posix()
        snapshot[rel] = (st.st_size if path.is_file() else -1, st.st_mtime_ns)
    return snapshot


def _set_readonly_tree(root: Path) -> list[tuple[Path, int]]:
    """Mark files and directories under ``root`` read-only; return original modes for restore."""
    saved: list[tuple[Path, int]] = []
    # Files first, then directories bottom-up so traversal works while setting modes.
    all_paths = sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    all_paths.append(root)
    for path in all_paths:
        mode = stat.S_IMODE(path.lstat().st_mode)
        saved.append((path, mode))
        if path.is_dir() or path.is_file():
            path.chmod(mode & ~0o222)
    return saved


def _restore_modes(saved: list[tuple[Path, int]]) -> None:
    """Restore original modes top-down so directories become writable before children."""
    for path, mode in reversed(saved):
        if path.exists():
            path.chmod(mode)


def _clean_subprocess_env() -> dict[str, str]:
    """Return host env without repo-pointing Python path overrides."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    return env


def test_declarative_uv_build_bundles_static_and_standard_io_without_staging(
    tmp_path: Path,
) -> None:
    """Direct ``uv build --package plynx`` includes static/, standard_io, and pinned plynx-sdk."""
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        pytest.skip("uv is required for wheel build test")

    out_dir = tmp_path / "dist"
    res = subprocess.run(
        [uv_bin, "build", "--package", "plynx", "--out-dir", str(out_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"

    plynx_wheels = list(out_dir.glob("plynx-*.whl"))
    assert len(plynx_wheels) == 1, f"Expected 1 plynx wheel, found {plynx_wheels}"

    with zipfile.ZipFile(plynx_wheels[0]) as whl:
        names = set(whl.namelist())
        metadata_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        metadata_text = whl.read(metadata_name).decode("utf-8")

    assert "plynx/static/index.html" in names
    assert any(n.startswith("plynx/static/assets/") for n in names)
    assert "plynx/AGENT_GUIDE.md" in names
    assert "plynx/skills/plynx-create-workflow/SKILL.md" in names
    assert "plynx/builtin_packs/standard_io/pyproject.toml" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/__init__.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/agent.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/demo.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/interactive.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/text.py" in names
    assert not any(n.endswith("uv.lock") for n in names), "Wheel must not bundle uv.lock files"
    assert "Requires-Dist: plynx-sdk<3.0.0,>=2.0.0" in metadata_text or (
        "Requires-Dist: plynx-sdk>=2.0.0,<3.0.0" in metadata_text
    ), metadata_text


def test_build_script_creates_wheels_with_static_and_builtin_packs(tmp_path: Path) -> None:
    """scripts/build.py builds plynx-sdk and plynx wheels containing static/ and standard_io."""
    out_dir = tmp_path / "dist"
    cmd = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--skip-ui",
        "--out-dir",
        str(out_dir),
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"

    sdk_wheels = list(out_dir.glob("plynx_sdk-*.whl"))
    plynx_wheels = list(out_dir.glob("plynx-*.whl"))
    assert len(sdk_wheels) == 1, f"Expected 1 sdk wheel, found {sdk_wheels}"
    assert len(plynx_wheels) == 1, f"Expected 1 plynx wheel, found {plynx_wheels}"

    with zipfile.ZipFile(plynx_wheels[0]) as whl:
        names = set(whl.namelist())

    assert "plynx/static/index.html" in names
    assert any(n.startswith("plynx/static/assets/") for n in names)
    assert "plynx/AGENT_GUIDE.md" in names
    assert "plynx/skills/plynx-create-workflow/SKILL.md" in names
    assert "plynx/builtin_packs/standard_io/pyproject.toml" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/__init__.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/agent.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/demo.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/interactive.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/text.py" in names
    assert not any(n.endswith("uv.lock") for n in names)


def test_installed_wheel_validates_and_runs_standard_io_workflow_isolated(
    tmp_path: Path,
) -> None:
    """Accept R0.1: installed wheel runs standard_io outside repo with no site-packages writes."""
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        pytest.skip("uv is required for isolated wheel execution test")

    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--skip-ui", "--out-dir", str(dist_dir)],
        cwd=ROOT,
        check=True,
    )
    sdk_whl = next(dist_dir.glob("plynx_sdk-*.whl"))
    plynx_whl = next(dist_dir.glob("plynx-*.whl"))

    venv_dir = tmp_path / "isolated_venv"
    subprocess.run(
        [uv_bin, "venv", "--python", sys.executable, str(venv_dir)],
        cwd=tmp_path,
        check=True,
    )
    venv_python = _venv_bin(venv_dir, "python")
    venv_plynx = _venv_bin(venv_dir, "plynx")

    subprocess.run(
        [
            uv_bin,
            "pip",
            "install",
            "--python",
            str(venv_python),
            "--find-links",
            str(dist_dir),
            str(sdk_whl),
            str(plynx_whl),
        ],
        cwd=tmp_path,
        check=True,
    )

    site_packages_str = subprocess.run(
        [str(venv_python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    site_packages = Path(site_packages_str).resolve()
    builtin_packs_in_sp = site_packages / "plynx" / "builtin_packs"
    assert (builtin_packs_in_sp / "standard_io" / "pyproject.toml").is_file()

    # Fresh user workspace completely outside the source tree
    workspace = tmp_path / "user_workspace"
    clean_env = _clean_subprocess_env()

    init_res = subprocess.run(
        [str(venv_plynx), "init", str(workspace)],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_res.returncode == 0, f"stdout={init_res.stdout}\nstderr={init_res.stderr}"
    assert (workspace / ".agents" / "skills" / "plynx-create-workflow" / "SKILL.md").is_file()

    workflow_file = workspace / "workflows" / "wheel_smoke.yaml"
    workflow_file.write_text(
        """version: 1
name: wheel_smoke
nodes:
  join:
    op: standard_io/text:Concat
    inputs:
      a: "hello "
      b: "wheel"
  write:
    op: standard_io/demo:WriteText
    inputs:
      text: $join.text
      filename: "greeting.txt"
  read:
    op: standard_io/demo:ReadText
    inputs:
      path: $write.file
  echo:
    op: standard_io/demo:Echo
    inputs:
      text: $read.text
""",
        encoding="utf-8",
    )

    # Pre-warm plynx bytecode in site-packages if any before snapshotting, then lock builtin_packs
    # read-only on POSIX and assert zero writes to site-packages during validate/run/run-node.
    ops_res = subprocess.run(
        [str(venv_plynx), "ops", "--json"],
        cwd=workspace,
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ops_res.returncode == 0, f"stdout={ops_res.stdout}\nstderr={ops_res.stderr}"
    ops_data = json.loads(ops_res.stdout)
    std_ops = [entry for entry in ops_data if entry["pack"] == "standard_io"]
    assert std_ops, "Expected standard_io ops from installed wheel"
    repo_root_str = str(ROOT.resolve()).replace("\\", "/")
    sp_str = str(site_packages).replace("\\", "/")
    for entry in std_ops:
        assert entry["source"].startswith(sp_str), f"Expected site-packages source: {entry}"
        assert not entry["source"].startswith(repo_root_str), f"Leaked repo source: {entry}"

    before_snapshot = _snapshot_tree(site_packages)
    saved_modes: list[tuple[Path, int]] = []
    if os.name != "nt":
        saved_modes = _set_readonly_tree(builtin_packs_in_sp)

    try:
        # 1. Validate workflow cleanly (no uv.lock warning for standard_io)
        val_res = subprocess.run(
            [str(venv_plynx), "validate", "workflows/wheel_smoke.yaml"],
            cwd=workspace,
            env=clean_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert val_res.returncode == 0, f"stdout={val_res.stdout}\nstderr={val_res.stderr}"
        assert "uv.lock" not in val_res.stderr

        # 2. Execute real multi-node standard_io workflow
        run_res = subprocess.run(
            [str(venv_plynx), "run", "workflows/wheel_smoke.yaml", "--non-interactive"],
            cwd=workspace,
            env=clean_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run_res.returncode == 0, f"stdout={run_res.stdout}\nstderr={run_res.stderr}"

        runs_dir = workspace / ".plynx" / "runs"
        run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
        assert len(run_dirs) == 1
        echo_node_dir = run_dirs[0] / "nodes" / "echo"
        echo_result = json.loads((echo_node_dir / "result.json").read_text(encoding="utf-8"))
        assert echo_result["status"] == "SUCCESS"
        assert echo_result["outputs"]["text"] == {"kind": "scalar", "value": "hello wheel"}

        # 3. Re-run single node in scratch copy from installed wheel
        rn_res = subprocess.run(
            [str(venv_plynx), "run-node", str(echo_node_dir)],
            cwd=workspace,
            env=clean_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert rn_res.returncode == 0, f"stdout={rn_res.stdout}\nstderr={rn_res.stderr}"

        # No uv environment should have been created for stdlib-only standard_io
        assert not (workspace / ".plynx" / "envs").exists()

        # Zero writes to site-packages (no __pycache__, no lockfiles, no modified files)
        after_snapshot = _snapshot_tree(site_packages)
        assert after_snapshot == before_snapshot
    finally:
        if saved_modes:
            _restore_modes(saved_modes)


def test_uvx_serves_ui_in_clean_machine_environment(tmp_path: Path) -> None:
    """Accept 7.1: uvx --from <wheel> plynx ui serves UI in clean environment."""
    uv_bin = shutil.which("uvx")
    if uv_bin is None:
        pytest.skip("uvx is required for wheel smoke test")

    dist_dir = tmp_path / "dist"
    build_cmd = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--skip-ui",
        "--out-dir",
        str(dist_dir),
    ]
    subprocess.run(build_cmd, cwd=ROOT, check=True)

    plynx_whl = next(dist_dir.glob("plynx-*.whl"))
    clean_dir = tmp_path / "clean_env"
    clean_dir.mkdir()

    # Bind to a dedicated test port
    port = 8891
    server_cmd = [
        uv_bin,
        "--find-links",
        str(dist_dir),
        "--from",
        str(plynx_whl),
        "plynx",
        "ui",
        "--port",
        str(port),
        "--no-browser",
    ]

    proc = subprocess.Popen(
        server_cmd,
        cwd=clean_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait for server to come up
        deadline = time.monotonic() + 20.0
        started = False
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        started = True
                        break
            except Exception:
                time.sleep(0.3)

        if not started:
            stdout_text = (
                proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
            )
            stderr_text = (
                proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            )
            raise AssertionError(
                f"Server did not start up:\nstdout={stdout_text}\nstderr={stderr_text}"
            )

        # Check UI static root
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "<title>PLynx</title>" in html or "index" in html

        # Check ops endpoint
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ops") as resp:
            assert resp.status == 200
            ops_json = resp.read().decode("utf-8")
            assert "standard_io/demo:Echo" in ops_json
            assert "standard_io/text:Concat" in ops_json

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
