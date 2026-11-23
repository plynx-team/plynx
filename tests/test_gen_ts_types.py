"""Tests for ``scripts/gen_ts_types.py`` and ``ui/src/api/types.gen.ts``."""

from __future__ import annotations

from pathlib import Path

from scripts.gen_ts_types import TARGET_PATH, main, render_ts_types


def test_committed_ts_types_file_is_up_to_date() -> None:
    """Fails if ui/src/api/types.gen.ts is missing or out of sync with the Pydantic models."""
    assert TARGET_PATH.is_file(), f"Missing generated file: {TARGET_PATH}"
    assert main(["--check"]) == 0
    assert TARGET_PATH.read_text(encoding="utf-8") == render_ts_types()


def test_running_generator_twice_produces_no_diff(tmp_path: Path) -> None:
    """Running gen_ts_types twice produces byte-for-byte identical output."""
    out = tmp_path / "types.gen.ts"
    assert main(["--output", str(out)]) == 0
    first_bytes = out.read_bytes()

    assert main(["--output", str(out)]) == 0
    second_bytes = out.read_bytes()

    assert first_bytes == second_bytes
    assert main(["--check", "--output", str(out)]) == 0


def test_stale_or_missing_ts_types_file_fails_check(tmp_path: Path) -> None:
    """--check returns 1 when the output file is missing or stale."""
    out = tmp_path / "types.gen.ts"
    assert main(["--check", "--output", str(out)]) == 1

    out.write_text("// stale\n", encoding="utf-8")
    assert main(["--check", "--output", str(out)]) == 1
