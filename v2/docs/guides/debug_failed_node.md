# Guide: Debug a Failed Node with `plynx run-node`

When a workflow node fails, PLynx records the run state in SQLite, logs stdout/stderr, and preserves the node attempt directory. You can reproduce, inspect, and fix the failure locally using `plynx run-node`.

---

## 1. Inspecting the Failure

When a run fails:

```bash
$ plynx run workflows/pipeline.yaml
ingest SUCCESS
transform RUNNING
transform FAILED
publish BLOCKED
Run failed with exit code 1.
```

Check the run state and node status:

```bash
plynx runs
plynx runs <run_id>
```

Inspect stdout and stderr logs for the failed node:

```bash
# Log files are saved under .plynx/runs/<run_id>/logs/
cat .plynx/runs/<run_id>/logs/transform.stderr.log
```

---

## 2. Using `plynx run-node`

Each node has its own directory under `.plynx/runs/<run_id>/nodes/<node_id>/`:

```text
.plynx/runs/20261118_120000_a1b2c3/
└── nodes/
    └── transform/
        ├── inputs.json
        ├── workdir/
        └── ...
```

`plynx run-node` re-runs that node in an isolated scratch copy without touching the original run directory or SQLite database:

```bash
plynx run-node .plynx/runs/20261118_120000_a1b2c3/nodes/transform
```

PLynx will:
1. Copy the attempt directory to a temporary scratch directory.
2. Spawn the op in its pack environment with the exact inputs recorded in `inputs.json`.
3. Print stdout and stderr (including the full Python traceback) directly to your terminal.

---

## 3. Fixing the Bug and Verifying

1. Open the source file of the failing operation in your editor.
2. Fix the bug (e.g. correct a typo, add a missing exception check, or fix data parsing).
3. Re-run `plynx run-node`:

```bash
plynx run-node .plynx/runs/20261118_120000_a1b2c3/nodes/transform
```

Once `plynx run-node` succeeds, it will print:
```text
OK: node attempt succeeded
outputs:
  result: ...
```

---

## 4. Resuming the Workflow

Now resume the original workflow run using `plynx resume`:

```bash
plynx resume <run_id>
```

PLynx will:
* Detect that upstream nodes (e.g. `ingest`) succeeded and reuse their outputs from SQLite/CAS.
* Re-run only `transform` and downstream nodes (e.g. `publish`).
* Complete the workflow to `SUCCESS`.
