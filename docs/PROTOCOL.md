# Protocol (PLynx v2.0.0)

Exact formats. Code must match this file. Change this file first, then the code, in the same commit. Schema version of every JSON manifest: `"schema": 1`.

## 1. Conventions

- Run ID: `YYYYMMDD_HHMMSS_<6 hex>` in UTC, e.g. `20261116_201500_a1b2c3`. It is the SQLite key and the run directory name. CLI accepts any unique prefix.
- Node ID: `^[a-z][a-z0-9_]*$` for user-declared nodes. At runtime, stage validators use the reserved ID `__stage_validator__<stage_id>` (`RUNTIME_NODE_ID_PATTERN`). Stage ID: `^[a-z][a-z0-9_]*$`, or `[a-zA-Z0-9][a-zA-Z0-9_-]*` when a validator is attached (see 2).
- JSON files: UTF-8, no BOM, `\n` newlines. Written atomically.
- Paths inside a node's manifests are relative to that node's directory (`.plynx/runs/<run_id>/nodes/<node_id>/`), use `/`, and never contain `..` or a drive letter. Paths in SQLite and `run_manifest.json` are relative to the workspace root.
- Times: UTC float seconds.
- Hash: lowercase hex SHA-256.

## 2. `workflow.yaml`

```yaml
version: 1
name: foo_or_woo               # optional, default: file stem
description: ""                # optional
concurrency: 4                 # optional
max_injected_nodes: 3          # optional cumulative dynamic-splice budget per run
agent:                         # optional workflow-level agent defaults
  provider: default            # AgentProvider
  model: ""                    # optional model override
  max_injected_nodes: 3        # optional alias when grouped under agent:
stages:                        # optional
  ask:
    title: "1. Ask"            # optional, default: stage id
    require_approval: false    # optional, default false
    validator:                 # optional StageValidatorSpec (runs as __stage_validator__ask)
      op: standard_io/agent:StageSupervisor
      mode: on_anomaly         # ValidatorMode: on_anomaly | on_failure | always
      allow_graph_edits: confirm # GraphEditPolicy: confirm | auto | forbidden
      inputs:
        prompt: "Inspect anomalies."
nodes:
  pick:
    op: standard_io/demo:AskFooOrWoo
    title: "Pick one"          # optional display override
    stage: ask                 # optional; default stage id "main", title "Workflow"
    inputs:
      prompt: "foo or woo?"
  echo:
    op: standard_io/demo:Echo
    stage: print
    inputs:
      text: $pick.choice
```

Rules:

- `op` is `<pack>/<module>:<Name>` (see 3). `Name` is a class name or a decorated function name.
- `stages.<stage_id>.validator`: optional stage-end supervisor (`StageValidatorOp` or `AgentOp`). Scheduled as reserved node `__stage_validator__<stage_id>` depending on all regular nodes in `<stage_id>`. `mode` defaults to `on_anomaly`; `allow_graph_edits` defaults to `confirm`.
- `nodes.<id>.allow_graph_edits`: optional `GraphEditPolicy` override (`forbidden | confirm | auto`), valid only on `AgentOp` nodes (defaults to the op class `ALLOW_GRAPH_EDITS`).
- `nodes.<id>.meta`: optional provenance mapping `{ injected_by?: str, reason?: str, superseded_by?: str }` written into `workflow.snapshot.yaml` when an agent or outer harness splices or supersedes nodes at runtime.
- `inputs` is one map for every port of the op (the old parameter/input split is gone). A value is one of:
  - a **reference**: the string `$<node_id>.<output_name>`, or the mapping `{ from_node: <node_id>, output: <output_name> }`;
  - a **literal**: any YAML scalar, list or mapping. For `Path` and `Directory` ports a string literal is a workspace-relative path;
  - an **escaped string**: a string starting with `$$` stands for the literal string with one `$` removed.
  - Any other string starting with `$` is a validation error.
- A port with no value and no default is a **run input**. The CLI (`--set`, `--input`) and the UI ask for it when the run starts.
- A stage listed in `stages:` keeps its order. Stage labels used only on nodes get the order of first appearance. Edges must stay in the same stage or go to a later stage.
- No coordinates, no sizes, no UI fields. Unknown top-level or node keys are a validation error.
- YAML is read and written with `ruamel.yaml` so comments and key order survive UI edits.

Layout sidecar `workflows/.<name>.layout.json` (UI-owned, engine ignores it, copied into the run snapshot; viewport coordinates are stored locally in the client):

```json
{ "schema": 1, "nodes": { "pick": { "x": 0, "y": 0 } } }
```

## 3. Op declaration subset (static AST extraction)

