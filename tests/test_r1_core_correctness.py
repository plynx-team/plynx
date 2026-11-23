"""Regression and acceptance tests for Phase R1 (R1.1-R1.4)."""

from __future__ import annotations

import asyncio
import io
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import CliRunner
from plynx.api_models import (
    NodeStatus,
    RunStatus,
    StageApprovalEvent,
    StageGateKind,
    StageGateStatus,
    StageResolvedEvent,
    WorkflowInputSpec,
)
from plynx.cas.blob_store import BlobStore, hash_file
from plynx.cas.materialize import materialize_inputs
from plynx.cli import main as cli_main
from plynx.cli.interaction import (
    make_terminal_stage_approval_callback,
    make_terminal_stage_inputs_callback,
)
from plynx.engine import LocalExecutor, Scheduler, SchedulerOptions
from plynx.engine.executor import ExecutionRequest
from plynx.engine.runner import ENV_READY_SENTINEL
from plynx.registry import PackRegistry
from plynx.server.app import create_app
from plynx.store import RunStore
from plynx.workflow.models import NodeRef, Workflow, load_workflow
from plynx.workflow.validator import validate_workflow
from plynx_sdk.harness import EXIT_PROTOCOL_ERROR, EXIT_SUCCESS, run_harness
from plynx_sdk.protocol import InputsManifest, OutputsManifest, ScalarValue

from tests.fakes import FakeExecutor

# ---------------------------------------------------------------------------
# R1.1: External workspace inputs are copied (never hardlinked) into CAS
# ---------------------------------------------------------------------------


def test_r11_workspace_input_file_stays_writable_and_edits_do_not_corrupt_cas(
    tmp_path: Path,
) -> None:
    """Accept R1.1: workspace input file stays writable and in-place edits do not affect CAS."""
    user_file = tmp_path / "notes.txt"
    user_file.write_text("original content\n", encoding="utf-8")
    original_sha, _ = hash_file(user_file)

    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "read_file_test",
            "nodes": {
                "read": {
                    "op": "standard_io/files:BundleDirectory",
                    "inputs": {"file_a": "notes.txt"},
                }
            },
        }
    )

    store = RunStore(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor)
    final_state = asyncio.run(scheduler.run(wf, options=SchedulerOptions(no_cache=True)))
    assert final_state.status == RunStatus.SUCCESS

    # User file must remain writable (not chmod 0o444)
    assert os.access(user_file, os.W_OK)
    assert bool(user_file.stat().st_mode & stat.S_IWUSR)

    # CAS blob must exist and have a different inode than user_file
    blob_store = BlobStore.from_workspace(tmp_path)
    blob_path = blob_store.blob_path(original_sha)
    assert blob_path.is_file()
    assert blob_path.stat().st_ino != user_file.stat().st_ino

    # Edit user file in place; CAS blob SHA-256 and bytes must be unchanged
    user_file.write_text("edited by user later\n", encoding="utf-8")
    blob_sha_after, _ = hash_file(blob_path)
    assert blob_sha_after == original_sha
    assert blob_path.read_text(encoding="utf-8") == "original content\n"


def test_r11_workspace_input_directory_stays_writable(tmp_path: Path) -> None:
    """Workspace directory inputs are copied into CAS so files remain writable."""
    data_dir = tmp_path / "my_data"
    data_dir.mkdir()
    item_file = data_dir / "a.txt"
    item_file.write_text("v1", encoding="utf-8")
    original_sha, _ = hash_file(item_file)

    blob_store = BlobStore.from_workspace(tmp_path)
    registry = PackRegistry(tmp_path)
    wf = Workflow.model_validate(
        {
            "version": 1,
            "name": "dir_test",
            "nodes": {
                "ls": {
                    "op": "standard_io/files:ListDirectory",
                    "inputs": {"directory": "my_data"},
                }
            },
        }
    )
    node_dir = tmp_path / ".plynx" / "runs" / "r1" / "nodes" / "ls"
    materialize_inputs(
        node_id="ls",
        spec=wf.nodes["ls"],
        dst_node_dir=node_dir,
        completed_outputs={},
        blob_store=blob_store,
        workspace_root=tmp_path,
        registry=registry,
    )

    assert os.access(item_file, os.W_OK)
    item_file.write_text("v2", encoding="utf-8")
    blob_sha_after, _ = hash_file(blob_store.blob_path(original_sha))
    assert blob_sha_after == original_sha


