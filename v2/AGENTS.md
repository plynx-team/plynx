# AGENTS.md (PLynx v2)

You are building PLynx v2.0.0 in `v2/`. This folder is the project root. The legacy v1 code lives one level up and is reference material only.

## Read first, in this order

1. `docs/ARCHITECTURE.md`: layout, invariants, non-goals.
2. `docs/PROTOCOL.md`: exact formats. Code must match it. If they disagree, stop and ask.
3. `docs/PLAN.md`: do the first unchecked task. Only that task.
4. `docs/WORKFLOW.md`: git and legacy rules.
5. `docs/PACK_RULES.md`: before writing any Node Pack or built-in op.

## Hard rules

- **v2 is the root.** Never write a path that mentions `v2/` or goes outside it (`../`). Run every command from this folder.
- **Do not touch legacy.** Never edit, rename, move or delete a file outside `v2/`. The `scripts/check_legacy_untouched.py` check must pass before every commit.
- **No legacy imports.** v2 code never imports the legacy `plynx` package. Copying a legacy file into `v2/` and modifying it is allowed. Record each copy in `docs/LEGACY_MAP.md`.
- **Types first.** Every seam (SDK to engine, engine to server, server to UI) has a typed definition before it has an implementation. Mock the implementation, never the signature.
- **One task, one commit.** Small, atomic, tests included. Never mix refactors with features.
- **Stay inside non-goals.** `docs/ARCHITECTURE.md` lists what not to build. A request that needs a non-goal is a question for the owner.
- **Simplicity wins.** Standard library first. A new dependency needs a one-line reason in the commit message.
- **Do not guess.** If a fact, format or behavior is missing from these docs, ask the owner. Do not fill the gap.
- **Windows is supported.** Use `pathlib`, forward slashes in manifests, no shell-isms, no POSIX-only calls outside the `procgroup` module.

## Definition of done (every task)

- Acceptance criteria in `docs/PLAN.md` pass.
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` pass. For UI work, `npm run lint`, `npm run typecheck`, `npm test` pass in `ui/`.
- The task's checkbox in `docs/PLAN.md` is ticked in the same commit.
- Docs changed if behavior changed. One fact lives in one file.