The registry reads Python source with `ast`. It never imports pack code. Anything outside this subset marks the op `invalid` (with a reason). `plynx validate` reports it.

Class form:

```python
from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op

class Concat(Op):
    """Join two strings.

    Supports joining arbitrary strings with an optional delimiter.
    """                                # cleaned docstring (inspect.cleandoc) = description
    TITLE = "Concat text"              # required, str literal
    CATEGORY = "Text / Basic"          # optional literal, default "Uncategorized"
    CACHEABLE = True                   # optional literal bool, default True (False when SIDE_EFFECTS = SideEffect.WRITE)
    SIDE_EFFECTS = SideEffect.NONE     # optional SideEffect or str literal ("none" | "read" | "write"), default "none"

    class Outputs(TypedDict):
        text: str

    def run(self, a: str, b: str = " ") -> Outputs:
        """Run concatenation.

        Args:
            a: First string to join.
            b: Second string to join (appended to `a`).
        """
        return {"text": a + b}
```

Function form:

```python
from plynx_sdk import op

class ConcatOut(TypedDict):            # module-level TypedDict in the same file
    text: str

@op(title="Concat text", category="Text / Basic", cacheable=True, side_effects="none")
def concat(a: str, b: str = " ") -> ConcatOut:
    return {"text": a + b}
```

- `@op(...)` arguments are literals. A single return annotation that is not a `TypedDict` (e.g. `-> str`) means one output named `result`.
- External side-effect metadata (`SIDE_EFFECTS` / `side_effects`): Declarative author contract (not OS/network sandboxing) classifying external consequence as `SideEffect.NONE` (`"none"`, pure local `workdir/`), `SideEffect.READ` (`"read"`, external read-only query or LLM call), or `SideEffect.WRITE` (`"write"`, external state mutation or real-world action). Setting `SIDE_EFFECTS = SideEffect.WRITE` defaults `CACHEABLE` to `False`; combining `WRITE` with `CACHEABLE = True` is invalid (`valid: false` in the registry and an `error` in `plynx validate`). `plynx validate` emits a `warning` when a `WRITE` node lacks an upstream `require_approval: true` stage gate after its non-local upstream producers.
- Port annotations allowed:
  - Primitives: `str`, `int`, `float`, `bool`, `dict`, `list`, `Path`, `Directory`.
  - Choices: `Literal["val1", "val2", ...]` (from `typing`; values must be str or int literals; yields `options` in registry).
  - Bounded numbers: `Annotated[int, Range(min, max, step=1)]` and `Annotated[float, Range(min, max, step=...)]` (from `plynx_sdk`; arguments are numeric literals, `step` optional; yields `min`, `max`, `step` in registry).
  - Media files: `Annotated[Path, Media("<mime>")]`, aliases from `plynx_sdk.types` (`PdfFile`, `AudioWav`, `MidiFile`, `MarkdownFile`, `JsonFile`, `ImageFile`, `CsvFile`, `TextFile`), module-level aliases defined in the same file as `Name = Annotated[Path, Media("<mime>")]`, `Name = Literal[...]`, or `Name = Annotated[int | float, Range(...)]`.
  - Optionals: `X | None` / `Optional[X]` of any of the above.
- Defaults are literals. Port names are `snake_case`.
- Variadic operations: An op can declare `ALLOW_EXTRA_INPUTS = True` (class form) or `@op(..., allow_extra_inputs=True)` (function form). Variadic inputs are declared via typed keyword arguments `**extra: <Type>` (e.g. `**tracks: AudioWav`). When enabled, the workflow engine accepts arbitrary named input ports matching `<Type>`.
- Agent operations (`AgentOp` and `StageValidatorOp` subclasses): Default `ALLOW_EXTRA_INPUTS = True`, `SIDE_EFFECTS = SideEffect.READ`, `agent_role = "agent" | "validator"`, and `ALLOW_GRAPH_EDITS = GraphEditPolicy.FORBIDDEN` (`AgentOp`) or `GraphEditPolicy.CONFIRM` (`StageValidatorOp`), exposed as `allow_graph_edits` on `OpEntry`. Subclasses may omit `def run()` (Choice A), inheriting `prompt_file: MarkdownFile | None = None`, `prompt: str = ""`, `provider: AgentProviderLiteral = "default"`, `model: str = ""`, and `**extra: Any`, or declare an explicit `def run(...)` (Choice B) with mandatory typed ports alongside standard agent ports (`StageValidatorOp` defaults `Outputs` to `{ summary: str }`). Inheritance from any base class outside `Op`, `AgentOp`, and `StageValidatorOp` or computed metadata is not supported.

