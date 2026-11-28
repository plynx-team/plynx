# Guide: Creating a Workflow

A PLynx workflow is a declarative YAML file describing a directed acyclic graph (DAG) of operations. Place workflows in `workflows/` (or any directory listed under `workflows:` in `plynx.yaml`).

## 1. Minimal Workflow

Create `workflows/greet.yaml`:

```yaml
version: 1
name: Greeting Workflow
nodes:
  generate:
    op: standard_io/demo:Echo
    inputs:
      text: "Hello from PLynx!"
  shout:
    op: standard_io/text:Concat
    inputs:
      a: $generate.text
      b: " Welcome aboard."
```

Key fields:

- **`version: 1`**: Workflow schema version (required).
- **`nodes`**: Mapping of node IDs (`^[a-z][a-z0-9_]*$`) to node definitions.
- **`op`**: Operation identifier in `<pack>/<module>:<Name>` format. Run `plynx ops` to list available ops.
- **`inputs`**: Mapping of port names to values:
  - **Wiring reference**: `$<node_id>.<output_name>` (or `{ from_node: <node_id>, output: <output_name> }`).
  - **Literal**: Any YAML scalar, list, or mapping. For `Path` or `Directory` ports, a string literal is a workspace-relative path.
  - **Escaped `$`**: Prefix a literal string starting with `$` using `$$` (e.g. `$$HOME` evaluates to `$HOME`).

## 2. Unbound Run Inputs (`--set` vs `--input`)

Any required input port omitted from `inputs:` (and without a default in the op definition) becomes an **unbound run input**:

```yaml
version: 1
name: Parametrized Workflow
nodes:
  read_doc:
    op: standard_io/demo:ReadText
    inputs: {}
  prefix_doc:
    op: standard_io/text:Concat
    inputs:
      b: $read_doc.text
```

Supply unbound inputs at runtime:

- **Scalars (`str`, `int`, `float`, `bool`, JSON)**: use `--set node.port=value`.
- **Files and directories (`Path`, `Directory`)**: use `--input node.port=path`.

```bash
plynx run \
  --input read_doc.path=notes.txt \
  --set prefix_doc.a="Summary: " \
  workflows/parametrized.yaml
```

If an unbound input is omitted in interactive mode, PLynx prompts for it in the terminal (or in the Web UI before/during the stage). In `--non-interactive` mode, missing inputs pause the run with exit code `2`.

## 3. Stages and Approval Gates

Group nodes into ordered stages using the top-level `stages:` mapping and assign each node via `stage: <stage_id>`. Edges must stay within the same stage or point to a later stage.

Set `require_approval: true` on a stage to pause the run after all nodes in that stage succeed, before any later stage begins:

```yaml
version: 1
name: Staged Workflow
stages:
  prepare:
    title: "1. Prepare"
    require_approval: true
  publish:
    title: "2. Publish"
nodes:
  step1:
    op: standard_io/demo:Echo
    stage: prepare
    inputs:
      text: prepped
  step2:
    op: standard_io/text:Concat
    stage: publish
    inputs:
      a: $step1.text
      b: " published"
```

Resolving a stage approval gate:

- **CLI (interactive)**: `plynx run` and `plynx resume` prompt in the terminal to approve or cancel when the stage finishes.
- **CLI (non-interactive / CI)**: `plynx run --non-interactive` exits with code `2` (`WAITING_FOR_USER`).
- **Web UI / REST**: Click **Approve & Continue** in the Stepper view, or call `POST /api/v1/runs/{run_id}/stages/{stage_id}/approve`.

## 4. Validating and Running

Always validate statically before running:

```bash
plynx validate workflows/greet.yaml
```

Static validation checks YAML schema, DAG cycles, op existence, port wiring, type/media compatibility, stage ordering, unguarded `SideEffect.WRITE` nodes (emitting a warning if no `require_approval: true` gate precedes an external write), and missing `uv.lock` files.

Run, inspect, and view in the UI:

```bash
# Run in-process
plynx run workflows/greet.yaml

# Run non-interactively (exits 2 if blocked on checkpoint or stage gate)
plynx run --non-interactive workflows/greet.yaml

# Bypass cache (e.g. after editing a shared helper module)
plynx run --no-cache workflows/greet.yaml

# List runs or inspect one run
plynx runs
plynx runs <run_id>

# Launch local Web UI (http://127.0.0.1:8080)
plynx ui
```
