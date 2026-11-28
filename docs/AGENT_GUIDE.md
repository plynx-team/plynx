# PLynx User Agent Reference

Self-contained reference for AI coding agents working in a PLynx workspace. Print this guide anytime with `plynx agent-guide`.

## 1. Quick Workflow Loop

```bash
# 1. Initialize workspace (creates .plynx/, workflows/, custom_packs/, plynx.yaml, .agents/skills/)
plynx init

# 2. Inspect all available operations and exact port schemas (always do this first)
plynx ops --json

# 3. Validate a workflow statically (no code executed; exit 0 = ok, 1 = issues)
plynx validate workflows/my_flow.yaml

# 4. Run a workflow (use --non-interactive in automated sessions)
plynx run --non-interactive workflows/my_flow.yaml

# 5. Inspect runs, logs, and execution telemetry
plynx runs
plynx runs <run_id>
plynx runs --stats
```

## 2. CLI Commands & Exit Codes

| Command | Purpose |
| :--- | :--- |
| `plynx init [dir]` | Initialize `.plynx/`, `workflows/`, `custom_packs/`, `plynx.yaml`, `.agents/skills/plynx-create-workflow/SKILL.md`, and `.gitignore`. |
| `plynx ops [--json]` | List discovered built-in (`standard_io`) and custom ops. Use `--json` for full port schemas. |
| `plynx validate <workflow.yaml>` | Statically validate schema, DAG cycles, op IDs, port types/media, stage validators, stage order, and `uv.lock`. |
| `plynx run <workflow.yaml> [opts]` | Execute a workflow. Options: `--set node.port=val` (scalars), `--input node.port=path` (files/dirs), `--answer node.cp_n=val`, `--answers file.json`, `--concurrency N`, `--agent-provider <p>`, `--agent-model <m>`, `--max-injected-nodes N`, `--non-interactive`, `--no-cache`. |
| `plynx resume <run_id> [opts]` | Continue a failed, canceled, or waiting run, reusing completed node outputs and validating any edits made to `.plynx/runs/<run_id>/workflow.snapshot.yaml`. Options: `--answer`, `--answers`, `--concurrency`, `--agent-provider`, `--agent-model`, `--max-injected-nodes N`, `--non-interactive`. |
| `plynx run-node <node_dir> [--op <op>] [--allow-side-effects]` | Re-run a single node attempt in a scratch copy without touching SQLite or the original directory. Blocks `side_effects: "write"` ops unless `--allow-side-effects` is passed after user confirmation. |
| `plynx runs [run_id] [--limit N] [--workflow PATH] [--stats] [--json]` | List recent runs (with `[DRIFT]` alerts), inspect one run by ID or unique prefix, or report per-node execution stats, cache-hit rates, and dynamic injections (`--stats`). |
| `plynx clean [--days 14] [--dry-run]` | Delete old unpinned runs and unreferenced cache blobs. |
| `plynx ui [--port 8080] [--host 127.0.0.1] [--no-browser]` | Start local web UI and REST/SSE API. |
| `plynx agent-guide` | Print this reference to stdout. |

Exit codes for `plynx run` and `plynx resume`:
- `0`: `SUCCESS`
- `1`: `FAILED` (or CLI/validation error)
- `2`: `WAITING_FOR_USER` (blocked on a checkpoint, missing input, patch approval, or stage approval gate in `--non-interactive` mode)
- `130`: `CANCELED`

## 3. Workflow Design & Granularity Heuristics

Follow these heuristics when designing or refactoring PLynx workflows:

1. **Reuse Before Authoring (`plynx ops --json` first)**: Always inspect built-in `standard_io` ops (including `standard_io/agent:AgentPrompt` and `standard_io/agent:StageSupervisor`) and existing `custom_packs/` ops before writing new Python ops.
2. **Context-Free, Honest Operations (Never Overfit to One Workflow)**: Outside automated tests, never hardcode workflow-specific strings, lookup tables, questions, or toy heuristics inside an op. Parameterize domain specifics via input ports, and use real libraries in isolated Node Packs (`uv.lock`) or `AgentOp` for general tasks. Every op's `TITLE` and docstring must be 100% accurate: if an op claims to detect languages or translate text, it must genuinely do so for any input.
3. **Goldilocks Granularity (Typically 3–8 Nodes Across 2–4 Stages)**: Never write a 1-node monolith script (which defeats Stepper visibility and intermediate CAS caching), and never create 25 tiny 2-line micro-nodes (which adds UI clutter and subprocess startup overhead). Each node should represent one coherent, human-understandable step.
4. **Cache-Boundary Splitting**: Separate expensive or slow steps (`AgentOp` LLM calls, PDF parsing, media rendering, network I/O) from fast deterministic formatting so downstream tweaks hit `plynx-cache-1` in 0 ms.
5. **Declare `SIDE_EFFECTS` & Isolate External Writes Behind Approval Gates**: Separate preview/fetch steps (`SIDE_EFFECTS = SideEffect.NONE` or `SideEffect.READ`) from external mutations (`SIDE_EFFECTS = SideEffect.WRITE`, which automatically sets `CACHEABLE = False`: sending emails/messages, `HttpPostJson`, `git push`, DB/API writes) instead of overloading one op with a `dry_run` flag. Group `WRITE` ops into a dedicated final stage with `require_approval: true` on the preceding stage so `--non-interactive` runs stop (`exit 2`) before touching external systems (`plynx validate` warns if unguarded).
6. **Safe Debugging by `side_effects` (`plynx ops --json`)**: When refactoring ops or debugging workflows, inspect historical `.plynx/runs/<run_id>/nodes/<node_id>/{inputs.json,result.json}` and `logs/` **read-only**, run `plynx validate`, and check each op's `side_effects` field:
   - `"none"`: pure local `workdir/` op — safe to test and replay freely with `plynx run` and `plynx run-node`.
   - `"read"`: external read-only query or `AgentOp` — safe from external mutations (mock network calls in `pytest`; avoid unnecessary batch replays on paid APIs/LLMs).
   - `"write"`: mutates external state — `plynx run-node` blocks execution by default (`exit 1`), and `allow_graph_edits: auto` downgrades to `confirm`. **Never** pass `--allow-side-effects` or approve a pre-write stage gate without explicit human confirmation.

## 4. `workflow.yaml` Schema

```yaml
version: 1
name: example_flow
stages:
  prepare:
    title: "1. Prepare"
    require_approval: false
    validator:
      op: standard_io/agent:StageSupervisor
      mode: on_anomaly
      allow_graph_edits: confirm
      inputs:
        prompt: "If any node emitted a warning, propose a bounded adapter splice before finish."
  finish:
    title: "2. Finish"
nodes:
  step_a:
    op: standard_io/demo:Echo
    stage: prepare
    inputs:
      text: "hello"
  step_b:
    op: standard_io/text:Concat
    stage: finish
    inputs:
      a: $step_a.text
      b: " world"
```

Rules:
- `nodes` is a top-level mapping of node IDs (`^[a-z][a-z0-9_]*$`). Never nest `nodes:` inside `stages:`.
- `stages` is an optional top-level mapping (`stage_id: { title?, require_approval?, validator? }`). Edges must stay in the same stage or point to a later stage.
- `stages.<stage_id>.validator` attaches a `StageValidatorOp` (such as `standard_io/agent:StageSupervisor`) materialized as reserved node `__stage_validator__<stage_id>`:
  - `mode`: `on_anomaly` (default; 0 ms skip unless a stage node calls `self.warn()` or fails), `on_failure`, or `always`.
  - `allow_graph_edits`: `confirm` (default; pauses for human `[Approve Patch / Reject]`), `auto`, or `forbidden`.
- `op` is `<pack>/<module>:<Name>` (copy the exact `id` from `plynx ops --json`).
- `inputs` values:
  - Wiring reference: `$<node_id>.<output_name>` or `{ from_node: <node_id>, output: <output_name> }`.
  - Literal: YAML scalar, list, or mapping. For `file`/`directory` ports, strings are workspace-relative paths.
  - Literal starting with `$`: escape with `$$` (e.g. `$$PATH`).
