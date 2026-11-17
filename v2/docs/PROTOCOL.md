# Protocol (PLynx v2.0.0)

Exact formats. Code must match this file. Change this file first, then the code, in the same commit. Schema version of every JSON manifest: `"schema": 1`.

## 1. Conventions

- Run ID: `YYYYMMDD_HHMMSS_<6 hex>` in UTC, e.g. `20261116_201500_a1b2c3`. It is the SQLite key and the run directory name. CLI accepts any unique prefix.
- Node ID: `^[a-z][a-z0-9_]*$`. Stage ID: same pattern, or a free label (see 2).
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
stages:                        # optional
  ask:
    title: "1. Ask"            # optional, default: stage id
    require_approval: false    # optional, default false
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
- `inputs` is one map for every port of the op (the old parameter/input split is gone). A value is one of:
  - a **reference**: the string `$<node_id>.<output_name>`, or the mapping `{ from_node: <node_id>, output: <output_name> }`;
  - a **literal**: any YAML scalar, list or mapping. For `Path` and `Directory` ports a string literal is a workspace-relative path;
  - an **escaped string**: a string starting with `$$` stands for the literal string with one `$` removed.
  - Any other string starting with `$` is a validation error.
- A port with no value and no default is a **run input**. The CLI (`--set`, `--input`) and the UI ask for it when the run starts.
- A stage listed in `stages:` keeps its order. Stage labels used only on nodes get the order of first appearance. Edges must stay in the same stage or go to a later stage.
- No coordinates, no sizes, no UI fields. Unknown top-level or node keys are a validation error.
- YAML is read and written with `ruamel.yaml` so comments and key order survive UI edits.

Layout sidecar `workflows/.<name>.layout.json` (UI-owned, engine ignores it, copied into the run snapshot):

```json
{ "schema": 1, "nodes": { "pick": { "x": 0, "y": 0 } }, "viewport": { "x": 0, "y": 0, "zoom": 1 } }
```

## 3. Op declaration subset (static AST extraction)

The registry reads Python source with `ast`. It never imports pack code. Anything outside this subset marks the op `invalid` (with a reason). `plynx validate` reports it.

Class form:

```python
from pathlib import Path
from typing import TypedDict
from plynx_sdk import Op

class Concat(Op):
    """Join two strings."""            # first docstring line = description
    TITLE = "Concat text"              # required, str literal
    CATEGORY = "Text / Basic"          # optional literal, default "Uncategorized"
    CACHEABLE = True                   # optional literal bool, default True

    class Outputs(TypedDict):
        text: str

    def run(self, a: str, b: str = " ") -> Outputs:
        return {"text": a + b}
```

Function form:

```python
from plynx_sdk import op

class ConcatOut(TypedDict):            # module-level TypedDict in the same file
    text: str

@op(title="Concat text", category="Text / Basic", cacheable=True)
def concat(a: str, b: str = " ") -> ConcatOut:
    return {"text": a + b}
```

- `@op(...)` arguments are literals. A single return annotation that is not a `TypedDict` (e.g. `-> str`) means one output named `result`.
- Port annotations allowed: `str`, `int`, `float`, `bool`, `dict`, `list`, `Path`, `Directory`, `Annotated[Path, Media("<mime>")]`, aliases from `plynx_sdk.types` (`PdfFile`, `AudioWav`, `MarkdownFile`, `JsonFile`, `ImageFile`, `CsvFile`, `TextFile`), module-level aliases defined in the same file as `Name = Annotated[Path, Media("<mime>")]`, and `X | None` / `Optional[X]` of those.
- Defaults are literals. Port names are `snake_case`.
- Inheritance from a custom base class or computed metadata is not supported in v2.0.0.

Port type vocabulary (`type`): `str`, `int`, `float`, `bool`, `json` (`dict` or `list`), `file` (`Path`), `directory` (`Directory`). `media` is a MIME string or `null`. A `file` port with `media` accepts a wire from a `file` output with the same `media` or `null`.

Registry entry (served by `GET /api/v1/ops`, cached in `.plynx/registry_cache.json` keyed by `source` and its mtime):

```json
{
  "id": "standard_io/text:Concat", "pack": "standard_io", "module": "text", "name": "Concat",
  "kind": "class", "title": "Concat text", "category": "Text / Basic", "cacheable": true,
  "description": "Join two strings.",
  "inputs": [{ "name": "a", "type": "str", "media": null, "required": true, "default": null }],
  "outputs": [{ "name": "text", "type": "str", "media": null }],
  "source": "builtin_packs/standard_io/src/standard_io/text.py",
  "valid": true, "error": null
}
```

## 4. Node Pack layout

A pack is a directory containing `pyproject.toml` and `uv.lock`. Its directory name equals its top-level import package (`standard_io`). Source is at `src/<pack>/` or `<pack>/`. `<pack>/<module>:<Name>` imports `<pack>.<module>` and reads `<Name>`. Dependencies: `plynx-sdk` and the pack's own libraries. Never `plynx`.

## 5. IPC between engine and child

Command (engine to child), cwd = `<node_dir>/workdir`:

