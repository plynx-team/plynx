# Release Plan (PLynx v2.0.0)

Remaining work required to harden, clean up, and ship PLynx `v2.0.0`.
Supersedes the completed Phase 0–8 checklist in [PLAN.md](PLAN.md).

Work top to bottom. One task = one focused commit. Tick the box in the same commit when **Accept** and `AGENTS.md` checks pass.

---

## Phase R0: Packaging, Wheel Execution & Existing-Repo Workflow (P0 Blockers)

Goal: `pip install plynx` or `uv tool install plynx` works cleanly inside any external user repository on Linux, macOS, and Windows.

- [x] **R0.1 Fix `builtin_packs` packaging and execution outside the repo.**
  - Remove copied monorepo `uv.lock` files from `builtin_packs/*/`.
  - Decide and implement clean execution for `standard_io` (stdlib-only built-in pack): run directly using the current Python interpreter / `plynx` environment (zero `uv sync` needed, zero writes into `site-packages`), or ship standalone lockfiles with read-only-safe env creation.
  - Switch `packages/plynx/pyproject.toml` to declarative bundling (so `uv build` and `pip install` include `builtin_packs/standard_io` and `static/` without relying only on imperative staging in `scripts/build.py`). Pin `plynx-sdk>=2.0.0,<3.0.0` in `packages/plynx/pyproject.toml`.
  - Update `tests/test_wheel.py` to install the built wheels in an isolated temp directory outside the repo and **execute a real workflow** (`plynx validate` + `plynx run`) against `standard_io`.
  - **Accept:** `tests/test_wheel.py` executes a real `standard_io` node from the installed wheel in a fresh temp dir with no access to the source tree and no writes to `site-packages`.

- [x] **R0.2 Stop parent `uv.lock` traversal and fix custom pack discovery.**
  - In `engine/runner.py` and `cas/cache_key.py`, check ONLY `pack_dir / "uv.lock"` (remove `pack_dir.parents[:3]` traversal, which breaks user repos that have their own top-level `uv.lock`).
  - Wire `plynx.yaml` `packs:` into `LocalExecutor` (via a shared `WorkspaceConfig` loader used by both `PackRegistry` and `LocalExecutor`).
  - Give `custom_packs/` precedence over `builtin_packs/` only when explicitly intended, or reject duplicate pack names with a clear error; key packs consistently.
  - **Accept:** A test creates a temp user repo with an unrelated root `uv.lock` and a `custom_packs/my_pack/` (and a `plynx.yaml` `packs:` entry); both `plynx validate` and `plynx run` succeed.

