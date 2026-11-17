# Plan (PLynx v2.0.0)

Do the first unchecked task. One task = one commit. Tick the box in the same commit. A task is done only when its **Accept** line passes and the checks in `AGENTS.md` pass. If an acceptance line cannot be met, stop and ask.

Phases 1 to 7 replace mocks from Phase 0 one seam at a time. The end-to-end test from task 0.11 stays green after every task.

## Phase 0: Walking skeleton (real signatures, mocked internals)

Goal: the thinnest path `CLI -> scheduler -> store -> events -> SSE -> UI`, with a fake executor. It proves the formats in [PROTOCOL.md](PROTOCOL.md) and the module boundaries before real code exists.

- [x] **0.1 Scaffold.** Create `pyproject.toml` (uv workspace), `packages/plynx-sdk`, `packages/plynx`, `builtin_packs/standard_io` (empty), `tests/`, `examples/`, ruff/mypy/pytest config, and `scripts/check_legacy_untouched.py` (fails when `git diff --name-only master...HEAD` lists a file outside `v2/`, except new files matching `.github/workflows/v2-*.yml`).
  Accept: `uv sync` in this folder works and ignores the legacy root `pyproject.toml`; `uv run pytest` passes a placeholder test; the check script returns 0 on a clean branch and 1 when a legacy file is modified (tested in a temp git repo).
- [x] **0.2 SDK wire types.** `plynx_sdk/protocol.py`: dataclasses for `InputsManifest`, `OutputsManifest`, `ResultManifest`, `CheckpointManifest`, value kinds (`scalar`, `file`, `directory`), with `to_json()` and `from_json()` that validate. Stdlib only.
  Accept: every JSON example in PROTOCOL.md section 5 is a fixture in `tests/fixtures/` and round-trips unchanged; invalid fixtures (missing `schema`, `..` in a path, scalar over 1 MiB) are rejected; `mypy --strict` passes.
- [x] **0.3 Engine models.** `plynx/workflow/models.py` (pydantic: `Workflow`, `Stage`, `NodeSpec`, reference parsing with the `$` rules), `plynx/api_models.py` (statuses, `RunState`, the seven event types as a tagged union, REST bodies).
  Accept: the example workflow parses; fixtures for unknown keys, bare `$` strings, `$$` escape, and bad node IDs fail with clear messages; statuses match ARCHITECTURE.md exactly.
- [x] **0.4 Generated TypeScript types.** `scripts/gen_ts_types.py` writes `ui/src/api/types.gen.ts` from the pydantic JSON Schema.
  Accept: running it twice produces no diff; a test fails if the committed file is stale.
- [x] **0.5 Fake registry and validator.** `registry/` interface (`OpRegistry` protocol) with an in-memory `FakeRegistry`. `workflow/validator.py`: unknown op, missing node reference, unknown output, cycle (`graphlib.CycleError`), backward stage edge, port type mismatch.
  Accept: `plynx validate examples/workflows/foo_or_woo.yaml` exits 0; one fixture per error kind exits 1 with the message naming the node.
- [x] **0.6 Store and event log (real).** `store/`: SQLite schema from PROTOCOL.md section 7, `RunStore`, run directory creation, `EventLog` (append with `seq`, read after `seq`).
  Accept: tests cover first-answer-wins, `seq` ordering under two writers (processes), and WAL access from two processes.
- [x] **0.7 Executor protocol, fake executor, real scheduler.** `engine/executor.py` (`Executor.run`, `Executor.launch` raising `NotImplementedError`), `engine/fake_executor.py` (scripted results, delays, failures, one checkpoint), `engine/scheduler.py` (`graphlib` + asyncio + semaphore, statuses, `BLOCKED`, events written to the store).
  Accept: a 4-node diamond runs; a failing node blocks only its dependents while the other branch finishes; `concurrency=1` never overlaps two nodes; events arrive in a valid order (`PENDING` -> `RUNNING` -> terminal).