Port type vocabulary (`type`): `str`, `int`, `float`, `bool`, `json` (`dict` or `list`), `file` (`Path`), `directory` (`Directory`).
- `options`: list of allowed scalar literals for `Literal[...]`, or `null`.
- `suggestions`: optional list of freeform autocomplete strings (e.g. `plynx.yaml` `agent.models` on `AgentOp` `model` ports), or `null`.
- `min`, `max`, `step`: numeric bounds for `Range(...)`, or `null`.
- `media`: MIME string or `null`. A `file` port with `media` accepts a wire from a `file` output with the same `media` or `null`.

Registry entry (served by `GET /api/v1/ops`, cached in `.plynx/registry_cache.json` keyed by `source` and its mtime):

```json
{
  "id": "standard_io/text:Concat", "pack": "standard_io", "module": "text", "name": "Concat",
  "kind": "class", "title": "Concat text", "category": "Text / Basic", "cacheable": true,
  "side_effects": "none",
  "description": "Join two strings.\n\nSupports joining arbitrary strings with an optional delimiter.",
  "inputs": [
    {
      "name": "a", "type": "str", "media": null,
      "options": null, "min": null, "max": null, "step": null,
      "required": true, "default": null,
      "description": "First string to join."
    }
  ],
  "outputs": [{ "name": "text", "type": "str", "media": null, "description": "" }],
  "allow_extra_inputs": false,
  "extra_inputs_type": null,
  "source": "builtin_packs/standard_io/src/standard_io/text.py",
  "valid": true, "error": null
}
```

## 4. Node Pack layout

A pack is a directory containing `pyproject.toml` and (for isolated third-party packs) `uv.lock`. Its directory name equals its top-level import package (`standard_io`). Source is at `src/<pack>/` or `<pack>/`. `<pack>/<module>:<Name>` imports `<pack>.<module>` and reads `<Name>`. Dependencies: `plynx-sdk` and the pack's own libraries. Never `plynx`. Stdlib-only built-in packs (`standard_io`) have no third-party dependencies, ship without `uv.lock`, and run directly using the active Python interpreter.

## 5. IPC between engine and child

Command (engine to child), cwd = `<node_dir>/workdir`:

For isolated packs:

```text
uv run --frozen --project <pack_dir> python -m plynx_sdk.harness --op <pack>.<module>:<Name> --dir <abs node_dir>
```

For stdlib-only built-in packs (such as `standard_io`):

```text
<sys.executable> -B -m plynx_sdk.harness --op <pack>.<module>:<Name> --dir <abs node_dir>
```

Environment: host environment (restricted by `env_passthrough` when set) + `.env` + `PYTHONUNBUFFERED=1`, `PYTHONUTF8=1`. Isolated packs also receive `UV_PROJECT_ENVIRONMENT=<workspace>/.plynx/envs/<pack>-<hash>`. Direct built-in packs receive `PYTHONPATH=<pack_src>` and `PYTHONDONTWRITEBYTECODE=1` so wheel-bundled packs stay read-only. For `@op` functions the harness finds the function by name.

### `inputs.json` (engine writes)

```json
{
  "schema": 1,
  "inputs": {
    "a":   { "kind": "scalar", "value": "hello" },
    "cfg": { "kind": "scalar", "value": { "k": 1 } },
    "doc": { "kind": "file", "path": "inputs/doc/resume.pdf", "sha256": "…", "size_bytes": 1234 },
    "frames": { "kind": "directory", "path": "inputs/frames", "tree_sha256": "…" }
  },
  "checkpoint_answers": { "cp_0": "foo", "cp_1": { "role": "ML", "skills": ["python", "sql"] } },
  "allow_graph_edits": "confirm"
}
```

- `scalar` holds `str | int | float | bool | dict | list`, at most 1 MiB serialized. Larger data must be a file.
- `checkpoint_answers` values are a `str` for `checkpoint()` and an object `{question_id: str | list[str]}` for `checkpoint_batch()`.
- `allow_graph_edits` is optional (`GraphEditPolicy`: `"forbidden" | "confirm" | "auto"`); omitted when unset on deterministic ops.
- Files and directories are materialized read-only (hard link, else copy) under `inputs/<port>/<original_filename>`.

### `outputs.json` (harness writes, only on success)

```json
{
  "schema": 1, "started_at": 1731800000.1, "finished_at": 1731800001.4,
  "outputs": {
    "text":   { "kind": "scalar", "value": "hello " },
    "report": { "kind": "file", "path": "workdir/report.md", "media": "text/markdown" },
    "frames": { "kind": "directory", "path": "workdir/frames" }
  },
  "warnings": ["Detected non-English document (lang=fr)"]
}
```

