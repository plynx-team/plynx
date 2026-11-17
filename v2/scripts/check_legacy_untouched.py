"""Fail when the current branch touches files outside this project folder.

The project folder is the parent of ``scripts/``. Its position inside the git repository is
resolved at run time, so the check keeps working after the folder is moved to the repository
root. The only allowed change outside the project folder is a newly added CI workflow file
matching ``.github/workflows/v2-*.yml``.

Usage: ``python scripts/check_legacy_untouched.py [--base master]``. Exit code 0 means clean,
1 means a file outside the project folder was changed.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ALLOWED_NEW_FILE_PATTERN = ".github/workflows/v2-*.yml"
ALLOWED_AGENT_PATTERNS = (".agents/*", ".agents/**", "AGENTS.md")
DEFAULT_BASE = "master"


def _git(project_root: Path, *args: str) -> str:
    """Run a git command inside the project folder and return its stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def find_violations(project_root: Path, base: str = DEFAULT_BASE) -> list[str]:
    """Return ``"<status> <path>"`` lines for changes outside ``project_root``."""
    prefix = _git(project_root, "rev-parse", "--show-prefix").strip()
    if not prefix:
        # The project folder is the repository root: nothing can be outside it.
        return []
    # Paths from `git diff` are relative to the repository root, not the working directory.
    diff = _git(project_root, "diff", "--name-status", "--no-renames", f"{base}...HEAD")
    violations: list[str] = []
    for line in diff.splitlines():
        status, _, path = line.partition("\t")
        if path.startswith(prefix):
            continue
        if status == "A" and fnmatch.fnmatchcase(path, ALLOWED_NEW_FILE_PATTERN):
            continue
        if any(fnmatch.fnmatchcase(path, pat) for pat in ALLOWED_AGENT_PATTERNS):
            continue
        violations.append(f"{status} {path}")
    return violations


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--base", default=DEFAULT_BASE, help="base branch (default: master)")
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parent.parent
    try:
        violations = find_violations(project_root, args.base)
    except subprocess.CalledProcessError as error:
        print(f"git failed: {error.stderr.strip()}", file=sys.stderr)
        return 1
    if violations:
        print("Files changed outside the project folder:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
