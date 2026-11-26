# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

### Added
- **Protocol enums**: `AgentTurnStatus`, `GraphEditPolicy`, `ValidatorMode`, and `AgentProvider` (`enum.StrEnum`) in `plynx_sdk.protocol`.
- **`self.warn()` / `plynx_sdk.warn()`**: non-fatal per-node warnings recorded in `outputs.json` and `result.json` (`warnings`).
- **Batch checkpoints**: `self.checkpoint_batch([...])` asks several questions (radio, checkbox, or freeform) in one pause. Supported by the REST answer endpoint (`answers`), SSE `node_checkpoint` (`questions`), CLI `--answers` / `--answer node.cp_n.question_id=value`, terminal prompts, and the Stepper / run inspector checkpoint card (**Submit Answers**).

### Changed
- SQLite `PRAGMA user_version` is now `2` (adds `checkpoints.questions_json`). Version 1 workspaces are upgraded in place on open.
- `POST /runs/{id}/checkpoints/{node_id}/{checkpoint_id}/answer` accepts `{ "answer": str }` or `{ "answers": {...} }`.

## [2.0.0] - 2026-11-22

Complete ground-up rewrite as a local-first, code-first workflow engine. Legacy PLynx v1 (`v1.12.1`) is preserved on the `legacy/v1` branch.

### Added
- **Zero-dependency SDK (`plynx-sdk`)**: Define operations as plain Python `Op` subclasses or `@op`-decorated functions with typed ports (`Path`, `Directory`, `Literal`, `Range`, `Media`), `ALLOW_EXTRA_INPUTS`, and interactive `checkpoint()` calls.
- **YAML Workflows & Static Validation**: Human-readable, Git-friendly YAML DAGs with named stages, deferred stage inputs, stage approval gates (`require_approval: true`), and static AST-based validation (`plynx validate`).
- **Local-First Engine & Content-Addressed Storage**: `graphlib` + `asyncio` scheduler backed by SQLite (WAL), append-only `events.jsonl`, and content-addressed blob storage in `.plynx/` with automatic early cutoff and `plynx clean` GC.
- **Isolated `uv` Environments**: Custom Node Packs execute in per-pack isolated `uv` virtual environments with cross-process lockfiles; built-in `standard_io` ops run directly with stdlib only.
- **Built-in `standard_io` Pack**: 13 cross-platform, stdlib-only operations covering text, data, files, and interactive prompts.
- **CLI**: `plynx init`, `validate`, `run`, `resume`, `run-node` (isolated scratch debugging), `runs`, `ops`, `clean`, `ui`, and `agent-guide`.
- **Web UI**: React + TypeScript + Vite application bundled in the `plynx` wheel featuring Stepper view, editable React Flow DAG canvas, live SSE logs, unified run snapshot inspector, and artifact previewers.

### Removed
- MongoDB, Flask, Docker/Kubernetes runtime stack, user accounts/OAuth, cloud storage backends, and distributed worker servers.

### Legacy v1 releases

## [1.9.8] - 2022-12-24

- Parse file extensions in upload dialog to determine the right type.
- Fix redirection logic.

## [1.9.7] - 2022-12-23

- Add ability to upload a file in Workflow editor.

## [1.9.4] - 2022-12-22

- Using Oauth2 to sign-up / log-in.
- Isolate workers from using database directly.

## [1.9.3] - 2022-12-11

- Fix a bug: do not restart a failed Operation without explicit action.
- Indicate running Operations using styles.

## [1.9.2] - 2022-12-10

- Some of the Operations have auto-run disabled.
- Auto-run can be specified on Operations level.
- Improved sync with a running job: it is not restarted with minor changes.

## [1.9.1] - 2022-11-26

- UI fixes.
- MongoDB: allow using disk in aggregation.

## [1.9.0] - 2022-11-25

- Updated react version to 17.
- Using reactFlow as the workflow engine.
- Added interactive Operation lookup.

## [1.8.1] - 2022-10-19

- Using single threaded python DAG by default.
- UI bug fixes.

## [1.8.0] - 2022-10-17

- Auto-sync and auto-run flags for interactive DAGs.
- Interactive DAG editor: subnode status is updated in the edit mode.
- UI: using only kind-title in the nodes.

## [1.7.9] - 2022-04-19

- Local DAG executor now supports Operations defined in the DB.

## [1.7.8] - 2022-04-18

- Refactoring: DB structure relies on python type annotation.
- Using python linters.
- Updated documentation and cleaned up the code.

## [1.7.5] - 2022-02-13

- New python API to create operations from the code.
- Improved Static List Hub with the support of Python API.
- Support of folders in the hubs.
- New local DAG executor.