The harness checks that returned keys equal the declared outputs and that paths exist inside `workdir/`. `warnings` lists the messages from `self.warn(message)` (or `plynx_sdk.warn(message)` in `@op` functions) in call order. `warn()` is non-fatal: the op keeps running and may still exit 0. The field is optional when reading and defaults to `[]`.

### `result.json` (engine writes after ingest; the durable record)

The engine hashes each output, moves it into the blob store, and writes:

```json
{
  "schema": 1, "status": "SUCCESS", "cache_key": "…", "cache_hit": false,
  "started_at": 1731800000.1, "finished_at": 1731800001.4,
  "outputs": {
    "text":   { "kind": "scalar", "value": "hello " },
    "report": { "kind": "file", "sha256": "…", "size_bytes": 10, "media": "text/markdown", "filename": "report.md" },
    "frames": { "kind": "directory", "tree_sha256": "…", "entries": [ { "path": "0001.png", "sha256": "…", "size_bytes": 99 } ] }
  },
  "warnings": ["Detected non-English document (lang=fr)"]
}
```

`warnings` is copied from `outputs.json`, is stored in `CACHE_INDEX.result_json`, and is kept on cache hits.

`tree_sha256` = SHA-256 of the UTF-8 text made of one line `"<sha256> <path>\n"` per entry, sorted by `path`. `result.json` is also what `CACHE_INDEX.result_json` stores.

### `checkpoint.json` (harness writes on interrupt)

```json
{ "schema": 1, "checkpoint_id": "cp_0", "question": "foo or woo?", "options": ["foo", "woo"], "allow_freeform": false, "questions": [ { "id": "default", "header": "", "question": "foo or woo?", "options": ["foo", "woo"], "multi_select": false, "allow_freeform": false } ] }
```

`checkpoint_id` is `cp_<n>`, `n` = index of the `checkpoint()` or `checkpoint_batch()` call in this attempt, from 0. If `checkpoint_answers` has the id, the call returns the answer. Otherwise it writes `checkpoint.json` and raises `CheckpointInterrupt` (a `BaseException`).

- `plynx_sdk.checkpoint(question, options=None, allow_freeform=False) -> str` (also `self.checkpoint(...)`) asks one question. `questions` holds one item with id `default`, mirrored in the top-level `question`, `options`, and `allow_freeform`. The answer is a string.
- `plynx_sdk.checkpoint_batch(questions) -> dict[str, str | list[str]]` (also `self.checkpoint_batch(...)`) asks several questions in one pause. Each item is a `CheckpointQuestion` or a dict with `id` (required, `[A-Za-z_][A-Za-z0-9_]*`, unique, `default` is reserved), `question` (required), `header` (default `""`), `options` (default `[]`), `multi_select` (default `false`), `allow_freeform` (default `true`). The top-level `question` is `""` and `options` is `null`. The answer maps every question id to a `str` (`multi_select: false`) or a `list[str]` (`multi_select: true`). Every question must be answered, unknown ids are rejected, and when a question has `options` and `allow_freeform` is false each value must be one of the options.
- `questions` is optional when reading a manifest. A manifest without it (written by v2.0.0) is read as one `default` question built from the top-level fields.

### `agent_turns.json` (`AgentOp` / `StageValidatorOp` writes inside `nodes/<node_id>/`)

```json
{
  "schema": 1,
  "turns": [
    {
      "turn_index": 0,
      "provider": "cursor",
      "model": "gpt-5",
      "session_id": "chat_abc123",
      "status": "needs_input",
      "prompt_summary": "Compare CV against job description...",
      "started_at": 1731800000.1,
      "finished_at": 1731800008.4,
      "questions": [
        {
          "id": "role",
          "header": "",
          "question": "Target track?",
          "options": [
            "ML",
            "Backend"
          ],
          "multi_select": false,
          "allow_freeform": true
        }
      ],
      "user_answers": {
        "role": "ML"
      }
    }
  ]
}
```

Before executing Turn `k`, `AgentOp` consults `agent_turns.json`. If Turn `k` is already recorded (e.g. replaying `run()` after a `checkpoint_batch()` exit `10`), `AgentOp` returns the recorded turn in 0 tokens, reads the stored checkpoint answer from `inputs.json`, and resumes Turn `k+1` via `--resume <session_id>`. Before each turn, `AgentOp` writes `workdir/turn_schema.json` and reads `workdir/turn_output.json` (falling back to CLI `stdout` JSON).

### `stage_context.json` (engine writes inside `nodes/__stage_validator__<stage_id>/`)

