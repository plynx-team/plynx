# Guide: Create a Workflow

A PLynx workflow is a declarative YAML document specifying a directed acyclic graph (DAG) of operations. By convention, canonical reference examples live in `examples/workflows/` (tracked in git), while local user workflows live in `workflows/` (gitignored).

---

## 1. Minimal Workflow Example

Create `workflows/greet.yaml`:

```yaml
version: 1
name: "Greeting Workflow"

nodes:
  generate:
    op: "standard_io/demo:Echo"
    inputs:
      text: "Hello from PLynx!"

  shout:
    op: "standard_io/text:Concat"
    inputs:
      a: "$generate.text"
      b: " Welcome aboard."
```

### Key Elements:
* **`version: 1`**: PLynx workflow schema version.
* **`nodes`**: Map of unique node IDs (e.g. `generate`, `shout`).
* **`op`**: Op reference formatted as `<pack>/<module>:<OpName>`.
* **`inputs`**:
  * **Literal values**: Direct strings, integers, floats, booleans, lists, or dicts.
  * **Wiring references**: References formatted as `$<node_id>.<port_name>` connecting an upstream output to a downstream input.

---

## 2. Unbound Run Inputs

If an input port is not wired to an upstream node and has no default value, it becomes an **unbound run input**:

```yaml
version: 1
name: "Parametrized Workflow"

nodes:
  process:
    op: "standard_io/demo:Echo"
    inputs:
      # 'text' is not specified here -> prompted at run time
```

When running:
* Pass via CLI: `plynx run --input process.text="Custom Value" workflows/parametrized.yaml`
* Or via Web UI form at `http://127.0.0.1:8080`.

---

## 3. Stages and Approval Gates

Workflows can group nodes into sequential stages and enforce human approval before advancing:

```yaml
version: 1
name: "Staged Workflow"

stages:
  - id: prepare
    name: "Data Preparation"
    nodes:
      step1:
        op: "standard_io/demo:Echo"
        inputs:
          text: "prepped"

  - id: publish
    name: "Production Publish"
    require_approval: true
    nodes:
      step2:
        op: "standard_io/text:Concat"
        inputs:
          a: "$step1.text"
          b: " published"
```

When `require_approval: true` is set, all nodes in `prepare` must finish successfully, and PLynx will pause in `WAITING_FOR_USER` state until approved:
* CLI: `plynx run --approve <stage_id> ...` or during resume: `plynx resume --approve <stage_id> <run_id>`
* REST / UI: Click **Approve & Continue** in the Stepper view.

---

## 4. Validating Workflows

Always validate workflows statically before executing:

```bash
plynx validate workflows/greet.yaml
```

Validation verifies:
1. Syntax and schema correctness.
2. Cycle detection (must be a valid DAG).
3. Op existence in installed/discovered Node Packs.
4. Input and output port wiring and type compatibility.
5. Stage direction constraints (edges cannot wire backward across stages).
6. Missing `uv.lock` files in discovered packs.

---

## 5. Running Workflows

### Run in-process:
```bash
plynx run workflows/greet.yaml
```

### Run with non-interactive mode (for CI or automated pipelines):
```bash
plynx run --non-interactive workflows/greet.yaml
```

### Inspect runs:
```bash
plynx runs
plynx runs <run_id>
```

### Open UI:
```bash
plynx ui
```
Open `http://127.0.0.1:8080` in your browser to view the Stepper and Graph views, edit wiring visually, and inspect artifacts.
