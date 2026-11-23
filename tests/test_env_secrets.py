"""Tests for Task 1.6: ``.env`` reader, ``env_passthrough``, and secret non-leakage."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec, RunStatus
from plynx.engine import (
    LocalExecutor,
    Scheduler,
    build_child_environment,
    parse_dotenv,
)
from plynx.store import RunStore
from plynx.workflow.models import Workflow

from tests.fakes import FakeRegistry

ENV_OP_CODE = '''"""Fixture op that checks environment variables without leaking secrets."""

from __future__ import annotations

import os
from typing import TypedDict

from plynx_sdk import Op


class CheckSecretEnvOp(Op):
    """Verify secret and passthrough env vars exist inside the child process."""

    TITLE = "Check secret env"

    class Outputs(TypedDict):
        has_secret: bool
        secret_len: int
        allowed_val: str
        has_blocked: bool

    def run(self, env_key: str = "PLYNX_SECRET_TOKEN") -> Outputs:
        secret = os.environ.get(env_key, "")
        allowed = os.environ.get("PLYNX_ALLOWED_HOST_VAR", "")
        has_blocked = "PLYNX_BLOCKED_HOST_VAR" in os.environ
        return {
            "has_secret": bool(secret),
            "secret_len": len(secret),
            "allowed_val": allowed,
            "has_blocked": has_blocked,
        }
'''


def _create_env_fixture_pack(base_dir: Path) -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    sdk_dir = (repo_root / "packages" / "plynx-sdk").as_posix()
    pack_dir = base_dir / "custom_packs" / "env_pack"
    src_dir = pack_dir / "src" / "env_pack"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(ENV_OP_CODE, encoding="utf-8")

    pyproject = f"""[project]
name = "env-pack"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_dir}", editable = true }}

[build-system]
requires = ["uv_build>=0.9.0,<0.10"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "env_pack"
"""
    (pack_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return pack_dir


def test_parse_dotenv_minimal_parser() -> None:
    """parse_dotenv supports comments, export prefix, quotes, escapes, and inline comments."""
    raw = """
# Top comment
SIMPLE=value1
export EXPORTED = value2 # trailing comment
SINGLE_QUOTED='hello # not a comment'
DOUBLE_QUOTED="line1\\nline2\\t\\"quoted\\""
EMPTY=
"""
    parsed = parse_dotenv(raw)
    assert parsed == {
        "SIMPLE": "value1",
        "EXPORTED": "value2",
        "SINGLE_QUOTED": "hello # not a comment",
        "DOUBLE_QUOTED": 'line1\nline2\t"quoted"',
        "EMPTY": "",
    }


def test_build_child_environment_respects_env_passthrough_and_dotenv(tmp_path: Path) -> None:
    """env_passthrough restricts host env while .env values always reach the child."""
    (tmp_path / ".env").write_text("DOTENV_SECRET=from_dotenv\n", encoding="utf-8")
    (tmp_path / "plynx.yaml").write_text(
        "env_passthrough:\n  - ALLOWED_VAR\n",
        encoding="utf-8",
    )
    fake_host = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp/home",
        "ALLOWED_VAR": "yes_allowed",
        "BLOCKED_VAR": "no_blocked",
        "VIRTUAL_ENV": "/some/venv",
    }
    env_dir = tmp_path / ".plynx" / "envs" / "pack-123"
    child_env = build_child_environment(tmp_path, env_dir, host_env=fake_host)

    assert child_env["DOTENV_SECRET"] == "from_dotenv"
    assert child_env["ALLOWED_VAR"] == "yes_allowed"
    assert "BLOCKED_VAR" not in child_env
    assert "VIRTUAL_ENV" not in child_env
    assert child_env["PYTHONUNBUFFERED"] == "1"
    assert child_env["PYTHONUTF8"] == "1"
    assert child_env["UV_PROJECT_ENVIRONMENT"] == str(env_dir)


def test_dotenv_reaches_child_and_never_appears_in_persisted_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Value in .env reaches child and never appears in manifests, snapshots, db, or events."""
    secret_value = "super_secret_token_val_9988776655"
    blocked_value = "blocked_host_secret_11223344"

    (tmp_path / ".env").write_text(
        f"PLYNX_SECRET_TOKEN={secret_value}\n",
        encoding="utf-8",
    )
    (tmp_path / "plynx.yaml").write_text(
        "env_passthrough:\n  - PLYNX_ALLOWED_HOST_VAR\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_ALLOWED_HOST_VAR", "allowed_ok")
    monkeypatch.setenv("PLYNX_BLOCKED_HOST_VAR", blocked_value)

    _create_env_fixture_pack(tmp_path)

    reg = FakeRegistry(
        ops=[
            OpEntry(
                id="env_pack/ops:CheckSecretEnvOp",
                pack="env_pack",
                module="ops",
                name="CheckSecretEnvOp",
                kind="class",
                title="Check secret env",
                inputs=[
                    InputPortSpec(
                        name="env_key",
                        type="str",
                        required=False,
                        default="PLYNX_SECRET_TOKEN",
                    )
                ],
                outputs=[
                    OutputPortSpec(name="has_secret", type="bool"),
                    OutputPortSpec(name="secret_len", type="int"),
                    OutputPortSpec(name="allowed_val", type="str"),
                    OutputPortSpec(name="has_blocked", type="bool"),
                ],
                source="custom_packs/env_pack/src/env_pack/ops.py",
            )
        ]
    )

    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "secret_check",
            "nodes": {
                "check": {
                    "op": "env_pack/ops:CheckSecretEnvOp",
                    "inputs": {"env_key": "PLYNX_SECRET_TOKEN"},
                }
            },
        }
    )

    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor, reg)

    state = asyncio.run(
        scheduler.run(
            wf,
            workflow_path="workflows/secret_check.yaml",
            workflow_bytes=b"version: 1\nname: secret_check\n",
            layout_bytes=b'{"schema": 1, "nodes": {}, "viewport": {"x": 0, "y": 0, "zoom": 1}}\n',
        )
    )
    assert state.status == RunStatus.SUCCESS

    node_dir = store.node_dir(state.id, "check")
    outputs_raw = (node_dir / "outputs.json").read_text(encoding="utf-8")
    assert '"has_secret": true' in outputs_raw or '"value": true' in outputs_raw
    assert f'"value": {len(secret_value)}' in outputs_raw
    assert '"value": "allowed_ok"' in outputs_raw

    # Grep every persisted artifact, manifest, snapshot, event log, and SQLite database file
    run_dir = store.run_dir(state.id)
    files_to_grep = [
        run_dir / "run_manifest.json",
        run_dir / "workflow.snapshot.yaml",
        run_dir / "layout.snapshot.json",
        run_dir / "events.jsonl",
        node_dir / "inputs.json",
        node_dir / "outputs.json",
        node_dir / "result.json",
        tmp_path / ".plynx" / "plynx.db",
    ]
    for extra_db_file in (tmp_path / ".plynx").glob("plynx.db*"):
        if extra_db_file not in files_to_grep:
            files_to_grep.append(extra_db_file)

    for path in files_to_grep:
        assert path.is_file(), f"Expected file {path} to exist"
        raw_bytes = path.read_bytes()
        assert secret_value.encode("utf-8") not in raw_bytes, f"Secret leaked into {path}"
        assert blocked_value.encode("utf-8") not in raw_bytes, (
            f"Blocked host secret leaked into {path}"
        )
