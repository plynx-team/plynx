# Pack Rules (Node Pack and Op Authoring)

These rules are agreements, not checks. The engine cannot enforce all of them. Break one and results can be stale, wrong, or expensive. This file ships with v2 as the primary reference for pack authors and AI coding agents.

## Quick Guides

* **[Creating a Workflow](guides/create_workflow.md)**: YAML DAG syntax, stage gates, unbound inputs, validation.
* **[Authoring a Node Pack](guides/author_pack.md)**: Package layout, `pyproject.toml`, `@op` / `Op` class, port types.
* **[Debugging with `run-node`](guides/debug_failed_node.md)**: Reproducing node failures in scratch copies and resuming runs.

---

## Pack Structure and Discovery

1. **Standard location**: Custom packs live in `custom_packs/<pack_name>` relative to the workspace root.
2. **Workspace configuration (`plynx.yaml`)**: Additional pack directories can be configured via `pack_dirs`:
   ```yaml
   pack_dirs:
     - "external_packs"
   env_passthrough:
     - "OPENAI_API_KEY"
     - "DATABASE_URL"
   ```
3. **Lockfile requirement**: Every pack must include a `uv.lock` file (`uv lock` inside the pack folder) for deterministic execution and caching. Missing lockfiles produce validation warnings.
4. **Dependencies**: A pack depends on `plynx-sdk` and its own libraries. It never depends on `plynx`.

---

## Declaring Ops

5. **Metadata is literal**: `TITLE`, `CATEGORY`, `CACHEABLE`, and `@op(...)` arguments are plain literals. Ports are annotated with the types in [PROTOCOL.md](PROTOCOL.md) section 3. Anything computed makes the op invalid.
6. **Outputs contract**: Declare outputs with a `TypedDict` (`class Outputs` in a class op, a module-level `TypedDict` for `@op`). Return a dict with exactly those keys.
7. **Descriptions**: The first docstring line is the description shown in the UI. Write clear, concise docstrings.

---

## Inputs, Outputs, and File Operations

8. **Never modify an input**: Input files and directories are read-only and shared through a content-addressed store (CAS). Copy to `workdir/` before editing.
9. **Confine writes to workdir**: Write outputs only inside the current working directory (`workdir/`). Return relative paths. No absolute paths, no `..`.
10. **Size limits**: Return JSON values (`dict`, `list`, scalars) only when small (under 1 MiB). Larger data goes to a file.
11. **Cross-platform compatibility**: Use `pathlib.Path`. Do not invoke OS-specific shell commands (`rm`, `cp`, `grep`). Windows is fully supported.

---

## Checkpoints (Human-in-the-Loop)

12. **Replay safety**: `checkpoint()` replays the whole node from the top after the user answers. Everything before a `checkpoint()` call runs twice. Call `checkpoint()` first, or make all work before it cheap and free of side effects. Never send a paid API request, write to an external system, or send a message before a checkpoint in the same node.
13. **Deterministic order**: Checkpoint calls must happen in the same order on every replay. Do not make their number depend on randomness, time, or network results.
14. **Exception handling**: Do not catch `BaseException` or use a bare `except:` around code that may call `checkpoint()`. Do not call `sys.exit(10)` manually.
15. **Cross-run scope**: Checkpoint answers are not remembered across fresh runs in v2.0.0. If a node must not re-ask, persist the answer in a memory file in the workspace and read it first.

---

## Caching and Performance

16. **Cache key scope**: The cache key covers: the op's own source file, the pack's `uv.lock`, input hashes, scalar parameters, and checkpoint answers. It does **not** cover other files in the pack (shared helpers), environment variables, time, or the network.
17. **Shared helpers**: After editing a shared helper, run `plynx run --no-cache` once. Prefer to keep op logic in the op's own file.
18. **Non-deterministic operations**: Set `CACHEABLE = False` (or `cacheable=False`) when the result depends on time, randomness without a fixed seed, or external state. An LLM call is cacheable only when you accept replaying the old answer.
19. **Run immutability**: Inside one run, a finished node's outputs never change, even for non-cacheable ops.

---

## Secrets, Logging, and Debugging

20. **Secrets**: Read secrets from environment variables (`.env` or the host). Never write them to outputs, files, or logs.
21. **Logging**: Log with `print` or `logging` to stdout and stderr. They are captured per node. Do not buffer on purpose.
22. **Tracebacks**: Let exceptions propagate. The engine captures and displays the full traceback. Do not exit with codes 10 or 2 on your own.
23. **Debugging with `run-node`**: A failed node keeps its directory. Re-run only that node with `plynx run-node <node_dir>`. Fix the source, verify with `run-node`, then resume the run with `plynx resume <run_id>`. Finished upstream nodes are never re-run.
24. **Validation first**: Always run `plynx validate <workflow>` before `plynx run`. It checks wiring, missing ports, backward stages, and types statically.
