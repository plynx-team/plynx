# Architecture (PLynx v2.0.0)

Rigid reference. No philosophy. Exact formats are in [PROTOCOL.md](PROTOCOL.md).

## What it is

A local-first workflow engine. A workflow is a static DAG in `workflow.yaml`. Each node runs as a separate OS process inside an isolated `uv` environment. Outputs are content-addressed and cached. A browser UI shows the DAG as a Stepper (default) or an editable Graph. Single user. No database server.

## Directory layout (v2 root)

```text
AGENTS.md
pyproject.toml            uv workspace (members: packages/*, builtin_packs/*)
uv.lock
docs/                     these instructions
scripts/                  repo tooling (check_legacy_untouched.py, gen_ts_types.py)
tests/                    end-to-end tests (cross-package)
examples/                 sample workspace: plynx.yaml, workflows/, custom_packs/
packages/
  plynx-sdk/              stdlib-only. Imported inside node environments.
    pyproject.toml
    src/plynx_sdk/
      __init__.py         exports Op, op, Media, Range, Directory, checkpoint types
      op.py               Op base class and @op decorator
      types.py            semantic media aliases (PdfFile, AudioWav, ...)
      protocol.py         IPC manifest dataclasses (inputs/outputs/checkpoint)
      harness.py          child entrypoint: python -m plynx_sdk.harness
      checkpoint.py       CheckpointInterrupt, replay logic
  plynx/                  engine, CLI, server
    pyproject.toml
    src/plynx/
      cli/                click commands: run, validate, resume, run-node, runs, ops, clean, ui, init
      workflow/           workflow.yaml models (pydantic), loader, writer, validator
      registry/           static AST extraction, registry cache, workspace discovery
      engine/             scheduler, executor, runner, procgroup
      store/              SQLite access, run directories, event log
      cas/                blob store, hashing, cache key, GC
      server/             FastAPI app, routes (ops, runs, workflows), state, REST, SSE
      config.py           plynx.yaml workspace config loader
      api_models.py       pydantic models for REST/SSE (source of TypeScript types)
      static/             built UI (generated, gitignored)
ui/                       React + TypeScript + Vite
  src/
    api/                  generated types + REST/SSE client
    components/           common UI components, PortInput, SearchBar, FeatherIcon
    graph/                React Flow editor, palette, inspector, nodes
    stepper/              Stepper view, stage cards, checkpoint cards
    previewers/           artifact previewers
    router/               view router and navigation
builtin_packs/            Node Packs shipped with plynx (tracked)
  standard_io/            pyproject.toml, src/standard_io/ (stdlib-only, bundled in wheel)
custom_packs/             user packs (gitignored, .gitkeep tracked) — only in workspaces
```

A **workspace** is a user project directory. Its root is discovered by scanning upward for:
1. Nearest ancestor containing `.plynx/` or `plynx.yaml`.
2. Nearest ancestor containing `.git/`.
3. Nearest ancestor containing `pyproject.toml` (excluding `custom_packs/`).
4. Falling back to the working directory.

Workspace layout:

```text
plynx.yaml                optional config
workflows/**/*.yaml       workflows
workflows/.<name>.layout.json   Graph coordinates (sidecar, UI-owned)
custom_packs/                   user packs (searched after the packs shipped inside the plynx wheel)
.env                      secrets (gitignored)
.plynx/                   runtime state (gitignored)
  plynx.db                SQLite
  runs/<run_id>/          run directories
  cache/blobs/ab/ab12...  content-addressed blobs
  envs/<pack>-<hash>/     uv virtual environments
  registry_cache.json
```

## Stack