- Any required input port omitted from `inputs:` becomes an unbound run input: pass scalars with `--set node.port=value` and files/directories with `--input node.port=path`.

## 5. Agentic Execution, Credentials & Dynamic DAG Repair

- **Built-in Agent Ops**:
  - `standard_io/agent:AgentPrompt`: Choice A `AgentOp` accepting `prompt_file`, `prompt`, `provider`, `model`, and variadic `**extra` inputs, returning `response: MarkdownFile`.
  - `standard_io/agent:StageSupervisor`: `StageValidatorOp` inspecting `stage_context.json` (`outputs.json`, `warnings`, `stdout`/`stderr` tails, `workflow.snapshot.yaml`, and `plynx ops` schemas) and optionally proposing a bounded `graph_patch`.
- **Provider & Model Resolution** (lowest to highest precedence, written into `inputs.json` before `plynx-cache-1` hashing):
  1. `plynx.yaml` `agent: { provider, model, agent_concurrency, max_injected_nodes, models, custom_command }` (or `PLYNX_AGENT_PROVIDER` / `PLYNX_AGENT_MODEL`).
  2. `workflow.yaml` top-level `agent: { provider, model }`.
  3. CLI `--agent-provider` / `--agent-model`.
  4. Node input port `provider` / `model` (or `--set node.provider=...` / `--set node.model=...`).
- **Credentials**: Coding-agent CLIs (`claude`, `cursor-agent`, `codex`, `gemini`, `opencode`, `goose`, `aider`) use either their existing host CLI login session (inherited via `HOME`) or API keys in a gitignored workspace `.env` file (or host environment, controlled by `env_passthrough` in `plynx.yaml`). Never write secrets to workflows, snapshots, outputs, or logs. See `docs/guides/agentic_workflows.md` for per-provider setup details.
- **Dynamic DAG Reload & Outer-Agent Edits**:
  - Graph patches (or manual edits to `.plynx/runs/<run_id>/workflow.snapshot.yaml` while paused, followed by `plynx resume <run_id>`) are validated by `validate_snapshot_mutation`: static `plynx validate` passes, `SUCCESS`/`RUNNING` nodes are untouched, upstream lineage (`U -> [New Subgraph] -> V`) is preserved, and injected nodes stay within `max_injected_nodes` (default `3`).
  - Baseline `workflows/<name>.yaml` is never mutated automatically; recurring splices across runs trigger `[DRIFT]` alerts in `plynx runs` and `plynx runs --stats`.

## 6. Debugging Failed Nodes

1. Inspect the run and stderr log:
   ```bash
   plynx runs <run_id>
   cat .plynx/runs/<run_id>/logs/<node_id>.stderr.log
   ```
2. For `side_effects: "none"` (or `"read"`) ops, reproduce in an isolated scratch copy (does not modify SQLite or run files; `side_effects: "write"` ops are blocked by default unless `--allow-side-effects` is passed after user confirmation):
   ```bash
   plynx run-node .plynx/runs/<run_id>/nodes/<node_id>
   ```
3. Edit the op's Python source, re-run `plynx run-node` until it exits `0`, then continue the workflow without re-running finished upstream nodes:
   ```bash
   plynx resume <run_id>
   ```

## 7. Adding a Custom Node Pack

Create `custom_packs/<pack_name>/` with `pyproject.toml`, `uv.lock` (`cd custom_packs/<pack_name> && uv lock`), and `src/<pack_name>/<module>.py`. Packs depend on `plynx-sdk` (never `plynx`).

```python
"""Custom text op example."""

from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import Directory, Media, Op, Range, SideEffect, TextFile, op

CsvReport = Annotated[Path, Media("text/csv")]


class WrapText(Op):
    """Wrap text with a prefix and write it to a file."""

    TITLE = "Wrap Text"
    CATEGORY = "Custom"
    CACHEABLE = True
    SIDE_EFFECTS = SideEffect.NONE

    class Outputs(TypedDict):
        text: str
        out_file: TextFile

    def run(
        self,
        text: str,
        style: Literal["plain", "upper"] = "plain",
        repeat: Annotated[int, Range(1, 10, step=1)] = 1,
    ) -> Outputs:
        body = (text.upper() if style == "upper" else text) * repeat
        out = Path("wrapped.txt")
        out.write_text(body, encoding="utf-8")
        return {"text": body, "out_file": out}


@op(title="Count Files", category="Custom", cacheable=True)
def count_files(folder: Directory) -> int:
    """Count files in a directory."""
    return sum(1 for p in folder.rglob("*") if p.is_file())
```

