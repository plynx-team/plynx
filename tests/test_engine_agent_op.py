"""Integration tests for Phase 3 (FEAT-AGT-1b) in ``plynx``:
- 4-level ``provider`` and ``model`` resolution & ``plynx-cache-1`` cache-key invalidation
- ``agent_concurrency`` semaphore separate from CPU ``concurrency``
- End-to-end ``Scheduler`` + ``LocalExecutor`` execution with 0-token checkpoint replay
- ``PackRegistry`` ``agent.models`` suggestions, CLI ``--agent-provider``/``--agent-model``,
  and FastAPI ``GET /runs/{run_id}/nodes/{node_id}/agent-turns``
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from plynx.cli import main as cli_main
from plynx.config import load_workspace_config, resolve_effective_agent_config
from plynx.engine import LocalExecutor, Scheduler, SchedulerOptions
from plynx.registry import PackRegistry
from plynx.server import create_app
from plynx.store import RunStore
from plynx.workflow.models import parse_workflow_yaml
from plynx_sdk.protocol import AgentProvider, AgentTurnsManifest, InputsManifest


def _create_agent_custom_pack(workspace: Path) -> Path:
    """Create a stdlib-only custom pack defining Choice A and Choice B AgentOps."""
    pack_dir = workspace / "custom_packs" / "agent_demo"
    src_dir = pack_dir / "src" / "agent_demo"
    src_dir.mkdir(parents=True, exist_ok=True)
    sdk_root = Path(__file__).resolve().parent.parent / "packages" / "plynx-sdk"
    (pack_dir / "pyproject.toml").write_text(
        '[project]\nname = "agent-demo"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["plynx-sdk"]\n\n'
        "[tool.uv.sources]\n"
        f'plynx-sdk = {{ path = "{sdk_root.as_posix()}", editable = true }}\n\n'
        "[build-system]\n"
        'requires = ["uv_build>=0.9.0,<0.10"]\n'
        'build-backend = "uv_build"\n\n'
        "[tool.uv.build-backend]\n"
        'module-name = "agent_demo"\n',
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "ops.py").write_text(
        "from pathlib import Path\n"
        "import time\n"
        "from typing import Any, TypedDict\n"
        "from plynx_sdk import AgentOp, AgentProviderLiteral, MarkdownFile\n\n"
        "class ChoiceASummarizer(AgentOp):\n"
        '    """Summarize input notes with an agent."""\n'
        '    TITLE = "Choice A Summarizer"\n'
        '    CATEGORY = "Agents"\n\n'
        "    class Outputs(TypedDict):\n"
        "        report: MarkdownFile\n"
        "        used_model: str\n\n"
        "class SlowMockAgent(AgentOp):\n"
        '    """Sleep briefly inside run() while tracking active concurrency on disk."""\n'
        '    TITLE = "Slow Mock Agent"\n'
        "    CACHEABLE = False\n\n"
        "    class Outputs(TypedDict):\n"
        "        peak_seen: int\n\n"
        "    def run(\n"
        "        self,\n"
        "        tracker_dir: str,\n"
        "        prompt_file: MarkdownFile | None = None,\n"
        "        prompt: str = '',\n"
        "        provider: AgentProviderLiteral = 'default',\n"
        "        model: str = '',\n"
        "        **extra: Any,\n"
        "    ) -> Outputs:\n"
        "        tdir = Path(tracker_dir)\n"
        "        my_token = tdir / f'active_{id(self)}_{time.time_ns()}'\n"
        "        my_token.write_text('1', encoding='utf-8')\n"
        "        try:\n"
        "            peaks: list[int] = []\n"
        "            for _ in range(8):\n"
        "                peaks.append(len(list(tdir.glob('active_*'))))\n"
        "                time.sleep(0.03)\n"
        "            res = self.run_agent(\n"
        "                prompt=prompt or 'check',\n"
        "                provider=provider,\n"
        "                model=model,\n"
        "                mock_responses={'status': 'completed', 'outputs': {'peak_seen': max(peaks)}},\n"
        "            )\n"
        "            return {'peak_seen': int(res['peak_seen'])}\n"
        "        finally:\n"
        "            my_token.unlink(missing_ok=True)\n",
        encoding="utf-8",
    )
    return pack_dir


def test_four_level_provider_and_model_precedence(tmp_path: Path) -> None:
    """Verify 4-level precedence: plynx.yaml < workflow.yaml < CLI flag < node input < --set."""
    (tmp_path / "plynx.yaml").write_text(
        "agent:\n"
        "  provider: claude\n"
        "  model: claude-sonnet-4-5\n"
        "  agent_concurrency: 3\n"
        "  models:\n"
        "    - claude-sonnet-4-5\n"
        "    - gpt-5\n",
        encoding="utf-8",
    )
    cfg = load_workspace_config(tmp_path)
    assert cfg.agent_provider == AgentProvider.CLAUDE
    assert cfg.agent_model == "claude-sonnet-4-5"
    assert cfg.agent_concurrency == 3
    assert cfg.agent_models == ["claude-sonnet-4-5", "gpt-5"]

    # Level 1: plynx.yaml wins when everything else is default/empty
    assert resolve_effective_agent_config(
        workspace_config=cfg,
        node_provider="default",
        node_model="",
        env={},
    ) == ("claude", "claude-sonnet-4-5")

    # Level 2: workflow.yaml overrides plynx.yaml
    assert resolve_effective_agent_config(
        workspace_config=cfg,
        workflow_provider="cursor",
        workflow_model="cursor-fast",
        node_provider="default",
        node_model="",
        env={},
    ) == ("cursor", "cursor-fast")

    # Level 3: CLI --agent-provider / --agent-model overrides workflow.yaml when node uses default
    assert resolve_effective_agent_config(
        workspace_config=cfg,
        workflow_provider="cursor",
        workflow_model="cursor-fast",
        cli_provider="codex",
        cli_model="gpt-5",
        node_provider="default",
        node_model="",
        env={},
    ) == ("codex", "gpt-5")

    # Level 4: Explicit non-default node input in YAML wins over CLI --agent-provider
    assert resolve_effective_agent_config(
        workspace_config=cfg,
        workflow_provider="cursor",
        workflow_model="cursor-fast",
        cli_provider="mock",
        cli_model="gpt-5",
        node_provider="gemini",
        node_model="gemini-2.5-pro",
        env={},
    ) == ("gemini", "gemini-2.5-pro")

    # --set node.provider / --set node.model overrides node input in YAML
    assert resolve_effective_agent_config(
        workspace_config=cfg,
        workflow_provider="cursor",
        workflow_model="cursor-fast",
        cli_provider="codex",
        cli_model="gpt-5",
        node_provider="gemini",
        node_model="gemini-2.5-pro",
        set_provider="mock",
        set_model="mock-override",
        env={},
    ) == ("mock", "mock-override")


def test_pack_registry_attaches_model_suggestions_from_plynx_yaml(tmp_path: Path) -> None:
    """PackRegistry attaches agent.models from plynx.yaml as suggestions on AgentOp model ports."""
    _create_agent_custom_pack(tmp_path)
    (tmp_path / "plynx.yaml").write_text(
        "packs:\n  - custom_packs\nagent:\n  models:\n    - sonnet-4.5\n    - gpt-5\n",
        encoding="utf-8",
    )
    reg = PackRegistry(tmp_path)
    op_entry = reg.get("agent_demo/ops:ChoiceASummarizer")
    assert op_entry is not None
    assert op_entry.valid is True
    assert op_entry.agent_role == "agent"
    model_port = next(p for p in op_entry.inputs if p.name == "model")
    assert model_port.suggestions == ["sonnet-4.5", "gpt-5"]


def test_e2e_agent_op_checkpoint_replay_cache_invalidation_and_rest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end CLI/Engine/REST test: 0-token replay, cache invalidation on model change, and /agent-turns."""
    _create_agent_custom_pack(tmp_path)
    (tmp_path / ".plynx").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workflows").mkdir(parents=True, exist_ok=True)
    (tmp_path / "plynx.yaml").write_text(
        "workflows: workflows\npacks:\n  - custom_packs\nagent:\n  provider: mock\n  model: m-v1\n",
        encoding="utf-8",
    )

    mock_script = tmp_path / "mock_turns.json"
    mock_script.write_text(
        json.dumps(
            {
                "summarize": [
                    {
                        "status": "needs_input",
                        "session_id": "e2e_sid_1",
                        "questions": [
                            {
                                "id": "tone",
                                "question": "Select summary tone",
                                "options": ["concise", "detailed"],
                                "allow_freeform": False,
                            }
                        ],
                    },
                    {
                        "status": "completed",
                        "session_id": "e2e_sid_1",
                        "outputs": {
                            "report": "# Concise Report\n\nVerified.",
                            "used_model": "ok",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(mock_script))
    monkeypatch.chdir(tmp_path)

    wf_file = tmp_path / "workflows" / "summarize.yaml"
    wf_file.write_text(
        "version: 1\n"
        "name: summarize\n"
        "nodes:\n"
        "  summarize:\n"
        "    op: agent_demo/ops:ChoiceASummarizer\n"
        "    inputs:\n"
        "      prompt: 'Summarize these notes'\n"
        "      notes: 'Latency dropped 40%'\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    # 1. Non-interactive run hits Turn 0 needs_input -> exits 2 (WAITING_FOR_USER)
    res1 = runner.invoke(cli_main, ["run", "--non-interactive", str(wf_file)])
    assert res1.exit_code == 2

    store = RunStore(tmp_path)
    runs = store.list_runs(limit=5)
    assert len(runs) == 1
    run_id = runs[0].id

    # Verify effective provider & model were materialized into inputs.json before cache key
    inputs_disk = InputsManifest.from_json(
        (store.node_dir(run_id, "summarize") / "inputs.json").read_bytes()
    )
    assert inputs_disk.inputs["provider"].to_dict() == {"kind": "scalar", "value": "mock"}
    assert inputs_disk.inputs["model"].to_dict() == {"kind": "scalar", "value": "m-v1"}

    # Mutate mock_turns.json Turn 0 to INVALID status to prove Attempt 2 replays Turn 0 from
    # agent_turns.json rather than re-reading Turn 0 from the mock provider!
    mock_script.write_text(
        json.dumps(
            {
                "summarize": [
                    {"status": "INVALID_IF_RE_EXECUTED"},
                    {
                        "status": "completed",
                        "session_id": "e2e_sid_1",
                        "outputs": {
                            "report": "# Concise Report\n\nVerified.",
                            "used_model": "ok",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    # 2. Resume with batch answer -> replays Turn 0 in 0 tokens, runs Turn 1, exits 0!
    res2 = runner.invoke(
        cli_main,
        [
            "resume",
            run_id,
            "--non-interactive",
            "--answer",
            "summarize.cp_0.tone=concise",
        ],
    )
    assert res2.exit_code == 0, res2.output

    turns_disk = AgentTurnsManifest.from_json(
        (store.node_dir(run_id, "summarize") / "agent_turns.json").read_bytes()
    )
    assert len(turns_disk.turns) == 2
    assert turns_disk.turns[0].user_answers == {"tone": "concise"}
    assert turns_disk.turns[1].status.value == "completed"

    # 3. Verify GET /api/v1/runs/{run_id}/nodes/{node_id}/agent-turns REST endpoint
    app = create_app(tmp_path)
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/runs/{run_id}/nodes/summarize/agent-turns")
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema"] == 1
        assert len(body["turns"]) == 2
        assert body["turns"][0]["session_id"] == "e2e_sid_1"
        assert body["turns"][0]["user_answers"] == {"tone": "concise"}
        assert body["turns"][1]["status"] == "completed"

    # 4. Verify cache hit vs cache invalidation when --agent-model changes
    single_turn_script = tmp_path / "single_turn.json"
    single_turn_script.write_text(
        json.dumps(
            {
                "status": "completed",
                "outputs": {"report": "# Cached Report\n", "used_model": "m1"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLYNX_MOCK_AGENT_RESPONSES", str(single_turn_script))

    r_fresh = runner.invoke(
        cli_main,
        ["run", "--non-interactive", "--agent-model", "model-alpha", str(wf_file)],
    )
    assert r_fresh.exit_code == 0
    fresh_id = store.list_runs(limit=1)[0].id
    fresh_state = store.get_run_state(fresh_id)
    assert fresh_state is not None
    assert fresh_state.nodes["summarize"].cache_hit is False

    # Same model -> cache hit!
    r_hit = runner.invoke(
        cli_main,
        ["run", "--non-interactive", "--agent-model", "model-alpha", str(wf_file)],
    )
    assert r_hit.exit_code == 0
    hit_id = store.list_runs(limit=1)[0].id
    hit_state = store.get_run_state(hit_id)
    assert hit_state is not None
    assert hit_state.nodes["summarize"].cache_hit is True

    # Different --agent-model -> cache invalidated (cache_hit is False)!
    r_miss = runner.invoke(
        cli_main,
        ["run", "--non-interactive", "--agent-model", "model-beta", str(wf_file)],
    )
    assert r_miss.exit_code == 0
    miss_id = store.list_runs(limit=1)[0].id
    miss_state = store.get_run_state(miss_id)
    assert miss_state is not None
    assert miss_state.nodes["summarize"].cache_hit is False


def test_agent_concurrency_semaphore_limits_parallel_agent_ops(tmp_path: Path) -> None:
    """agent_concurrency=1 serializes AgentOp executions even when CPU concurrency=4."""
    _create_agent_custom_pack(tmp_path)
    tracker_dir = tmp_path / "tracker"
    tracker_dir.mkdir(parents=True)
    (tmp_path / "plynx.yaml").write_text(
        "packs:\n  - custom_packs\nconcurrency: 4\nagent:\n  provider: mock\n  agent_concurrency: 1\n",
        encoding="utf-8",
    )

    wf_yaml = (
        "version: 1\n"
        "name: parallel_agents\n"
        "concurrency: 4\n"
        "nodes:\n"
        "  a1:\n"
        "    op: agent_demo/ops:SlowMockAgent\n"
        f"    inputs:\n      tracker_dir: {tracker_dir.as_posix()!r}\n"
        "  a2:\n"
        "    op: agent_demo/ops:SlowMockAgent\n"
        f"    inputs:\n      tracker_dir: {tracker_dir.as_posix()!r}\n"
        "  a3:\n"
        "    op: agent_demo/ops:SlowMockAgent\n"
        f"    inputs:\n      tracker_dir: {tracker_dir.as_posix()!r}\n"
    )
    wf = parse_workflow_yaml(wf_yaml)
    store = RunStore(tmp_path)
    reg = PackRegistry(tmp_path)
    executor = LocalExecutor(tmp_path)
    scheduler = Scheduler(store, executor, reg)

    t0 = time.monotonic()
    final_state = asyncio.run(
        scheduler.run(
            wf,
            workflow_bytes=wf_yaml.encode("utf-8"),
            options=SchedulerOptions(concurrency=4, non_interactive=True),
        )
    )
    _ = time.monotonic() - t0
    assert final_state.status.value == "SUCCESS"

    for nid in ("a1", "a2", "a3"):
        res_json = json.loads(
            (store.node_dir(final_state.id, nid) / "result.json").read_text(encoding="utf-8")
        )
        assert res_json["outputs"]["peak_seen"]["value"] == 1
