"""Tests for ``scripts/check_legacy_untouched.py`` in a throwaway git repository."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_legacy_untouched.py"
GIT_IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
PROJECT = "project"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *GIT_IDENTITY, *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with a legacy file and a project folder holding a copy of the script."""
    _git(tmp_path, "init", "-b", "master")
    (tmp_path / "legacy.txt").write_text("legacy\n")
    scripts = tmp_path / PROJECT / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPT, scripts / SCRIPT.name)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    _git(tmp_path, "checkout", "-b", "work")
    return tmp_path


def _commit(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"change {relative_path}")


def _run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / PROJECT / "scripts" / SCRIPT.name
    return subprocess.run(
        [sys.executable, str(script)], cwd=repo, capture_output=True, text=True, check=False
    )


def test_clean_branch_passes(repo: Path) -> None:
    _commit(repo, f"{PROJECT}/new_file.py", "x = 1\n")
    assert _run_check(repo).returncode == 0


def test_modified_legacy_file_fails(repo: Path) -> None:
    _commit(repo, "legacy.txt", "changed\n")
    result = _run_check(repo)
    assert result.returncode == 1
    assert "legacy.txt" in result.stderr


def test_new_legacy_file_fails(repo: Path) -> None:
    _commit(repo, "other/new.txt", "new\n")
    assert _run_check(repo).returncode == 1


def test_new_workflow_file_is_allowed(repo: Path) -> None:
    _commit(repo, ".github/workflows/v2-ci.yml", "name: ci\n")
    assert _run_check(repo).returncode == 0


def test_modified_workflow_file_fails(repo: Path) -> None:
    _git(repo, "checkout", "master")
    _commit(repo, ".github/workflows/v2-ci.yml", "name: ci\n")
    _git(repo, "checkout", "-b", "work2")
    _commit(repo, ".github/workflows/v2-ci.yml", "name: changed\n")
    assert _run_check(repo).returncode == 1


def test_unrelated_workflow_file_fails(repo: Path) -> None:
    _commit(repo, ".github/workflows/ci.yml", "name: ci\n")
    assert _run_check(repo).returncode == 1


def test_deleted_legacy_file_fails(repo: Path) -> None:
    (repo / "legacy.txt").unlink()
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "delete legacy")
    assert _run_check(repo).returncode == 1


def test_changes_merged_from_base_are_ignored(repo: Path) -> None:
    """A hotfix merged from master is not a violation (three-dot diff)."""
    _git(repo, "checkout", "master")
    _commit(repo, "legacy.txt", "hotfix\n")
    _git(repo, "checkout", "work")
    _commit(repo, f"{PROJECT}/new_file.py", "x = 1\n")
    _git(repo, "merge", "--no-edit", "master")
    assert _run_check(repo).returncode == 0