Before launching a Stage Validator subprocess, the engine writes `stage_context.json` containing `"schema": 1`, `run_id`, `stage_id`, `stage_title`, `mode`, `allow_graph_edits`, `max_injected_nodes`, `nodes` (per-node `op`, `status`, `cache_hit`, `attempt`, `error`, `warnings`, `outputs` with 4 KiB text previews, and 100-line `stdout_tail` / `stderr_tail`), `workflow_snapshot_yaml`, and `registered_ops` (`OpEntry` schemas). `AgentOp` summarizes this context automatically into the prompt.

### `graph_patch.json` (`AgentOp` / `StageValidatorOp` writes inside `nodes/<node_id>/`)

```json
{
  "schema": 1,
  "reason": "Detected French document; splicing translator before summarize.",
  "add_nodes": {
    "translate_fr": {
      "op": "demo_pack/ops:TranslateFr",
      "stage": "ask",
      "inputs": { "text": "$pick.choice" }
    }
  },
  "rewire_inputs": {
    "echo": { "text": "$translate_fr.text" }
  }
}
```

When a child exits `0` with `graph_patch.json` present:
- `GraphEditPolicy.FORBIDDEN`: the engine rejects the attempt (`FAILED`).
- `GraphEditPolicy.CONFIRM` / `AUTO`: the engine quiesces all active worker subprocesses, validates the candidate `workflow.snapshot.yaml` against all 4 mutation guardrails (`plynx validate`, `PENDING`-only / immutable `SUCCESS` nodes, Lineage Preservation `U -> [New Subgraph] -> V`, and cumulative `max_injected_nodes`), opens a `["Approve Patch", "Reject"]` checkpoint when policy is `CONFIRM` (or when `AUTO` attempts to inject any `SideEffect.WRITE` node), writes the updated `workflow.snapshot.yaml` (leaving `workflows/<name>.yaml` untouched), archives `graph_patch.applied.json` (or `graph_patch.rejected.json`), and reloads `graphlib.TopologicalSorter`.

### Child exit codes

| Exit | Files | Node status |
|---|---|---|
| 0 | `outputs.json` present and valid | `SUCCESS` |
| 10 | `checkpoint.json` present and valid | `WAITING_FOR_USER` |
| 1 | op raised; traceback on stderr | `FAILED` |
| 2 | harness/protocol error (bad input, missing op, bad outputs) | `FAILED` |
| any other, or killed by a signal not sent by the engine | | `FAILED` |
| engine sent the kill (cancel, timeout) | | `CANCELED` |
| 0 without `outputs.json`, or 10 without `checkpoint.json` | | `FAILED` (`protocol error`) |

### Protocol enums (`plynx_sdk.protocol`)

All are `enum.StrEnum`; use the members instead of raw strings. `ui/src/api/types.gen.ts` mirrors the API-visible ones.

| Enum | Values |
|---|---|
| `AgentTurnStatus` | `completed`, `needs_input`, `propose_patch` |
| `GraphEditPolicy` | `forbidden`, `confirm`, `auto` |
| `ValidatorMode` | `on_anomaly`, `on_failure`, `always` |
| `SideEffect` | `none`, `read`, `write` |
| `AgentProvider` | `default`, `claude`, `cursor`, `codex`, `gemini`, `opencode`, `goose`, `aider`, `custom`, `mock` |

## 6. Cache key

```text
cache_key = sha256("\n".join([
  "plynx-cache-1",
  op_entrypoint,        # "<pack>/<module>:<Name>"
  file_sha256,          # bytes of the op's source file
  uv_lock_sha256,       # bytes of the pack's uv.lock ("" if none)
  inputs_hash,
  params_hash,
]))
```

- `inputs_hash` = sha256 of canonical JSON (sorted keys, separators `,` `:`, no ASCII escaping) of `{port: sha256 | tree_sha256}` for every file and directory port (from a reference or a literal path).
- `params_hash` = same canonical JSON of `{port: value}` for every scalar port, plus `"__checkpoint_answers__": {...}` when answers exist and `"__allow_graph_edits__": "<policy>"` when `allow_graph_edits` is non-`forbidden`.
- Stage Validators (`__stage_validator__<stage_id>`) are never stored in `cache_index`, but are skipped in 0ms (`cache_hit = true`, `attempt = 0`) when 100% of active nodes in the stage hit CAS cache with zero warnings, or skipped (`cache_hit = false`, `attempt = 0`) when `ValidatorMode` trigger rules (`on_anomaly` / `on_failure`) are not met.
- Not covered, by design: other files in the pack (shared helpers), environment variables, time, network. Rule in `guides/author_pack.md`. Escape hatch: `plynx run --no-cache`.
- Lookup happens only in fresh runs and only for `CACHEABLE = True` ops. A miss with a missing blob is a miss, never an error.
- Early cutoff falls out of the formula: downstream keys depend on output hashes, not on upstream keys.

## 7. SQLite (`.plynx/plynx.db`)