- [x] **0.8 CLI `run` (skeleton).** `plynx run <workflow>` wires loader, validator, scheduler, store, and an executor factory that returns the fake executor.
  Accept: `plynx run examples/workflows/foo_or_woo.yaml` exits 0, prints one line per node status, leaves a run directory, `runs`/`node_runs` rows, and `events.jsonl`.
- [x] **0.9 Server skeleton.** FastAPI app: `GET /health`, `GET /runs/{id}`, `POST /runs`, `GET /runs/{id}/stream` (tails `events.jsonl`, supports `Last-Event-ID`).
  Accept: a test starts a run with the CLI in another process and the stream delivers the same ordered events; reconnect with `Last-Event-ID` returns only later events.
- [x] **0.10 UI skeleton.** `ui/`: Vite + React + TypeScript strict + Tailwind. One page: pick a run id, show node statuses live from the stream, using only generated types. `npm run build` writes into `packages/plynx/src/plynx/static/`. `plynx ui` serves it.
  Accept: `npm run lint`, `typecheck`, `test` pass; a vitest test feeds recorded events into the state reducer; the server returns the built `index.html` at `/`.
- [x] **0.11 Skeleton end-to-end test.** `tests/e2e/test_skeleton.py` runs the CLI as a subprocess on `foo_or_woo.yaml`: with `--non-interactive` the fake checkpoint gives exit 2; with `--answer pick.cp_0=foo` it gives exit 0 and the `echo` node receives `foo`.
  Accept: passes on Linux, macOS, and Windows. This test is the contract for all later phases.
- [x] **0.12 Measurement spike (no production code).** Measure and record in the table below: `uv run` start time per node (cold environment, warm environment), AST extraction time for 100 ops, `os.link` behavior and fallback on each OS, SQLite polling cost at 200 ms.
  Accept: the numbers are in the table. **Stop and tell the owner** if warm start is above 1 s per node or extraction above 50 ms for 100 ops. The chat's "<1 ms", "<10 ms", "0 ms" figures are unverified claims.

| Measurement | Linux | macOS | Windows |
|---|---|---|---|
| `uv run` warm start per node | 12.6 ms median (14.6 ms mean) | 24.9 ms median (27.0 ms mean) | pending CI (7.2) |
| `uv run` cold start (new env) | 21.6 ms | 54.0 ms | pending CI (7.2) |
| AST extraction, 100 ops | 6.5 ms | 5.9 ms | pending CI (7.2) |
| Hard link / fallback | `os.link` 0.02 ms / `copy2` 0.44 ms (1 MiB; `EXDEV` across mounts falls back) | `os.link` 0.19 ms / `copy2` 0.24 ms (1 MiB; `EXDEV` across volumes falls back) | NTFS `os.link`; cross-drive `OSError` falls back to `copy2` (pending CI 7.2) |
| SQLite polling cost at 200 ms | 0.11 ms / poll (0.06% duty cycle) | 0.34 ms / poll (0.17% duty cycle) | pending CI (7.2) |

## Phase 1: Real node execution

- [x] **1.1 SDK authoring API.** `Op`, `@op`, `Media`, `Range`, `Directory`, semantic aliases, `CheckpointInterrupt`. Stdlib only.
  Accept: both forms from PROTOCOL.md section 3 import and run in plain Python; importing `plynx_sdk` imports nothing outside the standard library (test checks `sys.modules`).
- [x] **1.2 Harness.** `python -m plynx_sdk.harness` reads `inputs.json`, calls the op, validates the result, writes `outputs.json`, maps failures to exit codes 1 and 2.
  Accept: run directly (no `uv`) on a fixture node directory for success, op exception, bad outputs, missing op.
- [x] **1.3 Checkpoint replay.** `checkpoint()` per PROTOCOL.md: id by call index, write `checkpoint.json`, exit 10; replay with answers.
  Accept: a fixture op asking "foo or woo?" exits 10 first and returns the answer on the second run; `except Exception` in the op does not swallow the interrupt.
