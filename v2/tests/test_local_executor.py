"""Tests for Task 1.5: ``LocalExecutor.run``, environment build, logs, and exit-code mapping."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from plynx.api_models import NodeStatus
from plynx.engine import (
    ExecutionRequest,
    Executor,
    LocalExecutor,
    create_executor,
)
from plynx_sdk.protocol import InputsManifest, ScalarValue

EXIT_TEST_OPS_CODE = '''"""Ops exercising every row of the PROTOCOL.md exit-code table."""

from __future__ import annotations

import os
import sys
import time
from typing import TypedDict

from plynx_sdk import Op


class LoudSuccessOp(Op):
    """Prints to stdout and stderr and returns a valid output."""

    TITLE = "Loud success"

    class Outputs(TypedDict):
        out: str

    def run(self, msg: str = "hi") -> Outputs:
        print(f"stdout:{msg}", flush=True)
        print(f"stderr:{msg}", file=sys.stderr, flush=True)
        return {"out": msg.upper()}


class RaiseErrorOp(Op):
    """Raises ValueError -> exit 1."""

    TITLE = "Raise error"

    class Outputs(TypedDict):
        out: str

    def run(self) -> Outputs:
        raise ValueError("op exploded")


class BadOutputProtocolOp(Op):
    """Returns invalid output keys -> harness exits 2."""

    TITLE = "Bad output"

    class Outputs(TypedDict):
        out: str

    def run(self) -> Outputs:
        return {"wrong": "key"}  # type: ignore[typeddict-item]


class RawExitOp(Op):
    """Calls os._exit(code) directly to simulate arbitrary exit codes or missing manifests."""

    TITLE = "Raw exit"

    class Outputs(TypedDict):
        out: str

    def run(self, code: int = 3) -> Outputs:
        os._exit(code)


class SleepOp(Op):
    """Sleeps so timeout and cancel can be tested."""

    TITLE = "Sleep op"

    class Outputs(TypedDict):
        out: str

    def run(self, seconds: float = 30.0) -> Outputs:
        time.sleep(seconds)
        return {"out": "done"}
'''


def _add_exit_test_module_to_standard_io() -> Path:
    """Create a temporary or fixture pack in tmp_path or return standard_io path."""
    return Path(__file__).resolve().parent.parent / "builtin_packs" / "standard_io"


def _create_fixture_pack(base_dir: Path) -> Path:
    """Create a standalone fixture pack that reuses standard_io's pyproject.toml."""
    std_io = _add_exit_test_module_to_standard_io()
    pack_dir = base_dir / "custom_packs" / "exit_pack"
    src_dir = pack_dir / "src" / "exit_pack"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(EXIT_TEST_OPS_CODE, encoding="utf-8")

    # Point plynx-sdk to the repo's packages/plynx-sdk path
    sdk_dir = (std_io.parent.parent / "packages" / "plynx-sdk").as_posix()
    pyproject = f"""[project]
name = "exit-pack"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_dir}", editable = true }}

[build-system]
requires = ["uv_build>=0.9.0,<0.10"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "exit_pack"
"""
    (pack_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return pack_dir


def test_executor_factory_returns_local_executor(tmp_path: Path) -> None:
    """create_executor() returns LocalExecutor and satisfies Executor protocol."""
    executor = create_executor(tmp_path)
    assert isinstance(executor, LocalExecutor)
    assert isinstance(executor, Executor)

    req = ExecutionRequest(
        run_id="r1",
        node_id="n1",
        op="standard_io/demo:Echo",
        attempt=1,
        node_dir=tmp_path / "n1",
        inputs=InputsManifest(inputs={"text": ScalarValue(value="hi")}),
    )
    with pytest.raises(NotImplementedError):
        asyncio.run(executor.launch(req))


def test_local_executor_runs_standard_io_and_emits_building_environment_once(
    tmp_path: Path,
) -> None:
    """First run emits BUILDING_ENVIRONMENT -> RUNNING; second run skips BUILDING_ENVIRONMENT."""
    executor = LocalExecutor(tmp_path)
    statuses_first: list[NodeStatus] = []
    node_dir_1 = tmp_path / ".plynx" / "runs" / "r1" / "nodes" / "echo"

    req_1 = ExecutionRequest(
        run_id="r1",
        node_id="echo",
        op="standard_io/demo:Echo",
        attempt=1,
        node_dir=node_dir_1,
        inputs=InputsManifest(inputs={"text": ScalarValue(value="hello uv")}),
        on_status=statuses_first.append,
    )
    res_1 = asyncio.run(executor.run(req_1))
    assert res_1.status == NodeStatus.SUCCESS, res_1.error
    assert res_1.exit_code == 0
    assert res_1.outputs is not None
    assert res_1.outputs.outputs == {"text": ScalarValue(value="hello uv")}
    assert statuses_first == [NodeStatus.BUILDING_ENVIRONMENT, NodeStatus.RUNNING]

    envs_dir = tmp_path / ".plynx" / "envs"
    built_envs = list(envs_dir.glob("standard_io-*"))
    assert len(built_envs) == 1
    assert (built_envs[0] / "pyvenv.cfg").is_file()

    # Second run reuses the environment without emitting BUILDING_ENVIRONMENT
    statuses_second: list[NodeStatus] = []
    node_dir_2 = tmp_path / ".plynx" / "runs" / "r1" / "nodes" / "pick"
    req_2 = ExecutionRequest(
        run_id="r1",
        node_id="pick",
        op="standard_io/demo:AskFooOrWoo",
        attempt=1,
        node_dir=node_dir_2,
        inputs=InputsManifest(inputs={"prompt": ScalarValue(value="foo or woo?")}),
        on_status=statuses_second.append,
    )
    res_2 = asyncio.run(executor.run(req_2))
    assert res_2.status == NodeStatus.WAITING_FOR_USER
    assert res_2.exit_code == 10
    assert res_2.checkpoint is not None
    assert res_2.checkpoint.checkpoint_id == "cp_0"
    assert statuses_second == [NodeStatus.RUNNING]


def test_local_executor_exit_code_table_logs_timeout_and_cancel(tmp_path: Path) -> None:
    """Covers every row in PROTOCOL.md's exit-code table, log capture, timeout, and cancel."""
    _create_fixture_pack(tmp_path)
    executor = LocalExecutor(tmp_path)
    run_nodes_dir = tmp_path / ".plynx" / "runs" / "r_exit" / "nodes"
    logs_dir = tmp_path / ".plynx" / "runs" / "r_exit" / "logs"

    # 1. Exit 0 with valid outputs.json + stdout/stderr log capture across attempts
    loud_dir = run_nodes_dir / "loud"
    res_a1 = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="loud",
                op="exit_pack/ops:LoudSuccessOp",
                attempt=1,
                node_dir=loud_dir,
                inputs=InputsManifest(inputs={"msg": ScalarValue(value="one")}),
            )
        )
    )
    assert res_a1.status == NodeStatus.SUCCESS
    assert res_a1.outputs is not None
    assert res_a1.outputs.outputs == {"out": ScalarValue(value="ONE")}

    res_a2 = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="loud",
                op="exit_pack/ops:LoudSuccessOp",
                attempt=2,
                node_dir=loud_dir,
                inputs=InputsManifest(inputs={"msg": ScalarValue(value="two")}),
            )
        )
    )
    assert res_a2.status == NodeStatus.SUCCESS
    stdout_text = (logs_dir / "loud.stdout.log").read_text(encoding="utf-8")
    stderr_text = (logs_dir / "loud.stderr.log").read_text(encoding="utf-8")
    assert "stdout:one" in stdout_text
    assert "--- attempt 2 ---" in stdout_text
    assert "stdout:two" in stdout_text
    assert "stderr:one" in stderr_text
    assert "--- attempt 2 ---" in stderr_text
    assert "stderr:two" in stderr_text

    # 2. Exit 1 (op raised exception) -> FAILED
    res_err = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="err_node",
                op="exit_pack/ops:RaiseErrorOp",
                attempt=1,
                node_dir=run_nodes_dir / "err_node",
                inputs=InputsManifest(),
            )
        )
    )
    assert res_err.status == NodeStatus.FAILED
    assert res_err.exit_code == 1
    assert res_err.error is not None
    assert "ValueError: op exploded" in res_err.error

    # 3. Exit 2 (harness protocol error: bad output keys) -> FAILED
    res_bad_out = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="bad_out",
                op="exit_pack/ops:BadOutputProtocolOp",
                attempt=1,
                node_dir=run_nodes_dir / "bad_out",
                inputs=InputsManifest(),
            )
        )
    )
    assert res_bad_out.status == NodeStatus.FAILED
    assert res_bad_out.exit_code == 2

    # 4. Any other non-zero exit code (e.g. exit 3) -> FAILED
    res_exit3 = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="exit3",
                op="exit_pack/ops:RawExitOp",
                attempt=1,
                node_dir=run_nodes_dir / "exit3",
                inputs=InputsManifest(inputs={"code": ScalarValue(value=3)}),
            )
        )
    )
    assert res_exit3.status == NodeStatus.FAILED
    assert res_exit3.exit_code == 3

    # 5. Exit 0 without outputs.json -> FAILED (protocol error)
    res_exit0_no_manifest = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="exit0_no_out",
                op="exit_pack/ops:RawExitOp",
                attempt=1,
                node_dir=run_nodes_dir / "exit0_no_out",
                inputs=InputsManifest(inputs={"code": ScalarValue(value=0)}),
            )
        )
    )
    assert res_exit0_no_manifest.status == NodeStatus.FAILED
    assert res_exit0_no_manifest.exit_code == 0
    assert res_exit0_no_manifest.error is not None
    assert "protocol error" in res_exit0_no_manifest.error

    # 6. Exit 10 without checkpoint.json -> FAILED (protocol error)
    res_exit10_no_cp = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="exit10_no_cp",
                op="exit_pack/ops:RawExitOp",
                attempt=1,
                node_dir=run_nodes_dir / "exit10_no_cp",
                inputs=InputsManifest(inputs={"code": ScalarValue(value=10)}),
            )
        )
    )
    assert res_exit10_no_cp.status == NodeStatus.FAILED
    assert res_exit10_no_cp.exit_code == 10
    assert res_exit10_no_cp.error is not None
    assert "protocol error" in res_exit10_no_cp.error

    # 7. Engine timeout -> CANCELED
    res_timeout = asyncio.run(
        executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="timeout_node",
                op="exit_pack/ops:SleepOp",
                attempt=1,
                node_dir=run_nodes_dir / "timeout_node",
                inputs=InputsManifest(inputs={"seconds": ScalarValue(value=30.0)}),
                timeout=0.3,
            )
        )
    )
    assert res_timeout.status == NodeStatus.CANCELED
    assert res_timeout.error is not None
    assert "timeout" in res_timeout.error

    # 8. Engine cancel_event -> CANCELED
    async def _run_and_cancel() -> None:
        cancel_ev = asyncio.Event()

        async def _trigger_cancel() -> None:
            await asyncio.sleep(0.2)
            cancel_ev.set()

        trigger_task = asyncio.create_task(_trigger_cancel())
        res_cancel = await executor.run(
            ExecutionRequest(
                run_id="r_exit",
                node_id="cancel_node",
                op="exit_pack/ops:SleepOp",
                attempt=1,
                node_dir=run_nodes_dir / "cancel_node",
                inputs=InputsManifest(inputs={"seconds": ScalarValue(value=30.0)}),
                cancel_event=cancel_ev,
            )
        )
        await trigger_task
        assert res_cancel.status == NodeStatus.CANCELED
        assert res_cancel.error == "canceled"

    asyncio.run(_run_and_cancel())
