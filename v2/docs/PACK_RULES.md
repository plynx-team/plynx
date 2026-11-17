# Pack rules (for anyone writing Node Packs, human or agent)

These rules are agreements, not checks. The engine cannot enforce them. Break one and results can be stale, wrong, or expensive. This file ships with v2 as agent rules for pack authors.

## Declaring ops

1. Metadata is literal. `TITLE`, `CATEGORY`, `CACHEABLE`, and `@op(...)` arguments are plain literals. Ports are annotated with the types in PROTOCOL.md section 3. Anything computed makes the op invalid.
2. Declare outputs with a `TypedDict` (`class Outputs` in a class op, a module-level `TypedDict` for `@op`). Return a dict with exactly those keys.
3. The first docstring line is the description shown in the UI. Write it.
4. A pack depends on `plynx-sdk` and its own libraries. It never depends on `plynx`.

## Inputs, outputs, files

5. **Never modify an input.** Input files and directories are read-only and shared through a content-addressed store. Copy to `workdir/` before editing.
6. Write outputs only inside the current directory (`workdir/`). Return relative paths. No absolute paths, no `..`.
7. Return JSON values (`dict`, `list`, scalars) only when small (under 1 MiB). Larger data goes to a file.
8. Use `pathlib`. No shell commands that exist only on one OS. Windows is supported.

## Checkpoints

9. `checkpoint()` replays the whole node from the top after the user answers. Everything before a `checkpoint()` call runs twice. Call `checkpoint()` first, or make all work before it cheap and free of side effects. Never send a paid API request, write to an external system, or send a message before a checkpoint in the same node.
10. Checkpoint calls must happen in the same order on every replay. Do not make their number depend on randomness, time, or network results.
11. Do not catch `BaseException` or use a bare `except:` around code that may call `checkpoint()`. Do not call `sys.exit(10)`.
12. Checkpoint answers are not remembered across fresh runs in v2.0.0. If a node must not re-ask, keep the answer in a file you own (a memory file in the workspace) and read it first.

## Caching

13. The cache key covers: the op's own source file, the pack's `uv.lock`, input hashes, scalar parameters, and checkpoint answers. It does **not** cover other files in the pack (shared helpers), environment variables, time, or the network.
14. After editing a shared helper, run `plynx run --no-cache` once. Prefer to keep op logic in the op's own file.
15. Set `CACHEABLE = False` (or `cacheable=False`) when the result depends on time, randomness without a fixed seed, or external state. An LLM call is cacheable only when you accept replaying the old answer.
16. Inside one run, a finished node's outputs never change, even for non-cacheable ops.

## Secrets and logs

17. Read secrets from environment variables (`.env` or the host). Never write them to outputs, files, or logs.
18. Log with `print` or `logging` to stdout and stderr. They are captured per node. Do not buffer on purpose.
19. Let exceptions propagate. The engine shows the traceback. Do not exit with codes 10 or 2 on your own.

## Debugging

20. A failed node keeps its directory. Re-run only that node with `plynx run-node <node_dir>`. Fix the source, then `plynx resume <run_id>`. Finished upstream nodes are not re-run.
21. Run `plynx validate <workflow>` before `plynx run`. It checks wiring and types without running code.