Pragmas on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`. `PRAGMA user_version = 2`. A version 1 database (v2.0.0) is upgraded in place on open with `ALTER TABLE checkpoints ADD COLUMN questions_json TEXT`, `ALTER TABLE node_runs ADD COLUMN warnings_json TEXT`, and `PRAGMA user_version = 2`. Any other version stops with "delete `.plynx/plynx.db`".

```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY, workflow_path TEXT NOT NULL, workflow_sha256 TEXT NOT NULL,
  status TEXT NOT NULL, run_inputs_json TEXT NOT NULL DEFAULT '{}',
  owner_pid INTEGER, cancel_requested INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, started_at REAL, finished_at REAL, error TEXT
);
CREATE TABLE node_runs (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, node_id TEXT NOT NULL,
  status TEXT NOT NULL, cache_hit INTEGER NOT NULL DEFAULT 0, cache_key TEXT,
  attempt INTEGER NOT NULL DEFAULT 0, exit_code INTEGER, error TEXT,
  warnings_json TEXT,
  started_at REAL, finished_at REAL, PRIMARY KEY (run_id, node_id)
);
CREATE TABLE checkpoints (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, node_id TEXT NOT NULL,
  checkpoint_id TEXT NOT NULL, question TEXT NOT NULL, options_json TEXT, allow_freeform INTEGER NOT NULL DEFAULT 0,
  questions_json TEXT,
  answer TEXT, created_at REAL NOT NULL, answered_at REAL,
  PRIMARY KEY (run_id, node_id, checkpoint_id)
);
CREATE TABLE stage_gates (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, stage_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'approval' CHECK (kind IN ('input','approval')),
  status TEXT NOT NULL CHECK (status IN ('WAITING','APPROVED')),
  created_at REAL NOT NULL, decided_at REAL, PRIMARY KEY (run_id, stage_id, kind)
);
CREATE TABLE cache_index (
  cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL, created_at REAL NOT NULL, last_accessed_at REAL NOT NULL
);
```

Gate kinds:
- `approval`: Opened when all nodes in a stage with `require_approval: true` reach `SUCCESS`. Pauses execution before any later stage begins. Approved via `POST /runs/{id}/stages/{stage_id}/approve` (or terminal prompt).
- `input`: Opened dynamically when prior stages have finished and the stage has unbound run inputs. Pauses execution until values are supplied via `POST /runs/{id}/stages/{stage_id}/inputs` or `approve` with inputs (or terminal prompt).

An answer is written with `UPDATE checkpoints SET answer=?, answered_at=? WHERE ... AND answer IS NULL`. Zero rows changed means someone else answered first. `questions_json` is the JSON list of `CheckpointQuestion` objects (`NULL` for rows created before version 2). For a single-question checkpoint `answer` is the plain string. For a batch checkpoint `answer` is the JSON-encoded answer map.

## 8. Run directory

```text
.plynx/runs/<run_id>/
  run_manifest.json          { schema, run_id, workflow_path, workflow_sha256, plynx_version, created_at, run_inputs }
  workflow.snapshot.yaml     exact bytes executed (updated via ruamel.yaml on accepted dynamic graph patches)
  .workflow.baseline.yaml    immutable initial workflow snapshot at run creation (used for drift & budget checks)
  .workflow.accepted.yaml    last engine-validated snapshot (used to validate outer-agent edits on plynx resume)
  layout.snapshot.json       only if the sidecar exists
  events.jsonl               append-only event log (section 9)
  logs/<node_id>.stdout.log  append-only; "--- attempt N ---" line between attempts
  logs/<node_id>.stderr.log
  nodes/<node_id>/
    inputs.json  stage_context.json  checkpoint.json  agent_turns.json  graph_patch.json  outputs.json  result.json
    inputs/<port>/<filename>
    workdir/