- [x] **1.4 Process groups.** `engine/procgroup.py`: start a process in its own group (POSIX `start_new_session`, Windows `CREATE_NEW_PROCESS_GROUP`), kill the tree (`os.killpg`, `taskkill /T /F`).
  Accept: a test spawns a child that spawns a grandchild; after kill neither is alive. Passes on all three OSes.
- [x] **1.5 `LocalExecutor.run`.** Write `inputs.json`, build the command with `uv run --frozen`, set `UV_PROJECT_ENVIRONMENT`, emit `BUILDING_ENVIRONMENT` on first environment build, capture logs to `logs/`, map exit codes, support timeout and cancel.
  Accept: runs the `standard_io` fixture op through a real `uv` process; exit-code table in PROTOCOL.md is covered by tests; the executor factory now returns `LocalExecutor`; task 0.11 still passes using real ops.
- [x] **1.6 Environment and secrets.** `.env` reader (minimal, no dependency), `env_passthrough`.
  Accept: a value in `.env` reaches the child; the value never appears in `run_manifest.json`, snapshots, the database, or `events.jsonl` (test greps them).
- [x] **1.7 `standard_io` pack.** Demo ops: `AskFooOrWoo`, `Echo`, `Concat`, `ReadText`, `WriteText`.
  Accept: `examples/workflows/foo_or_woo.yaml` runs end to end with real child processes and a real `uv.lock`.

## Phase 2: Registry and validation

- [x] **2.1 AST extractor, class form.** Per PROTOCOL.md section 3.
  Accept: extracts title, category, cacheable, ports, defaults, docstring from fixtures without importing them (fixture imports a package that is not installed).
- [x] **2.2 AST extractor, function form and aliases.** `@op`, module-level TypedDict outputs, `Literal`, `Range`, same-file `Annotated` aliases, `plynx_sdk.types` aliases.
  Accept: class and function fixtures for the same op produce equal registry entries.
- [x] **2.3 Invalid ops.** Anything outside the subset yields `valid: false` and a reason, never a crash.
  Accept: fixtures for computed `TITLE`, custom base class, unknown annotation each give the documented reason.
- [x] **2.4 Pack discovery and cache.** Search wheel-shipped packs, `builtin_packs/` (repo), `custom_packs/`; `registry_cache.json` keyed by file mtime.
  Accept: touching one file re-parses only that file; deleting the cache rebuilds it.
- [x] **2.5 Real validator.** Replace `FakeRegistry`: port types and media compatibility, required inputs, unbound run inputs, missing `uv.lock` warning.
  Accept: all Phase 0 validator fixtures still pass against the real registry; media mismatch is rejected, `Path` to `PdfFile` is accepted.
- [x] **2.6 `plynx ops`.** Human table and `--json`.
  Accept: output lists every op in `standard_io`.

## Phase 3: Artifacts and cache

- [x] **3.1 Blob store.** Hash a file, store as `blobs/ab/<sha256>`, read-only, `os.link` then `shutil.copy2` fallback.
  Accept: duplicate content is stored once; the fallback is exercised by a test that forces `OSError`; stored blobs reject writes.
- [x] **3.2 Ingest outputs.** Files and directories (tree hash) into the blob store; write `result.json`.
  Accept: directory with nested files round-trips; `tree_sha256` matches the PROTOCOL.md definition.
- [x] **3.3 Materialize inputs.** Build `inputs/<port>/<filename>` as read-only hard links or copies; write `inputs.json`.
  Accept: a node that tries to write to an input fails; the file extension is preserved.
- [x] **3.4 Cache key.** Exact formula from PROTOCOL.md section 6.
  Accept: golden test with a fixed expected hash; each component change alters the key; a change in an unrelated file of the pack does not.
- [x] **3.5 Cache hits.** Lookup in fresh runs for `CACHEABLE` ops; `--no-cache`; missing blob is a miss.
  Accept: second run of the same workflow reports `cache_hit = true` for all nodes and starts no child process (test counts spawns); deleting a blob turns that node into a miss without an error.
