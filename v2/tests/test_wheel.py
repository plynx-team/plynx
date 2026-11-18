"""Tests for packaging wheels and serving UI in clean environment (Task 7.1)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT / "scripts" / "build.py"


def test_build_script_creates_wheels_with_static_and_builtin_packs(tmp_path: Path) -> None:
    """scripts/build.py builds plynx-sdk and plynx wheels containing static/ and builtin_packs."""
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
    assert "plynx/builtin_packs/standard_io/pyproject.toml" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/__init__.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/demo.py" in names
    assert "plynx/builtin_packs/standard_io/src/standard_io/text.py" in names


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