```

Blob store: `.plynx/cache/blobs/<first 2 hex>/<sha256>`, mode read-only. Link order: `os.link`, then `shutil.copy2` on any `OSError`.

## 9. Events and SSE

`events.jsonl`, one JSON object per line: `{ "seq": 1, "ts": 1731800000.1, "type": "node_status", "data": { … } }`. `seq` starts at 1 per run, strictly increasing, written by the run owner.

| `type` | `data` |
|---|---|
| `run_status` | `run_id`, `status`, `error?` |
| `node_status` | `run_id`, `node_id`, `status`, `cache_hit`, `attempt`, `exit_code?`, `error?`, `warnings` |
| `node_checkpoint` | `run_id`, `node_id`, `checkpoint_id`, `question`, `options`, `allow_freeform`, `questions` (list of `CheckpointQuestion`; `question` is a one-line summary for batch checkpoints), `graph_patch?` (`{ reason, add_nodes, rewire_inputs }` for patch-confirmation checkpoints) |
| `checkpoint_resolved` | `run_id`, `node_id`, `checkpoint_id` |
| `stage_approval` | `run_id`, `stage_id`, `title`, `kind` (`input`/`approval`) |
| `stage_resolved` | `run_id`, `stage_id`, `kind` (`input`/`approval`) |
| `node_log` | `run_id`, `node_id`, `stream` (`stdout`/`stderr`), `offset`, `lines` |

`node_log` is not stored in `events.jsonl`. The server creates it by tailing the log files and batches at most one event per 50 ms per node.

SSE (`GET /api/v1/runs/{run_id}/stream`): frames `id: <seq>`, `event: <type>`, `data: <json>`. `Last-Event-ID` resumes after that `seq`. `node_log` frames have no `id`. A client opening a page first calls `GET /runs/{id}` (full state from SQLite) and `GET .../logs/...` (history), then connects the stream.

## 10. REST (JSON, loopback only, no auth; mounted at `/api/v1` and root `/`)

| Method and path | Purpose |
|---|---|
| `GET /health` | `{ "status": "ok", "version": "2.0.0" }` |
| `GET /ops` | list of registered operations (`OpEntry`) |
| `GET /workflows` | list of workflow paths with name and stage count (`WorkflowListItem`) |
| `GET /workflows/{path}` | `{ workflow, layout }` (`WorkflowDocument`) |
| `PUT /workflows/{path}` | save `{ workflow, layout }` (YAML round-trip, layout sidecar) |
| `POST /workflows/validate` | body `{ workflow }`, returns `{ issues: [{ severity, message, node_id?, port_name?, stage_id? }] }` |
| `GET /workflows/{path}/inputs` | run inputs still unbound: `[{ node_id, name, type, media, required, default, stage_id, options, min, max, step, description }]` (`WorkflowInputSpec`) |
| `POST /uploads` | multipart file upload. Returns `{ path }` (workspace-relative, under `.plynx/uploads/`) |
| `POST /runs` | `{ workflow_path, inputs?: { "node.name": value }, no_cache?: bool, agent_provider?: AgentProvider, agent_model?: str, max_injected_nodes?: int }`, returns `{ run_id }` |
| `GET /runs` | list runs, newest first, `?limit=50&cursor=...&workflow_path=...`, returns `{ runs: [...], next_cursor: ..., drift_alerts?: [...] }` |
| `GET /runs/stats` | aggregated per-node execution stats & baseline drift alerts (`?workflow_path=...`), returns `{ total_runs, nodes: [...], drift_alerts: [...] }` (`RunStatsResponse`) |
| `GET /runs/{id}` | full state: run, nodes, open checkpoints (including `graph_patch` when applicable), stage gates, run inputs (`RunState`) |
| `POST /runs/{id}/cancel` | request cancel |
| `POST /runs/{id}/resume` | take ownership and continue run, returns `{ run_id }` |
| `POST /runs/{id}/checkpoints/{node_id}/{checkpoint_id}/answer` | `{ answer: string }` for a single-question checkpoint, or `{ answers: { "<question_id>": string \| string[] } }` for a batch checkpoint. Send exactly one of the two. Invalid answers return `422 invalid_answer`. `RunState.checkpoints[]` carries `questions`, `answer`, and the decoded `answers` for batch checkpoints. |
| `POST /runs/{id}/stages/{stage_id}/approve` | approve stage gate (optional body `{ inputs?: { "node.name": value } }`) |
| `POST /runs/{id}/stages/{stage_id}/inputs` | submit deferred stage inputs (body `{ inputs: { "node.name": value } }`) and resolve its `input` gate |
| `GET /runs/{id}/stream` | SSE (section 9, supports `?last_event_id=N&initial_log_offset=N` or `Last-Event-ID` header) |
| `GET /runs/{id}/nodes/{node_id}/logs/{stream}?offset=0` | `text/plain`, header `X-Next-Offset` |
| `GET /runs/{id}/nodes/{node_id}/agent-turns` | `{ schema: 1, turns: [...] }` from `nodes/<node_id>/agent_turns.json` (empty list if none) |
| `GET /runs/{id}/nodes/{node_id}/outputs/{name}` | blob download, `Content-Type` from `media` |
| `POST /clean` | body `{ days?: int, dry_run?: bool }`, returns `{ runs_deleted, cache_entries_deleted, blobs_deleted, bytes_reclaimed }` |

Errors: HTTP status plus `{ "error": { "code": "snake_case", "message": "…" } }`.
Server binds `127.0.0.1` (or loopback host). CORS allows only the Vite dev origins (`http://localhost:3000`, `http://127.0.0.1:3000`) in dev mode.