# ---------------------------------------------------------------------------
# R1.2: uv env atomic readiness sentinel and cleanup of partial env dirs
# ---------------------------------------------------------------------------


def _create_isolated_pack(workspace_root: Path, pack_name: str = "r12_pack") -> Path:
    sdk_dir = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk"
    pack_dir = workspace_root / "custom_packs" / pack_name
    src_dir = pack_dir / "src" / pack_name
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(
        """from typing import TypedDict
from plynx_sdk import Op

class Ping(Op):
    TITLE = "Ping"

    class Outputs(TypedDict):
        out: str

    def run(self, msg: str = "ok") -> Outputs:
        return {"out": msg}
""",
        encoding="utf-8",
    )
    (pack_dir / "pyproject.toml").write_text(
        f"""[project]
name = "{pack_name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["plynx-sdk"]

[tool.uv.sources]
plynx-sdk = {{ path = "{sdk_dir.as_posix()}", editable = true }}

[build-system]
requires = ["uv_build>=0.9.0,<0.10"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "{pack_name}"
""",
        encoding="utf-8",
    )
    uv_bin = shutil.which("uv")
    assert uv_bin is not None
    subprocess.run([uv_bin, "lock", "--project", str(pack_dir)], cwd=pack_dir, check=True)
    return pack_dir


def test_r12_partial_env_without_sentinel_rebuilds_cleanly(tmp_path: Path) -> None:
    """Accept R1.2: a partial env dir with pyvenv.cfg but no sentinel is rebuilt cleanly."""
    from plynx.engine.runner import _compute_env_hash

    pack_dir = _create_isolated_pack(tmp_path, "r12_pack")
    env_hash = _compute_env_hash(pack_dir)
    env_dir = tmp_path / ".plynx" / "envs" / f"r12_pack-{env_hash}"
    env_dir.mkdir(parents=True, exist_ok=True)
    # Simulate a killed/interrupted uv sync that wrote pyvenv.cfg but never finished
    (env_dir / "pyvenv.cfg").write_text("home = /nonexistent\n", encoding="utf-8")
    (env_dir / "stale_marker.txt").write_text("partial", encoding="utf-8")
    assert not (env_dir / ENV_READY_SENTINEL).is_file()

    executor = LocalExecutor(tmp_path)
    statuses: list[NodeStatus] = []
    node_dir = tmp_path / ".plynx" / "runs" / "r1" / "nodes" / "p"
    req = ExecutionRequest(
        run_id="r1",
        node_id="p",
        op="r12_pack/ops:Ping",
        attempt=1,
        node_dir=node_dir,
        inputs=InputsManifest(inputs={"msg": ScalarValue(value="hello")}),
        on_status=statuses.append,
    )
    res = asyncio.run(executor.run(req))
    assert res.status == NodeStatus.SUCCESS, res.error
    assert statuses == [NodeStatus.BUILDING_ENVIRONMENT, NodeStatus.RUNNING]
    assert (env_dir / ENV_READY_SENTINEL).is_file()
    assert not (env_dir / "stale_marker.txt").exists()


# ---------------------------------------------------------------------------
# R1.3: $$ round-trip, Optional[Path] outputs, input resolution, CLI run_id
# ---------------------------------------------------------------------------