| Area | Choice |
|---|---|
| Python | >= 3.11. Windows, macOS, Linux. |
| Packaging | `uv` workspace. Dist names `plynx` and `plynx-sdk`, version `2.0.0`. |
| SDK dependencies | stdlib only. Wire models are `dataclasses`. |
| Engine dependencies | `pydantic>=2` (workflow, REST, SSE models), `fastapi`, `uvicorn`, `click`, `ruamel.yaml` (round-trip YAML writes), `python-multipart` (file uploads). |
| Scheduling | `graphlib.TopologicalSorter` + `asyncio` + `asyncio.Semaphore(concurrency)`. |
| Child processes | `uv run` (or `sys.executable -B` for stdlib-only built-in packs), one per node attempt, in its own process group. |
| State | SQLite (WAL) via stdlib `sqlite3`, called through `asyncio.to_thread`. |
| Lint / types / tests | `ruff`, `mypy --strict`, `pytest`. |
| UI | Vite, React, TypeScript strict, Tailwind, `@xyflow/react`, `dagre`. No component library. |
| UI types | Generated from the pydantic JSON Schema (`scripts/gen_ts_types.py`). Never hand-written. |

## Invariants

1. `plynx-sdk` imports only the standard library. Node environments never install `plynx`.
2. `workflow.yaml` holds logic only. No coordinates, no sizes. Layout lives in the sidecar.
3. Every node runs in its own process. Only files and JSON cross a process boundary. No in-memory objects.
4. SQLite and files on disk are the ground truth. SSE events are push notifications that can be lost.
5. Within one run, a node's completed outputs never change, even when `CACHEABLE = False`.
6. A fresh run starts with empty node directories. Cache lookup applies only to fresh runs. `plynx resume` reuses the run's own outputs.
7. Paths in node manifests are relative to the node directory, use `/`, and never contain `..`.
8. Times are UTC float seconds (`time.time()`).
9. Files shared between processes are written atomically (write temp, then `os.replace`).
10. Secrets live in `.env` or the host environment. They are never written to snapshots, manifests, logs by the engine, or the database.
11. Workflows are strict DAGs. Inter-stage edges go forward only.
12. Node outputs enter the blob store read-only. Nodes receive inputs read-only.
13. Engine code is split so that only `engine/procgroup.py` contains OS-specific process-tree code.
14. Every seam has a typed definition (dataclass, pydantic model, or generated TypeScript type) before its implementation.
15. The server binds to `127.0.0.1` and has no authentication, because it can run arbitrary code. Binding elsewhere is a non-goal.

## Executors

The engine talks to a node through the `Executor` protocol in `plynx/engine/executor.py`:

| Method | Meaning | v2.0.0 |
|---|---|---|
| `run(request) -> NodeResult` | Execute a node now, in this machine, and wait. | `LocalExecutor` implements it. |
| `launch(request) -> LaunchHandle` | Hand a node to an external engine and return immediately. | Signature only. Raises `NotImplementedError`. |

`plynx run` calls `LocalExecutor` in the same process. No server is needed. `plynx ui` runs the same engine inside the server process when a run is started from the browser.

## Who owns a run

One process owns a run at a time (`RUNS.owner_pid`). Other processes (browser, second CLI) interact only through SQLite and the run directory:

- **Watching:** the server tails `.plynx/runs/<run_id>/events.jsonl` and the log files and emits SSE. A run started from the CLI is visible in the UI.
- **Answering and cancelling:** a client writes the answer or `cancel_requested` row. The owner polls SQLite every 200 ms. First answer wins (`UPDATE ... WHERE answer IS NULL`).
- **Dead owner:** a run whose `owner_pid` is gone is marked `FAILED` (`engine_died`) on server start or `plynx runs`. `plynx resume` takes ownership.

## Statuses (single source)

| Entity | Values |
|---|---|
| Node | `PENDING`, `BUILDING_ENVIRONMENT`, `RUNNING`, `WAITING_FOR_USER`, `SUCCESS`, `FAILED`, `CANCELED`, `BLOCKED` |
| Run | `RUNNING`, `WAITING_FOR_USER`, `SUCCESS`, `FAILED`, `CANCELED` |

`BLOCKED` means a dependency is `FAILED` or `CANCELED`. A run is `WAITING_FOR_USER` when nothing is running and at least one checkpoint or stage approval is open. A cache hit is `SUCCESS` with `cache_hit = true`.