```text
uv run --frozen --project <pack_dir> python -m plynx_sdk.harness --op <pack>.<module>:<Name> --dir <abs node_dir>
```

Environment: host environment (restricted by `env_passthrough` when set) + `.env` + `PYTHONUNBUFFERED=1`, `PYTHONUTF8=1`, `UV_PROJECT_ENVIRONMENT=<workspace>/.plynx/envs/<pack>-<hash>`. For `@op` functions the harness finds the function by name.

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
  "checkpoint_answers": { "cp_0": "foo" }
}
```

- `scalar` holds `str | int | float | bool | dict | list`, at most 1 MiB serialized. Larger data must be a file.
- Files and directories are materialized read-only (hard link, else copy) under `inputs/<port>/<original_filename>`.

### `outputs.json` (harness writes, only on success)

```json
{
  "schema": 1, "started_at": 1731800000.1, "finished_at": 1731800001.4,
  "outputs": {
    "text":   { "kind": "scalar", "value": "hello " },
    "report": { "kind": "file", "path": "workdir/report.md", "media": "text/markdown" },
    "frames": { "kind": "directory", "path": "workdir/frames" }
  }
}
```

The harness checks that returned keys equal the declared outputs and that paths exist inside `workdir/`.

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
  }
}
```

`tree_sha256` = SHA-256 of the UTF-8 text made of one line `"<sha256> <path>\n"` per entry, sorted by `path`. `result.json` is also what `CACHE_INDEX.result_json` stores.

### `checkpoint.json` (harness writes on interrupt)

```json
{ "schema": 1, "checkpoint_id": "cp_0", "question": "foo or woo?", "options": ["foo", "woo"], "allow_freeform": false }
```

`checkpoint_id` is `cp_<n>`, `n` = index of the `checkpoint()` call in this attempt, from 0. The SDK API is `plynx_sdk.checkpoint(question, options=None, allow_freeform=False) -> str`, also available as `self.checkpoint(...)` on `Op`. If `checkpoint_answers` has the id, it returns the answer. Otherwise it writes `checkpoint.json` and raises `CheckpointInterrupt` (a `BaseException`). Answers are strings.

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
- `params_hash` = same canonical JSON of `{port: value}` for every scalar port, plus `"__checkpoint_answers__": {...}` when answers exist.
- Not covered, by design: other files in the pack (shared helpers), environment variables, time, network. Rule in `PACK_RULES.md`. Escape hatch: `plynx run --no-cache`.
- Lookup happens only in fresh runs and only for `CACHEABLE = True` ops. A miss with a missing blob is a miss, never an error.
- Early cutoff falls out of the formula: downstream keys depend on output hashes, not on upstream keys.

## 7. SQLite (`.plynx/plynx.db`)

Pragmas on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`. `PRAGMA user_version = 1`. No migrations in v2.0.0: an unknown version stops with "delete `.plynx/plynx.db`".

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
  started_at REAL, finished_at REAL, PRIMARY KEY (run_id, node_id)
);
CREATE TABLE checkpoints (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, node_id TEXT NOT NULL,
  checkpoint_id TEXT NOT NULL, question TEXT NOT NULL, options_json TEXT, allow_freeform INTEGER NOT NULL DEFAULT 0,
  answer TEXT, created_at REAL NOT NULL, answered_at REAL,
  PRIMARY KEY (run_id, node_id, checkpoint_id)
);
CREATE TABLE stage_gates (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, stage_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('WAITING','APPROVED')),
  created_at REAL NOT NULL, decided_at REAL, PRIMARY KEY (run_id, stage_id)
);
CREATE TABLE cache_index (
  cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL, created_at REAL NOT NULL, last_accessed_at REAL NOT NULL
);
```

An answer is written with `UPDATE checkpoints SET answer=?, answered_at=? WHERE ... AND answer IS NULL`. Zero rows changed means someone else answered first.

## 8. Run directory

```text
.plynx/runs/<run_id>/
  run_manifest.json        { schema, run_id, workflow_path, workflow_sha256, plynx_version, created_at, run_inputs }
  workflow.snapshot.yaml   exact bytes executed
  layout.snapshot.json     only if the sidecar exists
  events.jsonl             append-only event log (section 9)
  logs/<node_id>.stdout.log   append-only; "--- attempt N ---" line between attempts
  logs/<node_id>.stderr.log
  nodes/<node_id>/
    inputs.json  checkpoint.json  outputs.json  result.json
    inputs/<port>/<filename>
    workdir/
```

Blob store: `.plynx/cache/blobs/<first 2 hex>/<sha256>`, mode read-only. Link order: `os.link`, then `shutil.copy2` on any `OSError`.

## 9. Events and SSE

`events.jsonl`, one JSON object per line: `{ "seq": 1, "ts": 1731800000.1, "type": "node_status", "data": { … } }`. `seq` starts at 1 per run, strictly increasing, written by the run owner.

