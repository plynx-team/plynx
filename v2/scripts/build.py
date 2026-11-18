"""Build plynx-sdk and plynx wheels containing built static/ and builtin_packs."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
BUILTIN_PACKS_DIR = ROOT / "builtin_packs"
PLYNX_PKG_DIR = ROOT / "packages" / "plynx"
PLYNX_SRC_DIR = PLYNX_PKG_DIR / "src" / "plynx"
STAGED_BUILTIN_DIR = PLYNX_SRC_DIR / "builtin_packs"
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


def stage_builtin_packs() -> None:
    """Copy ``v2/builtin_packs`` into ``packages/plynx/src/plynx/builtin_packs``."""
    if STAGED_BUILTIN_DIR.exists():
        shutil.rmtree(STAGED_BUILTIN_DIR)

    print(f"Staging builtin packs into {STAGED_BUILTIN_DIR}...")
    shutil.copytree(
        BUILTIN_PACKS_DIR,
        STAGED_BUILTIN_DIR,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache"),
    )


def clean_staged_builtin_packs() -> None:
    """Remove staged builtin packs directory from packages source."""
    if STAGED_BUILTIN_DIR.exists():
        shutil.rmtree(STAGED_BUILTIN_DIR)


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

    wheels = list(target_out.glob("*.whl"))
    return wheels


def verify_wheel_contents(plynx_wheel: Path) -> None:
    """Verify that ``plynx`` wheel contains static assets and builtin packs."""
    with zipfile.ZipFile(plynx_wheel) as archive:
        names = set(archive.namelist())

    required_entries = [
        "plynx/static/index.html",
        "plynx/builtin_packs/standard_io/pyproject.toml",
        "plynx/builtin_packs/standard_io/src/standard_io/__init__.py",
        "plynx/builtin_packs/standard_io/src/standard_io/demo.py",
        "plynx/builtin_packs/standard_io/src/standard_io/text.py",
    ]
    missing = [entry for entry in required_entries if entry not in names]
    if missing:
        raise RuntimeError(f"Wheel {plynx_wheel.name} is missing required entries: {missing}")
    print(f"Verified {plynx_wheel.name}: static assets and builtin packs present.")


def main(argv: list[str] | None = None) -> int:
    """Main build entrypoint."""
    parser = argparse.ArgumentParser(
        description="Build plynx-sdk and plynx wheels containing static UI and builtin packs."
    )
    parser.add_argument(
        "--skip-ui",
        action="store_true",
        help="Skip rebuilding the UI with npm (uses existing static/ assets).",
    )
    parser.add_argument(
        "--keep-staged",
        action="store_true",
        help="Keep staged builtin_packs directory in packages/plynx/src/plynx after build.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DIST_DIR,
        help=f"Directory to write distributions to (default: {DIST_DIR}).",
    )
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="Stage UI and builtin packs into packages/plynx/src/plynx without building wheels.",
    )
    args = parser.parse_args(argv)

    try:
        build_ui(skip_ui=args.skip_ui)
        stage_builtin_packs()

        if args.stage_only:
            print("Staging complete.")
            return 0

        wheels = build_wheels(out_dir=args.out_dir)
        plynx_whl = next((w for w in wheels if w.name.startswith("plynx-2")), None)
        if plynx_whl is None:
            raise RuntimeError("plynx wheel was not generated")
        verify_wheel_contents(plynx_whl)
        print("Build completed successfully.")
        return 0
    finally:
        if not args.keep_staged and not args.stage_only:
            clean_staged_builtin_packs()


if __name__ == "__main__":
    sys.exit(main())
