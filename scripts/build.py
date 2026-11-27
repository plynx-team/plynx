"""Build plynx-sdk and plynx wheels containing built static/ and standard_io."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
PLYNX_PKG_DIR = ROOT / "packages" / "plynx"
PLYNX_SRC_DIR = PLYNX_PKG_DIR / "src" / "plynx"
STATIC_DIR = PLYNX_SRC_DIR / "static"
DIST_DIR = ROOT / "dist"


def build_ui(skip_ui: bool = False) -> None:
    """Build Vite UI assets into ``packages/plynx/src/plynx/static`` unless skipped."""
    if skip_ui:
        if not (STATIC_DIR / "index.html").is_file():
            raise RuntimeError(
                f"Static directory {STATIC_DIR} is missing index.html and --skip-ui was requested"
            )
        return

    npm_path = shutil.which("npm")
    if npm_path is None:
        if (STATIC_DIR / "index.html").is_file():
            print("npm not found; using existing built static UI assets.")
            return
        raise RuntimeError("npm is required to build the UI assets but was not found in PATH")

    print(f"Building UI assets in {UI_DIR}...")
    subprocess.run([npm_path, "run", "build"], cwd=UI_DIR, check=True)


def build_wheels(out_dir: Path | None = None) -> list[Path]:
    """Run ``uv build`` for ``plynx-sdk`` and ``plynx``."""
    target_out = out_dir or DIST_DIR
    target_out.mkdir(parents=True, exist_ok=True)

    uv_path = shutil.which("uv")
    if uv_path is None:
        raise RuntimeError("uv is required to build distributions but was not found in PATH")

    for pkg in ("plynx-sdk", "plynx"):
        print(f"Building {pkg} distribution...")
        cmd = [
            uv_path,
            "build",
            "--package",
            pkg,
            "--out-dir",
            str(target_out),
        ]
        subprocess.run(cmd, cwd=ROOT, check=True)

    return list(target_out.glob("*.whl"))


def verify_wheel_contents(plynx_wheel: Path) -> None:
    """Verify that ``plynx`` wheel contains static assets and standard_io without uv.lock."""
    with zipfile.ZipFile(plynx_wheel) as archive:
        names = set(archive.namelist())

    required_entries = [
        "plynx/static/index.html",
        "plynx/skills/plynx-create-workflow/SKILL.md",
        "plynx/builtin_packs/standard_io/pyproject.toml",
        "plynx/builtin_packs/standard_io/src/standard_io/__init__.py",
        "plynx/builtin_packs/standard_io/src/standard_io/agent.py",
        "plynx/builtin_packs/standard_io/src/standard_io/demo.py",
        "plynx/builtin_packs/standard_io/src/standard_io/interactive.py",
        "plynx/builtin_packs/standard_io/src/standard_io/text.py",
    ]
    missing = [entry for entry in required_entries if entry not in names]
    if missing:
        raise RuntimeError(f"Wheel {plynx_wheel.name} is missing required entries: {missing}")
    lockfiles = [entry for entry in names if entry.endswith("uv.lock")]
    if lockfiles:
        raise RuntimeError(f"Wheel {plynx_wheel.name} must not bundle lockfiles: {lockfiles}")
    print(f"Verified {plynx_wheel.name}: static assets and standard_io present.")


def main(argv: list[str] | None = None) -> int:
    """Main build entrypoint."""
    parser = argparse.ArgumentParser(
        description="Build plynx-sdk and plynx wheels containing static UI and standard_io."
    )
    parser.add_argument(
        "--skip-ui",
        action="store_true",
        help="Skip rebuilding the UI with npm (uses existing static/ assets).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DIST_DIR,
        help=f"Directory to write distributions to (default: {DIST_DIR}).",
    )
    args = parser.parse_args(argv)

    build_ui(skip_ui=args.skip_ui)
    wheels = build_wheels(out_dir=args.out_dir)
    plynx_whl = next((w for w in wheels if w.name.startswith("plynx-2")), None)
    if plynx_whl is None:
        raise RuntimeError("plynx wheel was not generated")
    verify_wheel_contents(plynx_whl)
    print("Build completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