def test_r13_escaped_dollar_round_trips_through_rest_and_inline_runs(tmp_path: Path) -> None:
    """GET -> PUT /workflows/{path} and inline POST /runs round-trip $$ literal strings."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "dollars.yaml"
    wf_path.write_text(
        """version: 1
name: dollars
nodes:
  echo:
    op: standard_io/demo:Echo
    inputs:
      text: "$$100"
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path, executor_factory=lambda _: FakeExecutor())

    async def _run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            get_res = await client.get("/workflows/workflows/dollars.yaml")
            assert get_res.status_code == 200, get_res.text
            doc = get_res.json()
            assert doc["workflow"]["nodes"]["echo"]["inputs"]["text"] == "$$100"

            # PUT the fetched document directly back without 422
            put_res = await client.put("/workflows/workflows/dollars.yaml", json=doc)
            assert put_res.status_code == 200, put_res.text
            reloaded = load_workflow(wf_path)
            assert reloaded.nodes["echo"].inputs["text"] == "$100"

            # Inline POST /runs with the same workflow JSON must succeed
            run_res = await client.post(
                "/runs",
                json={
                    "workflow_path": "workflows/dollars.yaml",
                    "workflow": doc["workflow"],
                    "inputs": {},
                },
            )
            assert run_res.status_code == 201, run_res.text

    asyncio.run(_run())


def test_r13_plain_json_dict_with_from_node_not_hijacked() -> None:
    """A plain JSON dict containing 'from_node' alongside extra keys stays a dict."""
    wf = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "n": {
                    "op": "standard_io/demo:Echo",
                    "inputs": {
                        "meta": {"from_node": "alice", "extra": 123},
                        "num": {"from_node": 42},
                        "real_ref": {"from_node": "other", "output": "val"},
                    },
                }
            },
        }
    )
    assert wf.nodes["n"].inputs["meta"] == {"from_node": "alice", "extra": 123}
    assert wf.nodes["n"].inputs["num"] == {"from_node": 42}
    assert wf.nodes["n"].inputs["real_ref"] == NodeRef(from_node="other", output="val")


def test_r13_harness_handles_none_for_optional_path_and_directory_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Harness accepts None for Path | None and Directory | None outputs, rejects non-optional."""
    mod_file = tmp_path / "opt_outputs_mod.py"
    mod_file.write_text(
        """from pathlib import Path
from typing import TypedDict
from plynx_sdk import Directory, Op

class OptionalOutOp(Op):
    TITLE = "Optional Out"

    class Outputs(TypedDict):
        maybe_file: Path | None
        maybe_dir: Directory | None

    def run(self) -> Outputs:
        return {"maybe_file": None, "maybe_dir": None}

class RequiredFileOp(Op):
    TITLE = "Required File"

    class Outputs(TypedDict):
        req_file: Path

    def run(self) -> Outputs:
        return {"req_file": None}  # type: ignore[typeddict-item]
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    # Optional Path | None and Directory | None -> exit 0 with ScalarValue(None)
    node_dir_ok = tmp_path / "node_ok"
    node_dir_ok.mkdir()
    (node_dir_ok / "inputs.json").write_text(InputsManifest().to_json(), encoding="utf-8")
    rc = run_harness("opt_outputs_mod:OptionalOutOp", node_dir_ok)
    assert rc == EXIT_SUCCESS
    out_manifest = OutputsManifest.from_json((node_dir_ok / "outputs.json").read_bytes())
    assert out_manifest.outputs["maybe_file"] == ScalarValue(value=None)
    assert out_manifest.outputs["maybe_dir"] == ScalarValue(value=None)

    # Non-optional Path returning None -> exit 2 (protocol error)
    node_dir_bad = tmp_path / "node_bad"
    node_dir_bad.mkdir()
    (node_dir_bad / "inputs.json").write_text(InputsManifest().to_json(), encoding="utf-8")
    rc_bad = run_harness("opt_outputs_mod:RequiredFileOp", node_dir_bad)
    assert rc_bad == EXIT_PROTOCOL_ERROR


