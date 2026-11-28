# Guide: Debugging a Failed Node with `plynx run-node`

When a node fails, PLynx records the run state in `.plynx/plynx.db`, saves stdout/stderr logs, and keeps the node's input manifest and directory on disk. You can reproduce and fix the failure in isolation using `plynx run-node`, then continue the run with `plynx resume`.

## 1. Inspect the Failure

Check the run status and read the failing node's logs:

```bash
plynx runs
plynx runs <run_id>

# Inspect captured logs
cat .plynx/runs/<run_id>/logs/<node_id>.stdout.log
cat .plynx/runs/<run_id>/logs/<node_id>.stderr.log
```

## 2. Reproduce in Scratch with `plynx run-node`

Each attempted node has a directory at `.plynx/runs/<run_id>/nodes/<node_id>/` containing `inputs.json`, materialized read-only inputs under `inputs/`, and `workdir/`:

```bash
plynx run-node .plynx/runs/<run_id>/nodes/<node_id>
```

What `plynx run-node` does:

1. Copies `<node_dir>` into a temporary scratch directory.
2. Reads the op identifier from `workflow.snapshot.yaml` (or pass `--op <pack>/<module>:<Name>` explicitly if debugging a standalone directory).
3. Executes the op in its pack environment with the exact recorded `inputs.json`.
4. Streams the child's stdout and stderr directly to your terminal and exits with the child's exit code (`0` on success, `1` on exception, `10` on checkpoint interrupt).
5. Leaves `.plynx/plynx.db`, `events.jsonl`, logs, and the original `<node_dir>` completely untouched.

> **External Write Guardrail (`SIDE_EFFECTS = SideEffect.WRITE`):** If the target operation declares `side_effects="write"` (e.g. `standard_io/http:HttpPostJson` or a custom webhook/email op), `plynx run-node` exits `1` before spawning a subprocess so debugging never triggers accidental external actions. Pass `--allow-side-effects` only when you intentionally want to execute the external write.

## 3. Fix and Verify

1. Edit the op's Python source file to fix the bug.
2. Re-run `plynx run-node .plynx/runs/<run_id>/nodes/<node_id>`.
3. Verify the command exits `0` (check `$?`) with the expected stdout/stderr output.

## 4. Resume the Workflow

Once the fix is verified, resume the original run:

```bash
plynx resume <run_id>
```

PLynx reuses all already-completed upstream node outputs from the run and executes only the failed node and its downstream dependents.