| `type` | `data` |
|---|---|
| `run_status` | `run_id`, `status`, `error?` |
| `node_status` | `run_id`, `node_id`, `status`, `cache_hit`, `attempt`, `exit_code?`, `error?` |
| `node_checkpoint` | `run_id`, `node_id`, `checkpoint_id`, `question`, `options`, `allow_freeform` |
| `checkpoint_resolved` | `run_id`, `node_id`, `checkpoint_id` |
| `stage_approval` | `run_id`, `stage_id`, `title` |
| `stage_resolved` | `run_id`, `stage_id` |
| `node_log` | `run_id`, `node_id`, `stream` (`stdout`/`stderr`), `offset`, `lines` |

`node_log` is not stored in `events.jsonl`. The server creates it by tailing the log files and batches at most one event per 50 ms per node.

SSE (`GET /api/v1/runs/{run_id}/stream`): frames `id: <seq>`, `event: <type>`, `data: <json>`. `Last-Event-ID` resumes after that `seq`. `node_log` frames have no `id`. A client opening a page first calls `GET /runs/{id}` (full state from SQLite) and `GET .../logs/...` (history), then connects the stream.

## 10. REST (`/api/v1`, JSON, loopback only, no auth)

| Method and path | Purpose |
|---|---|
| `GET /health` | `{ "status": "ok", "version": "2.0.0" }` |
| `GET /ops` | registry entries |
| `GET /workflows` | list of workflow paths with name and stage count |
| `GET /workflows/{path}` | `{ workflow, layout }` |
| `PUT /workflows/{path}` | save `{ workflow, layout }` (YAML round-trip, layout sidecar) |
| `POST /workflows/validate` | body `{ workflow }`, returns `{ issues: [{ severity, node_id?, message }] }` |
| `GET /workflows/{path}/inputs` | run inputs still unbound: `[{ node_id, name, type, media, required, default, stage_id }]` |
| `POST /uploads` | multipart file. Returns `{ path }` (workspace-relative, under `.plynx/uploads/`) |
| `POST /runs` | `{ workflow_path, inputs: { "node.name": value }, no_cache? }` returns `{ run_id }` |
| `GET /runs` | list, newest first, `?limit&cursor` |
| `GET /runs/{id}` | full state: run, nodes, open checkpoints, stage gates, run inputs |
| `POST /runs/{id}/cancel` | request cancel |
| `POST /runs/{id}/resume` | take ownership and continue |
| `POST /runs/{id}/checkpoints/{node_id}/{checkpoint_id}/answer` | `{ answer }` |
| `POST /runs/{id}/stages/{stage_id}/approve` | approve gate |
| `GET /runs/{id}/stream` | SSE (section 9) |
| `GET /runs/{id}/nodes/{node_id}/logs/{stream}?offset=0` | `text/plain`, header `X-Next-Offset` |
| `GET /runs/{id}/nodes/{node_id}/outputs/{name}` | blob download, `Content-Type` from `media` |
| `POST /clean` | `{ days, dry_run }` returns reclaimed counts |

Errors: HTTP status plus `{ "error": { "code": "snake_case", "message": "…" } }`.
Server binds `127.0.0.1`. CORS allows only the Vite dev origin (`http://localhost:3000`) in dev mode.

## 11. CLI

| Command | Behavior |
|---|---|
| `plynx init [dir]` | create `.plynx/`, `.gitignore` entries, empty `custom_packs/.gitkeep` |
| `plynx validate <workflow>` | static check, no code executed. Exit 0 ok, 1 issues |
| `plynx run <workflow> [options]` | run in-process with `LocalExecutor` |
| `plynx resume <run_id> [--answer node.cp_n=value] [--non-interactive]` | continue a failed or waiting run |
| `plynx run-node <node_dir>` | re-run one node attempt in a scratch copy. Streams output to the terminal. Does not touch SQLite |
| `plynx runs [--limit N]` | list runs |
| `plynx ops [--json]` | list registry |
| `plynx clean [--days 14] [--dry-run]` | mark and sweep blobs, delete old unpinned runs |
| `plynx ui [--port 8080] [--no-browser]` | start the server and open the UI |

`plynx run` options: `--set node.name=value` (repeatable, scalar), `--input node.name=path` (repeatable, file or directory), `--answers file.json` (`{ "node.cp_n": "value" }`), `--answer node.cp_n=value`, `--concurrency N`, `--non-interactive` (also when `CI=true`), `--no-cache`.

Exit codes of `run` and `resume`: `0` success, `1` failed, `2` blocked on a checkpoint or stage approval in non-interactive mode, `130` canceled. Interactive mode prompts in the terminal: numbered options `[1-N]`, or text when `allow_freeform`.

## 12. `plynx.yaml` (optional)

```yaml
workflows: workflows                 # default
packs: [custom_packs]               # default, searched in order, after the packs shipped in the plynx wheel
                                     # (in the v2 repo, `builtin_packs/` is added automatically)
db: .plynx/plynx.db                  # default
concurrency: 4                       # default: os.cpu_count()
env_passthrough: ["*"]               # default: inherit all; or a list of names
cache: { max_size: 10GB }            # optional LRU budget for blobs
```

Concurrency precedence: `--concurrency` > `workflow.yaml` > `plynx.yaml` > `os.cpu_count()`.