def test_r13_input_resolution_alignment_empty_str_missing_file_and_cli_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validator/scheduler require node_id.port, allow empty str, fail on missing file, keep str --set."""
    monkeypatch.chdir(tmp_path)
    registry = PackRegistry(tmp_path)

    # 1. Bare port_name in run_inputs is NOT treated as bound by validator
    wf_unbound = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "e": {"op": "standard_io/demo:Echo"},
            },
        }
    )
    issues_bare = validate_workflow(wf_unbound, registry, run_inputs={"text": "hi"})
    assert any(
        i.severity == "warning" and "unbound run input 'text'" in i.message for i in issues_bare
    )
    issues_qualified = validate_workflow(wf_unbound, registry, run_inputs={"e.text": "hi"})
    assert not any("unbound run input" in i.message for i in issues_qualified)

    # 2. Empty string "" for str-typed required input is accepted and runs without pausing
    store = RunStore(tmp_path)
    scheduler = Scheduler(store, LocalExecutor(tmp_path), registry)
    state_empty = asyncio.run(
        scheduler.run(
            wf_unbound,
            options=SchedulerOptions(
                run_inputs={"e.text": ""},
                non_interactive=True,
                no_cache=True,
            ),
        )
    )
    assert state_empty.status == RunStatus.SUCCESS
    assert state_empty.nodes["e"].status == NodeStatus.SUCCESS

    # 3. Missing literal file path fails cleanly with clear error
    wf_missing_file = Workflow.model_validate(
        {
            "version": 1,
            "nodes": {
                "r": {
                    "op": "standard_io/files:BundleDirectory",
                    "inputs": {"file_a": "does_not_exist.txt"},
                }
            },
        }
    )
    state_missing = asyncio.run(
        scheduler.run(wf_missing_file, options=SchedulerOptions(no_cache=True))
    )
    assert state_missing.status == RunStatus.FAILED
    assert state_missing.nodes["r"].status == NodeStatus.FAILED
    assert state_missing.nodes["r"].error is not None
    assert "does_not_exist.txt" in state_missing.nodes["r"].error

    # 4. CLI --set does NOT coerce str-typed ports via json.loads, and prints run_id
    wf_file = tmp_path / "echo.yaml"
    wf_file.write_text(
        """version: 1
name: echo_str
nodes:
  e:
    op: standard_io/demo:Echo
""",
        encoding="utf-8",
    )
    runner = CliRunner()
    res = runner.invoke(
        cli_main,
        ["run", str(wf_file), "--set", "e.text=007", "--non-interactive", "--no-cache"],
    )
    assert res.exit_code == 0, res.output
    assert "run_id:" in res.output
    latest_run = store.list_runs(limit=1)[0]
    latest_state = store.get_run_state(latest_run.id)
    assert latest_state is not None
    assert latest_state.run_inputs["e.text"] == "007"

    # Also check --set with "true" on str port stays "true" (str, not bool)
    res_true = runner.invoke(
        cli_main,
        ["run", str(wf_file), "--set", "e.text=true", "--non-interactive", "--no-cache"],
    )
    assert res_true.exit_code == 0, res_true.output
    latest_run2 = store.list_runs(limit=1)[0]
    latest_state2 = store.get_run_state(latest_run2.id)
    assert latest_state2 is not None
    assert latest_state2.run_inputs["e.text"] == "true"
    assert isinstance(latest_state2.run_inputs["e.text"], str)

    # 5. CLI prints run_id on exit 2 (waiting) and exit 1 (failed)
    res_wait = runner.invoke(
        cli_main,
        ["run", str(wf_file), "--non-interactive"],
    )
    assert res_wait.exit_code == 2, res_wait.output
    assert "run_id:" in res_wait.output

    wf_fail = tmp_path / "fail_missing.yaml"
    wf_fail.write_text(
        """version: 1