## Non-goals (do not build)

- MongoDB, Flask, Docker, Docker Compose, Kubernetes, Celery, Redis, any database server.
- Users, login, tokens, IAM, multi-user isolation.
- S3, GCS, SSH or any remote artifact storage.
- Distributed workers, worker server, `launch` implementation.
- Recursive sub-graphs, `include:`, templates, hubs, a node database.
- Dynamic fan-out (`map:`). Batching happens inside Python nodes with `Directory` or lists of paths.
- `AgentOp`, agent CLI adapters, MCP server. They are in [TODO.md](TODO.md).
- API key vault, model selector, marketplace, `plynx pack install`.
- Tauri or desktop packaging.
- Real-time streaming or audio DSP inside the engine.
- Step debugger and breakpoints. (Checkpoints and stage approvals are not breakpoints.)
- Inline editing of output artifacts.
- Migration tools or compatibility with v1 workflows, runs, or databases.
- Backend graph layout (Graphviz, NetworkX).
- Any import of the legacy package.

## Key behaviors

- **Cache key:** `sha256(op_entrypoint + file_sha256 + uv_lock_sha256 + inputs_hash + params_hash)`. Exact canonicalization in PROTOCOL.md. Identical output bytes end the cascade (early cutoff).
- **Checkpoints:** `self.checkpoint(...)` raises an interrupt on first call. The child writes `checkpoint.json` and exits 10. After an answer, the node is re-run from the top and the call returns the stored answer. See [guides/author_pack.md](guides/author_pack.md) for the idempotency rule. A checkpoint answer is not remembered between fresh runs in v2.0.0.
- **Stage gates:** `require_approval: true` pauses the run after all nodes of the stage reach `SUCCESS`, before any node of a later stage starts.
- **Failure:** a failed node blocks only its dependents. Independent branches finish. The run ends `FAILED`.
- **Cancel / timeout:** the whole process tree is killed. POSIX: `os.killpg`. Windows: `taskkill /T /F`. Both inside `procgroup.py`.
- **First run:** the engine emits `BUILDING_ENVIRONMENT` while `uv` creates an environment.
- **Environments:** `UV_PROJECT_ENVIRONMENT=.plynx/envs/<pack>-<hash(pyproject+lock)>`, and `uv run --frozen`. Stdlib-only built-in packs (`standard_io`) run directly with `sys.executable -B`, `PYTHONPATH` pointing to the pack source, and `PYTHONDONTWRITEBYTECODE=1` so packs inside `site-packages` stay read-only.
- **Pack code reuse:** one pack is one `uv` project; ops in a pack share helpers.
- **Op definition:** a class (`Op`) or a function (`@op`). Both produce the same registry schema. Metadata must be literals so static AST reading works. See PROTOCOL.md "Op declaration subset".

## Architectural decisions

| # | Decision |
|---|---|
| 1 | SDK is stdlib-only with dataclass wire models. Pydantic is engine-only. TypeScript types are generated from pydantic. |
| 2 | Op reference in YAML: `op: <pack>/<module>:<Name>`, for example `standard_io/text:Concat`. |
| 3 | Environments live in `.plynx/envs/`, not in pack directories. |
| 4 | Node inputs are materialized as read-only hard links (or copies) under `inputs/<port>/<original_filename>` so file extensions survive. |
| 5 | Directories are stored as a tree of file blobs and rebuilt on demand. |
| 6 | `events.jsonl` per run is the SSE source. SQLite polling is the cross-process bus. |
| 7 | CLI is `click`. UI uses Tailwind and native React state with no component library. |
| 8 | Exit 137 is dropped. Engine-initiated kill is `CANCELED`. Other non-zero exits or signals are `FAILED`. |
| 9 | `plynx run --no-cache` exists as the escape hatch for the cache-key blind spot (shared helper edits). |
| 10 | CI runs on Linux, macOS, Windows. Provider: GitHub Actions workflow added as `.github/workflows/v2-*.yml` (the only allowed file outside `v2/`, add-only). |