## 11. CLI

| Command | Behavior |
|---|---|
| `plynx init [target_dir]` | create `.plynx/`, `workflows/.gitkeep`, `custom_packs/.gitkeep`, `plynx.yaml`, `.gitignore` entries |
| `plynx validate <workflow>` | static check, no code executed. Exit 0 ok, 1 issues |
| `plynx run <workflow> [options]` | run in-process with `LocalExecutor` |
| `plynx resume <run_id> [options]` | continue a failed, canceled, or waiting run, reusing completed node outputs |
| `plynx run-node <node_dir> [--op <op>] [--allow-side-effects]` | re-run one node attempt from `node_dir` in a scratch copy without touching SQLite (reads op from snapshot if omitted; blocks `side_effects='write'` ops unless `--allow-side-effects` is set) |
| `plynx runs [run_id] [--limit N] [--workflow PATH] [--stats] [--json]` | list recent runs (with `[DRIFT]` alerts), inspect one run by full ID or unique prefix, or compute per-node execution & drift stats (`--stats`) |
| `plynx ops [--json]` | list registered operations (table or full JSON schemas) |
| `plynx clean [--days 14] [--dry-run]` | mark-and-sweep garbage collection of old unpinned runs and unreferenced blobs |
| `plynx ui [--port 8080] [--host 127.0.0.1] [--no-browser]` | start the server on loopback host and open the UI |
| `plynx agent-guide` | print the self-contained User Agent Reference (`AGENT_GUIDE.md`) to stdout |

`plynx run` options: `--set node.port=value` (repeatable, scalar), `--input node.port=path` (repeatable, file or directory), `--answers file.json` (`{ "node.cp_n": "value" }`, or `{ "node.cp_n": { "question_id": "value" | ["v1", "v2"] } }` for batch checkpoints), `--answer node.cp_n=value` (repeatable; `--answer node.cp_n.question_id=value` for a batch question, repeat it to build a `multi_select` list), `--concurrency N`, `--agent-provider <provider>`, `--agent-model <model>`, `--max-injected-nodes N`, `--non-interactive` (also when `CI=true`), `--no-cache`.

`plynx resume` options: `--answers file.json` and `--answer` (same forms as `plynx run`), `--concurrency N`, `--agent-provider <provider>`, `--agent-model <model>`, `--max-injected-nodes N`, `--non-interactive`. Before resuming, `plynx resume` validates any outer-agent edits made to `.plynx/runs/<run_id>/workflow.snapshot.yaml` against `validate_snapshot_mutation`.

Exit codes of `run` and `resume`: `0` success, `1` failed, `2` blocked on a checkpoint or stage gate in non-interactive mode, `130` canceled. Interactive mode prompts in the terminal: numbered options `[1-N]`, or text when `allow_freeform`. A batch checkpoint prompts for each question in order; `multi_select` answers are comma separated.

## 12. `plynx.yaml` (optional)

```yaml
workflows: workflows                 # default: "workflows" (or list of directories: ["workflows"])
packs: [custom_packs]               # default: [], searched in order, after the packs shipped in the plynx wheel
                                     # (in the v2 repo, `builtin_packs/` is added automatically)
db: .plynx/plynx.db                  # default: ".plynx/plynx.db"
concurrency: 4                       # default: None (falls back to os.cpu_count())
env_passthrough: ["*"]               # default: inherit all; or a list of specific env var names
cache: { max_size: 10GB }            # optional LRU budget for blobs (e.g. "10GB", 10737418240)
agent:                               # optional coding-agent settings
  provider: default                  # AgentProvider (or PLYNX_AGENT_PROVIDER env var)
  model: ""                          # default model (or PLYNX_AGENT_MODEL env var)
  agent_concurrency: 2               # max concurrent AgentOp / StageValidatorOp attempts
  max_injected_nodes: 3              # cumulative per-run dynamic node injection budget
  models: []                         # optional autocomplete suggestions for UI <datalist>
  custom_command: ""                 # command template for AgentProvider.CUSTOM
```

Concurrency precedence: `--concurrency` > `workflow.yaml` > `plynx.yaml` > `os.cpu_count()`.
Max injected nodes precedence: `--max-injected-nodes` > `workflow.yaml` > `plynx.yaml` > `3`.
Agent `provider` / `model` precedence (resolved into `inputs.json` before `plynx-cache-1` cache-key computation): `plynx.yaml` / env -> `workflow.yaml` `agent:` -> CLI `--agent-provider` / `--agent-model` -> explicit non-default node `inputs` -> CLI `--set <node>.provider` / `--set <node>.model`.