- [x] **R0.3 Fix workspace root discovery and add `plynx init`.**
  - Update `find_workspace_root()` to scan upward in priority order: (1) `.plynx/` or `plynx.yaml`, (2) `.git/`, (3) `pyproject.toml`, (4) `cwd`. Avoid stopping at a nested `custom_packs/<pack>/pyproject.toml`.
  - Unify start-path handling across `validate`, `run`, `resume`, `runs`, `ops`, `clean`, and `ui`.
  - Remove hardcoded `examples/workflows` from default user workflow discovery in `server/app.py` (keep only `workflows`, or configure `examples/workflows` via this repo's `plynx.yaml`).
  - Implement `plynx init [dir]` (already listed in `PROTOCOL.md`): creates `.plynx/`, `workflows/`, `custom_packs/`, optional starter `plynx.yaml`, and appends `.plynx/` to `.gitignore` if inside a git repo.
  - **Accept:** Running `plynx init` in an existing repo sets up a working workspace; running `plynx ops` from inside `custom_packs/my_pack/` resolves the outer workspace root.

---

## Phase R1: Core Correctness, Data Integrity & Security (P0/P1)

- [x] **R1.1 Stop hardlinking external workspace inputs into CAS.**
  - In `cas/blob_store.py` and `cas/materialize.py`, copy (never hardlink) user/workspace input files into `.plynx/cache/blobs/` so PLynx never `chmod 0o444`s user files and later edits cannot corrupt CAS blobs. Keep hardlinks only for engine-owned `workdir/` outputs and materialized read-only inputs.
  - **Accept:** Test binds a writable workspace file as input, runs a workflow, verifies the user file remains writable, edits it in place, and verifies the CAS blob SHA-256 is unchanged.

- [x] **R1.2 Fix `uv` env atomic readiness and cross-process locking.**
  - In `engine/runner.py`, write an explicit `.plynx_env_ready` sentinel only *after* `uv sync` succeeds; guard env creation with a cross-process file lock (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) and clean up partial dirs on failure/cancel.
  - **Accept:** Test kills/fails mid-sync and verifies a subsequent run rebuilds cleanly instead of wedging on `pyvenv.cfg`.

- [x] **R1.3 Fix `$$` literal round-trip, `Optional[Path]` outputs, and input-resolution mismatches.**
  - Separate serialized wire syntax (`$$100`) from in-memory literal strings (`$100`) cleanly so `GET -> PUT /workflows/{path}` and inline `POST /runs` round-trip literal `$` strings without 422 errors. Do not hijack plain JSON dicts containing `"from_node"` unless tagged/valid.
  - Fix `plynx_sdk/harness.py` `_build_outputs_map` to handle `None` for `Path | None` and `Directory | None` outputs.
  - Align `validator.py`, `scheduler.py`, and `cas/materialize.py` on `node_id.port_name` vs bare `port_name`, allow empty string `""` for provided `str` inputs, fail clearly on missing literal file paths, and stop coercing `str`-typed CLI `--set` values via `json.loads`.
  - Print `run_id` in `plynx run` output (including on failure and exit 2).
  - **Accept:** Regression tests pass for each bug above.

- [x] **R1.4 Separate stage input gates from stage approval gates.**
  - Distinguish gate kind (`input` vs `approval`) in SQLite `stage_gates` schema, `api_models.py`, events, scheduler, and CLI (`cli/interaction.py`).
  - Ensure a stage with both deferred required inputs and `require_approval: true` triggers and resolves both gates cleanly without colliding.
  - **Accept:** Test runs a stage having both a deferred input and `require_approval: true`; both prompt and resolve cleanly via CLI and REST/SSE.

- [x] **R1.5 Fix `plynx clean` safety, path traversal, upload limits, and AST extractor bugs.**
  - Exclude active (`RUNNING`, `WAITING_FOR_USER`, `PENDING`) runs in `cas/clean.py`; reject `--days < 0` in CLI.
  - Validate `node_id` against `NODE_ID_PATTERN` (and check `relative_to`) in `/logs` and `/outputs` endpoints; stream uploads in chunks with a size limit and collision-safe naming in `POST /uploads`.
  - Fix `registry/extractor.py`: stop falling back to unrelated module `Outputs` TypedDict on function ops; fix `__init__.py` empty module IDs; stop false-positive `valid=False` entries on non-op helper classes; align missing return annotation handling with `harness.py`.
  - **Accept:** Security and regression tests pass for clean active-run protection, path traversal rejection, and AST edge cases.

---

## Phase R2: Performance & Runtime Stability (P1)

- [x] **R2.1 Fix SSE premature disconnect and eliminate 50Hz polling waste.**
  - Fix `server/app.py` `saw_terminal` logic so replaying an older `FAILED`/`CANCELED` event on a resumed run does not close the SSE stream while the run is `RUNNING`.
  - Replace 20ms (`50Hz`) full-file `events.jsonl` re-reads + full `workflow.snapshot.yaml` YAML/Pydantic reparsing with byte-offset tailing and lightweight status checks (e.g. `100–200ms` or event-driven notification).
  - **Accept:** Resumed run streams live events to completion; benchmark/test confirms SSE idle tick does not re-parse `workflow.snapshot.yaml`.

- [x] **R2.2 Harden `EventLog`, SQLite concurrency, GC, and server lifecycle.**
  - Replace `O_EXCL` lockfile + O(N²) full-file scan in `store/event_log.py` with `fcntl.flock` / Windows lock + tracked last `seq`.
  - Wrap `update_run_inputs` in `BEGIN IMMEDIATE`; avoid running `PRAGMA journal_mode=WAL` on every single query.
  - Add error-handling callback on server background run tasks (mark run `FAILED` on unexpected crash) and FastAPI `lifespan` shutdown hook to cancel active runs.
  - Fix `scheduler.resume()` so it respects `options.no_cache` instead of hardcoding `no_cache=True`.
  - Stop re-hashing `nodes/*/inputs/` on disk during GC/budget (track referenced blob hashes in manifests/SQLite).
  - Replace POSIX `ps` subprocess and Windows substring PID check in `procgroup.py` with safe checks (`os.kill(pid, 0)` on POSIX, exact PID match on Windows).
  - **Accept:** Concurrent writers, killed-writer recovery, resumed caching, and task crash tests pass.

---

## Phase R3: Domain-Agnostic Cleanup & Code Simplification (P1/P2)

- [x] **R3.1 Trim `builtin_packs/` to core, domain-agnostic `standard_io` only.**
  - Move `media_studio`, `pedalboard_studio`, and `podcast_studio` out of `builtin_packs/` into `examples/custom_packs/` (they remain runnable as examples, not bundled in the wheel).
  - Move hardcoded test toys (`AskFooOrWoo`, `SecretCodeChallenge`, `MultiStepQuestionnaire`) from `standard_io` into `tests/fixtures/`.
  - Upgrade `TemplateFormat` and `BundleDirectory` to use `ALLOW_EXTRA_INPUTS = True`; fix `BundleDirectory` missing-file/basename-collision bugs; use `.as_posix()` in `ListDirectory`; fix `JsonExtract` scalar JSON formatting.
  - Fix orphan/unwired nodes in remaining showcase workflows in `examples/workflows/`.
  - **Accept:** `builtin_packs/` contains only stdlib-only, cross-platform `standard_io`; all remaining example workflows have valid wiring with no fake/orphan nodes.

- [x] **R3.2 Remove test fakes, dead abstractions, and duplicate boilerplate in Python.**
  - Move `FakeRegistry`, `default_fake_ops` (536 lines), and `FakeExecutor` out of `packages/plynx/src/` into `tests/`.
  - Delete unused dead APIs: `Executor.launch()`, `LaunchHandle`, `spawn_process_group()`, `run_server()`, `ResultDirectoryEntry`, `Registry` alias, unused `approved_gates` set.
  - Create one small `WorkspaceConfig` loader (`plynx/config.py`) replacing the 4 duplicate `plynx.yaml` parsers, and wire `concurrency` (and `db` if kept, or drop `db` from `PROTOCOL.md`).
  - Deduplicate `_discover_builtin_packs_dirs`, `extractor.py` Assign/AnnAssign & positional/kwarg branches, `runner.py` `run_in_scratch`, and `scheduler.py` gate-wait logic.
  - Simplify `plynx_sdk/protocol.py` (eliminate triple validation on serialize and copy-pasted parse dispatchers).
  - Read package version from `importlib.metadata.version("plynx")` instead of 4 hardcoded `"2.0.0"` strings.
  - **Accept:** Zero test fakes in `src/`; all ruff/mypy/pytest checks pass; net LOC reduced significantly.

- [x] **R3.3 Break up Python god-functions.**
  - Split `Scheduler.run()` (873 lines) into focused methods/helper class (`_RunExecution`) with explicit state instead of 15 closure-captured variables.
  - Split `server/app.py` (`create_app()`, 865 lines) into clean route modules (`routes/workflows.py`, `routes/runs.py`, `routes/ops.py`) and explicit app state.
  - **Accept:** No function in `packages/plynx/src/` exceeds ~150 lines; all server and engine tests pass.

---

## Phase R4: UI Logical Fixes, Consolidation & Cleanup (P1/P2)

- [x] **R4.1 Fix broken UI flows & routing bugs.**
  - Fix `Router.tsx` 2-segment `:path*` bug (root-level workflows like `/editor/foo.yaml` fail to open) and decode URI segments.
  - Fix default editor experience: open `/editor/<path>` (and newly created workflows from `NewWorkflowModal`) in Graph view when editing, or make Stepper vs Graph mode crystal clear (never fabricate a fake `"RUNNING"` `"draft"` run state with `0%` progress in editor mode).
  - Fix `WorkflowEditor` live run bugs:
    - Filter open checkpoints by `!cp.answered_at` (not `cp.answer === null`).
    - Pass `workflow`, `runInputs`, `opsMap`, and `onApproved` to `StageApprovalCard` and `StepperView` so deferred stage inputs work.
    - Re-subscribe to SSE on `Resume Run`.
    - Render run-level `error` banner.
    - Disable ALL mutating toolbar buttons (`Save`, `Auto Layout`, `Duplicate`, `Delete`, `Disconnect`, stage delete) in Run Inspection mode; allow `onPaneClick` deselection in read-only mode.
    - Fix `Save & Run` to abort when `handleSave()` fails; run `prepareWorkflowForSave()` on in-memory runs too.
    - Scope `Escape` key handler so it does not hijack modals or freeform inputs.
  - Fix `LogsPanel`: fetch both `stdout` and `stderr` history via REST, reuse the active run SSE stream (no duplicate connection / shared `log_offset` bug), preserve original line numbers when filtering.
  - Remove hardcoded `/outputs/text` in `RunDetail.tsx`, fix `MarkdownPreviewer` link URL sanitization (`http:`/`https:`/`mailto:` only), and fix `RunInputsForm` required `bool` and invalid `json` handling.
  - **Accept:** Vitest tests cover every fixed bug above (no mocked-away false positives).

- [x] **R4.2 Unify Run Snapshot Inspection & fix `runDiff.ts`.**
  - Decide one clear model: Run Inspection mode renders the run's actual `workflow_snapshot` + `layout_snapshot` (read-only), not the live editor file. Reuse one shared `RunInspector` component between `/runs/:id` and the in-editor Run Inspection view (eliminate diverged `RunDetail.tsx` vs `WorkflowEditor.tsx` run views, and remove the redundant third Runs tab if `RunsHistoryPane` + `/runs` suffice).
  - Fix `runDiff.ts` false positives: do not treat runtime `run_inputs` for unbound ports as workflow edits; align diff direction (`+`/`-`) with the HUD banner copy; compute `StepperView` progress from snapshot nodes only.
  - Wire pagination (`limit`/`cursor` + `workflow_path` filter) on `GET /runs` so runs past #50 are not silently lost.
  - **Accept:** Launching an unmodified workflow with unbound inputs shows zero diff; inspecting an older run renders its true `workflow_snapshot`.

- [x] **R4.3 Decompose UI monoliths, unify widgets, and clean up CSS & E2E tests.**
  - Consolidate the 4 input widget implementations (`LiteralWidget`, `WorkflowNode`, `RunInputsForm`, `StageApprovalCard`) into one shared `PortInput` component; extend backend `WorkflowInputSpec` with `options`/`min`/`max`/`step`/`description`; remove the invalid `"Custom value..."` option for strict `Literal` ports.
  - Split `WorkflowEditor.tsx` (2,133 LOC) and `NodeInspector.tsx` (1,496 LOC) into focused components; fix React impure-updater undo/redo, node-switch key leak (`${nodeId}-${port.name}`), `Create & Move` stale slug, stage deletion reassign validation, Quick-Connect validation, and stop re-running Dagre on every render.
  - Stop storing mutable `viewport` in tracked `.layout.json` sidecars (keep viewport in `localStorage` or omit from git diffs).
  - Wrap legacy CSS in `@layer components` (or replace with Tailwind classes), remove dead v1 classes/undefined `--bg-tertiary`/`--bg-hover` vars and `!important` hacks, remove Google Fonts network call in `index.html`.
  - Fix `ui/playwright.config.ts` (remove hardcoded `/Users/khaxis/.local/bin/uv`) and update `ui/e2e/smoke.spec.ts` to match current routes/views without mutating tracked example files.
  - **Accept:** `npm run lint`, `npm run typecheck`, `npm test`, and Playwright smoke tests pass cleanly.

---

## Phase R5: Docs, README, User-Agent Guide & CI (P1)

- [x] **R5.1 Sync and trim living technical docs.**
  - Update `docs/PROTOCOL.md` to match actual REST API, CLI, gate kinds, and `plynx.yaml` keys.
  - Update `docs/ARCHITECTURE.md`: remove `(proposed)` tags, remove TanStack Query, fix workspace root rule, directory tree, and deps (`python-multipart`).
  - Compress `docs/UI_STYLE.md` (~60 lines of invariants, no copied `:root` CSS) and trim empty v1-diff table in `docs/TODO.md`.
  - **Accept:** Every command, config key, and endpoint in `PROTOCOL.md` and `ARCHITECTURE.md` matches the codebase.

- [x] **R5.2 Rewrite `README.md`, user/agent guides, and add doc-snippet tests.**
  - Rewrite `README.md` concisely: accurate Quickstart that works for `uvx`/`pip` installed users (`plynx init` + inline or starter workflow), accurate cache description (file bytes, not AST), accurate op list.
  - Merge `docs/PACK_RULES.md` + `docs/guides/author_pack.md` into one accurate, concise guide (fix broken class-attribute `Op` example, document `Directory`, `Literal`, `Range`, `Media`, `ALLOW_EXTRA_INPUTS`, `plynx ops --json`).
  - Rewrite `docs/guides/create_workflow.md` (fix `stages:` mapping schema, `--set` vs `--input`, remove nonexistent `--approve`) and `docs/guides/debug_failed_node.md` (accurate `run-node` output).
  - Add a concise, self-contained **User Agent Reference** (`docs/AGENT_GUIDE.md` — and ship/expose via `plynx` CLI or skill template) so an AI agent in any user repo knows how to inspect ops (`plynx ops --json`), write/validate/run/debug workflows, and add packs.
  - Add `tests/test_docs_snippets.py` that parses and validates the YAML/Python code blocks in docs/guides so drift breaks CI.
  - **Accept:** `tests/test_docs_snippets.py` passes; a fresh agent session can create, validate, and run a workflow in a blank repo using only the installed CLI + agent guide.

- [x] **R5.3 Fix CI pipeline (`v2-ci.yml`).**
  - Build UI assets before running `tests/test_wheel.py` (or exclude `test_wheel.py` from the pre-build pytest run so clean checkouts do not fail).
  - Add Playwright E2E job and `scripts/gen_ts_types.py --check`.
  - Verify green CI on Linux, macOS, and Windows (including the wheel-execution smoke test from R0.1).
  - **Accept:** `v2-ci.yml` is green on all 3 OSes.

---

## Phase 9: Promotion & Release (Owner-Gated)

Run only after R0–R5 are complete, CI is green on all 3 OSes, and the owner gives explicit approval. Follow [WORKFLOW.md](WORKFLOW.md) section "Promotion".

- [x] **9.1** Freeze legacy: confirm tag `v1.12.1` and create branch `legacy/v1` from `master`.
- [x] **9.2** Commit 1: delete legacy root files (preserving `.git`, `.github/`, `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `v2/`). Delete obsolete `v2/docs/PLAN.md`, `v2/docs/LEGACY_MAP.md`, `v2/docs/WORKFLOW.md`, and `v2/scripts/check_legacy_untouched.py`.
- [x] **9.3** Commit 2: `git mv` everything from `v2/` to repo root. No content edits.
- [x] **9.4** Commit 3: remove `working-directory: v2` and `check_legacy_untouched.py` from CI, rename `.github/workflows/v2-ci.yml` to `ci.yml`, update `AGENTS.md` (remove `v2/`-specific rules) and `README.md` (remove `cd plynx/v2`), update `CHANGELOG.md`.
- [x] **9.5** Tag `v2.0.0rc1`, run full CI + wheel smoke tests on all 3 OSes, publish `plynx-sdk` then `plynx` to PyPI, tag `v2.0.0`, and merge `v2` into `master`.
