# AGENTS.md (PLynx v2)

Instructions for AI coding agents working on the PLynx v2 codebase.
`v2/` is the active project root until Phase 9 promotion. Legacy v1 files one level up are read-only reference.

## Philosophy

- **Code-first workflows and operations.** Workflows are plain YAML; operations are plain Python (`Op` or `@op`). Both are Git-friendly, diffable, and easy to read.
- **Reuse over reinvention.** Build small, general-purpose operations that compose cleanly. Do not overfit core code or built-in packs to one demo use case.
- **Minimal abstractions.** Use standard library and built-in data structures first. Add a class, protocol, or layer only when current features clearly require it. Code must stay readable by humans.
- **Human-friendly workflows.** Users should understand, run, and debug workflows without fighting graph clutter or opaque runtime errors. Listen to real user feedback and simplify friction.
- **Docs match code.** Every change to behavior, CLI flags, API models, schemas, or file layout must update the matching doc in the same commit. Stale docs are bugs.

## Read First

1. [docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md) — active checklist to ship `v2.0.0`. Do the first unchecked task unless told otherwise.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module boundaries, invariants, non-goals.
3. [docs/PROTOCOL.md](docs/PROTOCOL.md) — exact wire formats, YAML schema, REST API, CLI, SQLite tables.
4. [docs/WORKFLOW.md](docs/WORKFLOW.md) — git workflow, legacy isolation, and Phase 9 promotion steps.

## Code Structure

- `packages/plynx-sdk/src/plynx_sdk/` — zero-dependency SDK (`Op`, `@op`, types, `checkpoint()`, `protocol.py`, child-process `harness.py`). Stdlib only.
- `packages/plynx/src/plynx/` — core engine and CLI:
  - `workflow/` — YAML workflow models and static DAG validator.
  - `registry/` — static AST op extractor (`extractor.py`) and pack discovery (`pack_registry.py`).
  - `engine/` — `graphlib` scheduler, local `uv` runner, env loader, process-group kill.
  - `cas/` — content-addressed blob store, cache keys, input materialization, output ingestion, GC.
  - `store/` — SQLite run/node/checkpoint/cache store and append-only `events.jsonl`.
  - `server/` — FastAPI REST + SSE server and bundled static UI.
  - `cli/` — Click CLI (`validate`, `run`, `resume`, `run-node`, `runs`, `ops`, `clean`, `ui`, `init`).
  - `api_models.py` — Pydantic models that generate `ui/src/api/types.gen.ts`.
- `builtin_packs/` — core domain-agnostic packs shipped in the `plynx` wheel (`standard_io` only).
- `examples/` — optional demo packs (`examples/custom_packs/`) and showcase workflows (`examples/workflows/`).
- `ui/` — React + TypeScript + Vite web app (Stepper + Graph editor + Run inspector). Builds into `packages/plynx/src/plynx/static/`.
- `scripts/` — `gen_ts_types.py`, `build.py`, `check_legacy_untouched.py`.
- `tests/` — pytest unit, integration, e2e, and wheel smoke tests.

## Hard Rules

- **Root is `v2/` (until Phase 9).** Run all commands from `v2/`. Never write paths containing `v2/` or `../`.
- **Do not touch legacy (until Phase 9).** Never modify files outside `v2/` (except `.github/workflows/v2-*.yml`). Verify with `uv run python scripts/check_legacy_untouched.py`.
- **Keep dependencies light.** `plynx-sdk` must have zero third-party dependencies. Core `plynx` keeps only lightweight CLI/HTTP/YAML packages. Heavy libraries belong only in isolated Node Packs.
- **No test code in production packages.** Test fakes and demo fixtures live in `tests/`, never in `packages/plynx/src/`.
- **Cross-platform.** Support Linux, macOS, and Windows. Use `pathlib`, POSIX forward slashes in manifests/outputs, no OS-specific shell commands in core or built-in packs.
- **Types stay synced.** After changing `api_models.py` or `workflow/models.py`, run `uv run python scripts/gen_ts_types.py` and commit `ui/src/api/types.gen.ts`.
- **Concise technical English.** Write comments, docstrings, and docs in short, clear, standard engineering English. Avoid fluff and marketing language. Keep one fact in one place.
- **Do not guess.** If a spec or product call is unclear, stop and ask the owner.

## Verification (Before Every Commit)

Run from `v2/`:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
uv run python scripts/gen_ts_types.py --check
uv run python scripts/check_legacy_untouched.py
```

If `ui/` changed:

```bash
cd ui && npm run lint && npm run typecheck && npm test
```

If packaging or `builtin_packs/` changed:

```bash
uv run python scripts/build.py
uv run pytest tests/test_wheel.py
```

## Definition of Done

1. Acceptance criteria for the task pass.
2. All checks above pass.
3. Matching docs (`README.md`, `PROTOCOL.md`, `ARCHITECTURE.md`, guides, or `AGENTS.md`) are updated if behavior or structure changed.
4. Task checkbox in `docs/RELEASE_PLAN.md` is ticked in the same commit.