- [x] **3.6 Early cutoff.** Downstream key depends on output hashes.
  Accept: change an upstream input so its output bytes stay identical; downstream nodes still hit.
- [x] **3.7 `plynx clean`.** Mark and sweep, `--days`, `--dry-run`, pinned runs kept.
  Accept: unreferenced blobs and stale `cache_index` rows are removed; referenced blobs survive; dry run changes nothing.
- [x] **3.8 Size budget.** `cache.max_size` LRU by `last_accessed_at`.
  Accept: with a small budget the oldest unreferenced blobs go first.

## Phase 4: Interaction and recovery

- [x] **4.1 Checkpoints in the engine.** Exit 10 -> `CHECKPOINTS` row, `WAITING_FOR_USER`, `node_checkpoint` event; answer -> re-run with answers; only dependents wait.
  Accept: in a diamond, the branch not behind the checkpoint finishes while the question is open; `checkpoint_resolved` is emitted once.
- [x] **4.2 CLI interaction.** Interactive prompt `[1-N]`/text, `--answers`, `--answer`, `--non-interactive`, exit code 2.
  Accept: the Phase 0 end-to-end test passes unchanged against real execution; piped stdin drives the interactive prompt in a test.
- [x] **4.3 Stage gates.** `require_approval: true` pauses after the whole stage succeeds and before the next stage starts.
  Accept: no node of stage N+1 has `started_at` before the approval time; `stage_approval` and `stage_resolved` events appear.
- [x] **4.4 Resume.** `plynx resume <id>` for failed and waiting runs; reuses the run's own outputs (even for `CACHEABLE = False`); takes ownership.
  Accept: fix a failing node's source, resume, only that node and its dependents run.
- [ ] **4.5 Cancel.** Local Ctrl-C and cross-process `cancel_requested`; process tree killed; nodes `CANCELED`; exit 130.
  Accept: no child or grandchild survives; a second process can cancel a run owned by the first.
- [ ] **4.6 Dead owner.** Detect a gone `owner_pid`, mark the run `FAILED` (`engine_died`).
  Accept: kill -9 the owner, the next `plynx runs` shows `FAILED`, `resume` continues.
- [ ] **4.7 `plynx run-node`.** Per PROTOCOL.md section 11.
  Accept: re-runs a failed node from its directory in a scratch copy and prints the traceback; SQLite is unchanged.
- [ ] **4.8 `plynx runs` and prefix IDs.**
  Accept: a unique prefix resolves; an ambiguous prefix lists candidates and exits 1.

## Phase 5: Server

- [ ] **5.1 Read endpoints.** `ops`, `workflows`, `workflows/{path}`, `workflows/{path}/inputs`, `runs`, `runs/{id}`.
  Accept: responses validate against `api_models.py`; `inputs` lists unwired ports with stage IDs.
- [ ] **5.2 Run control.** `POST /runs`, `cancel`, `resume`, answer, approve.
  Accept: a run started over REST can be answered and approved over REST; the double-answer test returns a conflict error.
- [ ] **5.3 Logs.** `logs` endpoint with offset; `node_log` SSE batching at most every 50 ms.
  Accept: a node printing 10 000 lines produces bounded SSE frames; history plus stream equals the file.
- [ ] **5.4 Outputs and uploads.** Blob download with media type; multipart upload into `.plynx/uploads/`.
  Accept: uploaded file path works as a run input; path traversal attempts are rejected.
- [ ] **5.5 Workflow save.** `PUT /workflows/{path}`: validate, write YAML round-trip (comments kept), write the layout sidecar.
  Accept: saving an unchanged workflow produces a byte-identical file; an invalid workflow is rejected and the file is untouched.
- [ ] **5.6 Clean and security.** `POST /clean`; loopback bind; CORS only for the dev origin.
  Accept: binding to a non-loopback host is refused; a cross-origin request from another origin gets no CORS header.

## Phase 6: UI