Key pack authoring rules:
- **Static AST discovery**: `TITLE`, `CATEGORY`, `CACHEABLE`, `ALLOW_EXTRA_INPUTS`, `SIDE_EFFECTS`, `@op(...)` arguments, and port defaults must be plain literals (or `SideEffect.<MEMBER>`). Verify with `plynx ops --json` (`"valid": true`).
- **Side-effect classification (`SIDE_EFFECTS`)**: Set `SIDE_EFFECTS = SideEffect.NONE` (default) for pure `workdir/` ops, `SideEffect.READ` (with `CACHEABLE = False` when live freshness matters) for external read-only API/DB queries, and `SideEffect.WRITE` for external mutations (which defaults `CACHEABLE = False` and rejects `CACHEABLE = True`).
- **Class `Op` inputs**: Declare input ports as parameters of `run(self, ...)` (not class attributes) and outputs as `class Outputs(TypedDict):`.
- **Variadic inputs**: Set `ALLOW_EXTRA_INPUTS = True` (or `@op(..., allow_extra_inputs=True)`) and add `**extra: <Type>` to `run()`.
- **Filesystem rules**: Inputs are read-only; write outputs only inside `workdir/` (current working directory) and return relative `Path` objects. Keep JSON/scalar outputs under 1 MiB.
- **Checkpoints**: `self.checkpoint(question, options=[...], allow_freeform=False)` replays the node from the start of `run()` once answered. Keep work before `checkpoint()` idempotent and never catch `BaseException` around it.
- **Batch checkpoints**: when you need several answers, ask once with `self.checkpoint_batch([CheckpointQuestion(id="role", question="Target track?", options=["ML", "Backend"]), {"id": "skills", "question": "Skills?", "options": [...], "multi_select": True}])`. It returns `{id: str | list[str]}` (`list[str]` for `multi_select`). The id `default` is reserved. Supply answers in non-interactive runs with `--answers file.json` (`{"node.cp_0": {"role": "ML", "skills": ["sql"]}}`) or `--answer node.cp_0.role=ML` (repeat the flag for a `multi_select` list).
- **Warnings vs. failures**: call `self.warn("message")` (or `plynx_sdk.warn(...)` in `@op` functions) only for a non-fatal data anomaly where the op still produces valid output (`exit 0`); `warnings` are stored in `outputs.json`/`result.json` and trigger `on_anomaly` stage validators. If an op cannot fulfill its contract (e.g., missing tool/platform or corrupt input), raise an exception (`exit 1` `FAILED`) instead of returning fake fallback output—downstream stops and an `on_failure`/`on_anomaly` stage validator can inspect `stderr.log` and propose an alternative op.
- **Agent operations (`AgentOp` / `StageValidatorOp`)**: Subclass `AgentOp` (defaults `ALLOW_EXTRA_INPUTS = True`) either without overriding `run()` (Choice A: inherits `prompt_file`, `prompt`, `provider`, `model`, `**extra` and materializes `class Outputs(TypedDict)` automatically) or with an explicit `def run(...)` calling `self.run_agent(...)` / `self.agent_turn(...)` (Choice B). Turns record to `nodes/<node_id>/agent_turns.json` so answering a `checkpoint_batch()` replays prior turns in 0 tokens.
- **Caching**: Cache keys hash op entrypoint, op source file bytes, pack `uv.lock`, input hashes, scalar params (including resolved `provider` and `model`), and checkpoint answers (not shared helper files or env vars). Run `plynx run --no-cache` after editing shared helpers; set `CACHEABLE = False` for non-deterministic ops.
