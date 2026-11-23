# Workflow (git, atomic changes, legacy isolation)

## Branch and folders

- Work on branch `v2`, created from `master` (`master` is at tag `v1.12.1`, the legacy reference).
- All new work lives in `v2/`. `v2/` is the project root for every script, config, and document. Nothing inside `v2/` mentions `v2/` or reads outside it.
- Legacy files stay exactly as they are until Phase 9.
- Hotfixes to legacy go to `master` and are merged into `v2` with a normal merge. The check script ignores merged-in changes (three-dot diff).

## Commands run from `v2/`

Always run tools from the `v2/` folder. The legacy `plynx/` package sits one level up and has the same import name as v2. Running Python from the repo root would import the wrong one. v2 uses a `src/` layout and its own `.venv` to avoid it.

```bash
uv sync
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
uv run python scripts/check_legacy_untouched.py
cd ui && npm run lint && npm run typecheck && npm test
```

## Atomic changes

- One task from PLAN.md per commit. The task's checkbox is ticked in that commit.
- A commit contains: code, tests, docs for that task. Nothing else.
- No drive-by refactors. If you see a problem outside the task, note it in `docs/TODO.md` and move on.
- Message: `<phase.task>: <imperative summary>`. Example: `1.3: replay checkpoint answers in harness`. A new dependency adds a line `dep: <name> because <reason>`.
- Never commit generated build output (`static/`, `dist/`, `.venv/`, `node_modules/`) or anything under `.plynx/`.
- Generated files that are tracked (`types.gen.ts`) must be regenerated in the same commit as their source.

## Legacy isolation rules

1. Do not modify, rename, move, or delete any file outside `v2/` before Phase 9.
2. The only allowed addition outside `v2/` is a new `.github/workflows/v2-*.yml` file.
3. `scripts/check_legacy_untouched.py` enforces rules 1 and 2. It runs in CI and before every commit.
4. v2 code never imports the legacy `plynx` package.
5. Copying a legacy file into `v2/` and changing it is allowed. Record source path, destination, and what changed in `docs/LEGACY_MAP.md` in the same commit. Copy only what the current task needs.
6. Legacy services (MongoDB, Flask API) are run only with legacy tools from the repo root, for side-by-side checks. Legacy ports: `5005`, `5006`, `3001`, `27017`. v2 uses `8080` (server) and `3000` (Vite dev).

## Verifying against legacy

When a v2 task reproduces a legacy feature (cache hit, previewers, parameter widgets, DAG scheduling), run the legacy behavior first and compare. The checklist is in [LEGACY_MAP.md](LEGACY_MAP.md). Record any difference you keep on purpose in `docs/TODO.md` under "Intentional differences".

## Promotion (Phase 9)

Done once, by the owner or under the owner's explicit instruction.

1. Verify: all tasks in `RELEASE_PLAN.md` (R0–R5) are ticked, CI is green on all three OSes, and the owner gives explicit approval.
2. `git branch legacy/v1 master` and confirm tag `v1.12.1` exists. Legacy remains reachable there.
3. Commit 1 on `v2`: delete every tracked top-level path except `.git`, `.github/`, `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `v2/`. (`v2/` has its own `.gitignore`.) That removes `plynx/`, `ui/`, `tests/`, `docs/`, `docker/`, `kubernetes/`, `scripts/`, `.circleci/`, `.dockerfile`, `.dockerignore`, `.gitmodules`, `.isort.cfg`, `.pre-commit-config.yaml`, `Makefile`, `setup.py`, `setup.cfg`, `requirements*.txt`, `config.yaml`, `template_config.yaml`, `docker-compose*.yml`, `wsgi.py`, `pylintrc`, `MANIFEST.in`, `pyproject.toml`, `AGENTS.md`, `README.md`, `.agents/`, and the rest. Also delete `v2/docs/PLAN.md`, `v2/docs/LEGACY_MAP.md`, `v2/docs/WORKFLOW.md`, `v2/docs/RELEASE_PLAN.md`, and `v2/scripts/check_legacy_untouched.py`.
4. Commit 2: `git mv v2/* .` and `git mv v2/.[!.]* .` (hidden files). No content edits. Because nothing in `v2/` refers to `v2/`, paths keep working.
5. Commit 3 (only what must change): remove `working-directory: v2` and `check_legacy_untouched.py` from CI, rename `.github/workflows/v2-*.yml` to drop the prefix, remove temporary `v2/` rules from `AGENTS.md`, update `README.md` clone instructions/badges, and add the `v2.0.0` entry to `CHANGELOG.md`.
6. Tag `v2.0.0rc1`, run the full suite and the wheel smoke test on all OSes, then publish `plynx-sdk` followed by `plynx` to PyPI and tag `v2.0.0`.
7. Merge `v2` into `master` as a normal merge (history of both lines is preserved). No force push.
