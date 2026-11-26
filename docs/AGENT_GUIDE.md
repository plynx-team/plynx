# PLynx User Agent Reference

Self-contained reference for AI coding agents working in a PLynx workspace. Print this guide anytime with `plynx agent-guide`.

## 1. Quick Workflow Loop

```bash
# 1. Initialize workspace (creates .plynx/, workflows/, custom_packs/, plynx.yaml)
plynx init

# 2. Inspect all available operations and exact port schemas (always do this first)
plynx ops --json

# 3. Validate a workflow statically (no code executed; exit 0 = ok, 1 = issues)
plynx validate workflows/my_flow.yaml

# 4. Run a workflow (use --non-interactive in automated sessions)
plynx run --non-interactive workflows/my_flow.yaml

# 5. Inspect runs and logs
plynx runs
plynx runs <run_id>
```

## 2. CLI Commands & Exit Codes

| Command | Purpose |
| :--- | :--- |
| `plynx init [dir]` | Initialize `.plynx/`, `workflows/`, `custom_packs/`, `plynx.yaml`, `.gitignore`. |
| `plynx ops [--json]` | List discovered built-in (`standard_io`) and custom ops. Use `--json` for full port schemas. |
| `plynx validate <workflow.yaml>` | Statically validate schema, DAG cycles, op IDs, port types/media, stage order, and `uv.lock`. |
| `plynx run <workflow.yaml> [opts]` | Execute a workflow. Options: `--set node.port=val` (scalars), `--input node.port=path` (files/dirs), `--answer node.cp_n=val`, `--answers file.json`, `--concurrency N`, `--agent-provider <p>`, `--agent-model <m>`, `--non-interactive`, `--no-cache`. |
| `plynx resume <run_id> [opts]` | Continue a failed, canceled, or waiting run, reusing completed node outputs. Options: `--answer`, `--answers`, `--concurrency`, `--agent-provider`, `--agent-model`, `--non-interactive`. |
| `plynx run-node <node_dir> [--op <op>]` | Re-run a single node attempt in a scratch copy without touching SQLite or the original directory. Streams stdout/stderr and exits with the child exit code. |
| `plynx runs [run_id] [--limit N]` | List recent runs or inspect one run by ID or unique prefix. |
| `plynx clean [--days 14] [--dry-run]` | Delete old unpinned runs and unreferenced cache blobs. |
| `plynx ui [--port 8080] [--host 127.0.0.1] [--no-browser]` | Start local web UI and REST/SSE API. |
| `plynx agent-guide` | Print this reference to stdout. |

Exit codes for `plynx run` and `plynx resume`:
- `0`: `SUCCESS`
- `1`: `FAILED` (or CLI/validation error)
- `2`: `WAITING_FOR_USER` (blocked on a checkpoint, missing input, or stage approval gate in `--non-interactive` mode)
- `130`: `CANCELED`

## 3. `workflow.yaml` Schema

```yaml
version: 1
name: example_flow
stages:
  prepare:
    title: "1. Prepare"
    require_approval: false
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
- `stages` is an optional top-level mapping (`stage_id: { title?, require_approval? }`). Edges must stay in the same stage or point to a later stage.
- `op` is `<pack>/<module>:<Name>` (copy the exact `id` from `plynx ops --json`).
- `inputs` values:
  - Wiring reference: `$<node_id>.<output_name>` or `{ from_node: <node_id>, output: <output_name> }`.
  - Literal: YAML scalar, list, or mapping. For `file`/`directory` ports, strings are workspace-relative paths.
  - Literal starting with `$`: escape with `$$` (e.g. `$$PATH`).
- Any required input port omitted from `inputs:` becomes an unbound run input: pass scalars with `--set node.port=value` and files/directories with `--input node.port=path`.

## 4. Debugging Failed Nodes

1. Inspect the run and stderr log:
   ```bash
   plynx runs <run_id>
   cat .plynx/runs/<run_id>/logs/<node_id>.stderr.log
   ```
2. Reproduce in an isolated scratch copy (does not modify SQLite or run files):
   ```bash
   plynx run-node .plynx/runs/<run_id>/nodes/<node_id>
   ```
3. Edit the op's Python source, re-run `plynx run-node` until it exits `0`, then continue the workflow without re-running finished upstream nodes:
   ```bash
   plynx resume <run_id>
   ```

## 5. Adding a Custom Node Pack

Create `custom_packs/<pack_name>/` with `pyproject.toml`, `uv.lock` (`cd custom_packs/<pack_name> && uv lock`), and `src/<pack_name>/<module>.py`. Packs depend on `plynx-sdk` (never `plynx`).

```python
"""Custom text op example."""

from pathlib import Path
from typing import Annotated, Literal, TypedDict

from plynx_sdk import Directory, Media, Op, Range, TextFile, op

CsvReport = Annotated[Path, Media("text/csv")]


class WrapText(Op):
    """Wrap text with a prefix and write it to a file."""

    TITLE = "Wrap Text"
    CATEGORY = "Custom"
    CACHEABLE = True

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
- **Static AST discovery**: `TITLE`, `CATEGORY`, `CACHEABLE`, `ALLOW_EXTRA_INPUTS`, `@op(...)` arguments, and port defaults must be plain literals. Verify with `plynx ops --json` (`"valid": true`).
- **Class `Op` inputs**: Declare input ports as parameters of `run(self, ...)` (not class attributes) and outputs as `class Outputs(TypedDict):`.
- **Variadic inputs**: Set `ALLOW_EXTRA_INPUTS = True` (or `@op(..., allow_extra_inputs=True)`) and add `**extra: <Type>` to `run()`.
- **Filesystem rules**: Inputs are read-only; write outputs only inside `workdir/` (current working directory) and return relative `Path` objects. Keep JSON/scalar outputs under 1 MiB.
- **Checkpoints**: `self.checkpoint(question, options=[...], allow_freeform=False)` replays the node from the start of `run()` once answered. Keep work before `checkpoint()` idempotent and never catch `BaseException` around it.
- **Batch checkpoints**: when you need several answers, ask once with `self.checkpoint_batch([CheckpointQuestion(id="role", question="Target track?", options=["ML", "Backend"]), {"id": "skills", "question": "Skills?", "options": [...], "multi_select": True}])`. It returns `{id: str | list[str]}` (`list[str]` for `multi_select`). The id `default` is reserved. Supply answers in non-interactive runs with `--answers file.json` (`{"node.cp_0": {"role": "ML", "skills": ["sql"]}}`) or `--answer node.cp_0.role=ML` (repeat the flag for a `multi_select` list).
- **Warnings**: call `self.warn("message")` (or `plynx_sdk.warn(...)` in `@op` functions) for a non-fatal data anomaly. The op still exits 0; the messages are stored in `warnings` of `outputs.json` and `result.json`.
- **Agent operations (`AgentOp`)**: Subclass `AgentOp` (defaults `ALLOW_EXTRA_INPUTS = True`) either without overriding `run()` (Choice A: inherits `prompt_file`, `prompt`, `provider`, `model`, `**extra` and materializes `class Outputs(TypedDict)` automatically) or with an explicit `def run(...)` calling `self.run_agent(...)` / `self.agent_turn(...)` (Choice B). Turns record to `nodes/<node_id>/agent_turns.json` so answering a `checkpoint_batch()` replays prior turns in 0 tokens.
- **Caching**: Cache keys hash op entrypoint, op source file bytes, pack `uv.lock`, input hashes, scalar params, and checkpoint answers (not shared helper files or env vars). Run `plynx run --no-cache` after editing shared helpers; set `CACHEABLE = False` for non-deterministic ops.