- [ ] **6.1 App shell.** Router, run list/history, workflow picker.
- [ ] **6.2 Run inputs form.** From `workflows/{path}/inputs`: file drop zones for `file`/`directory`, fields for scalars, defaults shown.
- [ ] **6.3 Stepper view.** Stage cards, parallel nodes as status rows, progress, `cache_hit` badge.
- [ ] **6.4 Logs panel.** History from REST, live lines from SSE, ANSI colors, download.
- [ ] **6.5 Checkpoint card.** Question, option buttons, freeform field; disappears on `checkpoint_resolved` in every tab.
- [ ] **6.6 Stage approval card.** "Approve & Continue".
- [ ] **6.7 Previewers.** Markdown, CSV, PDF, image, JSON, text. Copy and modify from legacy per [LEGACY_MAP.md](LEGACY_MAP.md).
- [ ] **6.8 Graph view, read-only.** React Flow, Dagre layout, stage group nodes, live status, `[ Stepper | Graph ]` toggle.
- [ ] **6.9 Graph editing: palette and nodes.** Palette grouped by `CATEGORY` with search (`/`, `Cmd+K`); add, duplicate, delete nodes.
- [ ] **6.10 Graph editing: wiring.** Drag edges between ports; reject type or media mismatches and backward stage edges with a visible reason.
- [ ] **6.11 Node inspector.** Edit literals from registry types, bind or unbind references, preview artifacts of the selected node.
- [ ] **6.12 Save and layout.** Save through `PUT /workflows`, sidecar for coordinates, dirty indicator.
- [ ] **6.13 Reload behavior.** Refresh during a run, during a checkpoint, and after a server restart restore the correct view from SQLite.

Accept for every 6.x: the component has a vitest test; `lint`, `typecheck`, `test` pass; the feature works against a real `plynx ui` server in a Playwright smoke test (added in 6.1 and extended per task).

## Phase 7: Packaging and agent docs

- [ ] **7.1 Wheel.** `uv build` for `plynx-sdk` and `plynx`; the `plynx` wheel contains built `static/` and the shipped `builtin_packs`.
  Accept: `uvx --from <wheel> plynx ui` serves the UI in a clean machine environment.
- [ ] **7.2 CI.** GitHub Actions `v2-ci.yml`: ruff, mypy, pytest, UI checks, wheel smoke test on Linux, macOS, Windows.
  Accept: green on all three. The workflow file is the only file added outside `v2/`.
- [ ] **7.3 Pack author and agent docs.** Finalize `PACK_RULES.md`; add short guides: create a workflow, author a pack, debug a failed node with `plynx run-node`.
  Accept: a fresh agent session given only these docs and the CLI creates and debugs a two-node workflow (record the transcript path in the commit message).
- [ ] **7.4 Quickstart README.**
  Accept: its commands work verbatim on all three OSes.

## Phase 8: Dogfood gate

- [ ] **8.1 Job Assistant workflow (headless).** Parse a portfolio, ask a checkpoint question, generate a letter with an LLM call (stubbed in CI). Second run with a different job description re-runs only downstream nodes.
  Accept: second run shows cache hits for every ingest node (test counts child spawns).
- [ ] **8.2 Owner trial.** The owner uses v2 for real tasks and records feedback in the `plynx_ideas` chat. Unresolved feedback about checkpoints or the Stepper becomes tasks here before Phase 9. This is the demand check for the unproven hypotheses in the chat.
  Accept: the owner writes "go" in the chat.

## Phase 9: Promotion (last stage)

Only after 8.2. Follow [WORKFLOW.md](WORKFLOW.md) section "Promotion". This is the only phase allowed to modify, move, or delete files outside `v2/`.

- [ ] **9.1** Freeze legacy: confirm tag `v1.12.0` and create branch `legacy/v1` from `master`.
- [ ] **9.2** Commit 1: delete legacy files (list in WORKFLOW.md).
- [ ] **9.3** Commit 2: `git mv` everything from `v2/` to the root. No content edits.
- [ ] **9.4** Fix CI paths and badges, tag `v2.0.0rc1`, run the full suite on all OSes.
- [ ] **9.5** Release `2.0.0`.