name: fail_missing
nodes:
  r:
    op: standard_io/files:BundleDirectory
    inputs:
      file_a: missing_file.txt
""",
        encoding="utf-8",
    )
    res_fail = runner.invoke(
        cli_main,
        ["run", str(wf_fail), "--non-interactive"],
    )
    assert res_fail.exit_code == 1, res_fail.output
    assert "run_id:" in res_fail.output


# ---------------------------------------------------------------------------
# R1.4: Separate stage input gates from stage approval gates
# ---------------------------------------------------------------------------


def _stage_with_both_input_and_approval() -> Workflow:
    return Workflow.model_validate(
        {
            "version": 1,
            "name": "both_gates_flow",
            "stages": {
                "s1": {"title": "Stage One", "require_approval": True},
                "s2": {"title": "Stage Two", "require_approval": False},
            },
            "nodes": {
                "n1": {
                    "op": "standard_io/text:Concat",
                    "stage": "s1",
                    "inputs": {"b": "_suffix"},
                },
                "n2": {
                    "op": "standard_io/demo:Echo",
                    "stage": "s2",
                    "inputs": {"text": "$n1.text"},
                },
            },
        }
    )


def test_r14_stage_with_both_deferred_input_and_require_approval_cli_callbacks(
    tmp_path: Path,
) -> None:
    """Accept R1.4 (CLI): stage with deferred input + require_approval prompts and resolves both."""
    store = RunStore(tmp_path)
    scheduler = Scheduler(store, LocalExecutor(tmp_path))
    wf = _stage_with_both_input_and_approval()

    # Terminal callbacks reading from simulated stdin: first the input value, then 'y' to approve
    input_stream = io.StringIO("hello\ny\n")
    prompt_lock = asyncio.Lock()

    input_calls: list[tuple[str, list[str]]] = []
    approval_calls: list[str] = []

    raw_inputs_cb = make_terminal_stage_inputs_callback(
        input_stream=input_stream,
        prompt_lock=prompt_lock,
    )
    raw_approval_cb = make_terminal_stage_approval_callback(
        input_stream=input_stream,
        prompt_lock=prompt_lock,
    )

    async def _wrapped_inputs_cb(
        stage_id: str,
        title: str,
        missing: list[WorkflowInputSpec],
    ) -> dict[str, Any] | None:
        input_calls.append((stage_id, [f"{m.node_id}.{m.name}" for m in missing]))
        return await raw_inputs_cb(stage_id, title, missing)

    async def _wrapped_approval_cb(stage_id: str, title: str) -> bool:
        approval_calls.append(stage_id)
        return await raw_approval_cb(stage_id, title)

    final_state = asyncio.run(
        scheduler.run(
            wf,
            options=SchedulerOptions(
                no_cache=True,
                poll_interval=0.01,
                stage_inputs_callback=_wrapped_inputs_cb,
                stage_approval_callback=_wrapped_approval_cb,
            ),
        )
    )

    assert final_state.status == RunStatus.SUCCESS
    assert final_state.nodes["n1"].status == NodeStatus.SUCCESS
    assert final_state.nodes["n2"].status == NodeStatus.SUCCESS
    assert input_calls == [("s1", ["n1.a"])]
    assert approval_calls == ["s1"]

    # Both gate rows exist distinctly in SQLite
    all_gates = store.list_stage_gates(final_state.id)
    assert {(g.stage_id, g.kind, g.status) for g in all_gates} == {
        ("s1", StageGateKind.INPUT, StageGateStatus.APPROVED),
        ("s1", StageGateKind.APPROVAL, StageGateStatus.APPROVED),
    }

    # Event log contains distinct input and approval events
    events = store.event_log(final_state.id).read_after(0)
    approval_events = [
        (ev.data.stage_id, ev.data.kind) for ev in events if isinstance(ev, StageApprovalEvent)
    ]
    resolved_events = [
        (ev.data.stage_id, ev.data.kind) for ev in events if isinstance(ev, StageResolvedEvent)
    ]
    assert approval_events == [
        ("s1", StageGateKind.INPUT),
        ("s1", StageGateKind.APPROVAL),
    ]
    assert resolved_events == [
        ("s1", StageGateKind.INPUT),
        ("s1", StageGateKind.APPROVAL),
    ]


def test_r14_stage_with_both_deferred_input_and_require_approval_rest_api(
    tmp_path: Path,
) -> None:
    """Accept R1.4 (REST/SSE): stage with deferred input + require_approval resolves both via API."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(parents=True)
    wf_file = wf_dir / "both_gates.yaml"
    wf_file.write_text(
        """version: 1
name: both_gates
stages:
  s1:
    title: "Stage 1"
    require_approval: true
  s2:
    title: "Stage 2"
nodes:
  n1:
    op: standard_io/text:Concat
    stage: s1
    inputs:
      b: "_end"
  n2:
    op: standard_io/demo:Echo
    stage: s2
    inputs:
      text: $n1.text
""",
        encoding="utf-8",
    )

    app = create_app(tmp_path, executor_factory=lambda _: FakeExecutor())

    async def _run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/runs",
                json={"workflow_path": "workflows/both_gates.yaml", "inputs": {}},
            )
            assert res.status_code == 201
            run_id = res.json()["run_id"]

            # 1. Wait for INPUT gate on s1
            deadline = time.monotonic() + 10.0
            got_input_gate = False
            while time.monotonic() < deadline:
                st = (await client.get(f"/runs/{run_id}")).json()
                gate = st["stage_gates"].get("s1")
                if (
                    st["status"] == "WAITING_FOR_USER"
                    and gate is not None
                    and gate["kind"] == "input"
                    and gate["status"] == "WAITING"
                ):
                    got_input_gate = True
                    break
                await asyncio.sleep(0.02)
            assert got_input_gate is True

            # Submit deferred input via /inputs
            inp_res = await client.post(
                f"/runs/{run_id}/stages/s1/inputs",
                json={"inputs": {"n1.a": "start"}},
            )
            assert inp_res.status_code == 200, inp_res.text

            # 2. Wait for APPROVAL gate on s1 (after n1 succeeds, before n2 runs)
            deadline = time.monotonic() + 10.0
            got_approval_gate = False
            while time.monotonic() < deadline:
                st = (await client.get(f"/runs/{run_id}")).json()
                gate = st["stage_gates"].get("s1")
                if (
                    st["status"] == "WAITING_FOR_USER"
                    and st["nodes"]["n1"]["status"] == "SUCCESS"
                    and st["nodes"]["n2"]["status"] == "PENDING"
                    and gate is not None
                    and gate["kind"] == "approval"
                    and gate["status"] == "WAITING"
                ):
                    got_approval_gate = True
                    break
                await asyncio.sleep(0.02)
            assert got_approval_gate is True

            # Approve stage s1 via /approve
            app_res = await client.post(f"/runs/{run_id}/stages/s1/approve")
            assert app_res.status_code == 200, app_res.text

            # 3. Wait for run to finish with SUCCESS
            deadline = time.monotonic() + 10.0
            finished = False
            while time.monotonic() < deadline:
                st = (await client.get(f"/runs/{run_id}")).json()
                if st["status"] == "SUCCESS":
                    finished = True
                    break
                await asyncio.sleep(0.02)
            assert finished is True

            # 4. Verify SSE stream replays both input and approval gate events
            sse_res = await client.get(f"/runs/{run_id}/stream")
            assert sse_res.status_code == 200
            body = sse_res.text
            assert '"kind": "input"' in body or '"kind":"input"' in body
            assert '"kind": "approval"' in body or '"kind":"approval"' in body

    asyncio.run(_run())
