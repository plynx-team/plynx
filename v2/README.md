# PLynx v2

**PLynx v2** is a domain-agnostic, local-first platform for building and running reproducible workflows (DAGs).

PLynx combines the simplicity of declarative YAML workflows, the power of isolated Python Node Packs, content-addressed caching, human-in-the-loop checkpoints, and an interactive modern web UI.

---

## Highlights

* **Local-First & Fast**: Zero daemon or database setup required. Runs purely against local files, SQLite, and a content-addressed blob store in `.plynx/`.
* **Isolated Node Execution**: Operations run in isolated virtual environments managed by `uv`, ensuring reproducible dependencies per pack without conflict.
* **Deterministic Caching**: Fine-grained content-addressed caching keyed by op AST source code, `uv.lock`, inputs, parameters, and checkpoint answers.
* **Human-in-the-Loop**: Interactive `checkpoint()` prompts let nodes pause execution for user decisions, questions, or approval gates, then resume seamlessly.
* **Modern Web UI**: Switch between a sequential Stepper view and an interactive React Flow DAG editor with live SSE logs, artifact previews, and drag-and-drop wiring.
* **Isolated Scratch Debugging**: Re-run and reproduce failing node attempts in a temporary scratch directory with `plynx run-node <node_dir>`.

---

## Installation

### Run directly with `uvx` (No installation needed)

```bash
uvx plynx --help
uvx plynx ui
```

### Install using `uv` or `pip`

```bash
# Using uv (recommended)
uv tool install plynx

# Or with pip into a virtual environment
pip install plynx
```

### Prerequisites

* Python **3.11+**
* [uv](https://docs.astral.sh/uv/) (recommended package installer and environment runner)

---

## Quickstart

### 1. Validate a Workflow

Statically validate workflow DAG structure, wiring ports, and pack requirements:

```bash
plynx validate examples/workflows/foo_or_woo.yaml
```

### 2. Run a Workflow

Execute a workflow directly in your terminal:

```bash
plynx run --answer pick.cp_0=foo examples/workflows/foo_or_woo.yaml
```

For interactive checkpoint prompts, omit `--answer` to answer directly from your terminal:

```bash
plynx run examples/workflows/foo_or_woo.yaml
```

### 3. Inspect Runs

List recent workflow runs:

```bash
plynx runs
```

Inspect the detailed state, parameters, and node statuses of a specific run:

```bash
plynx runs <run_id>
```

### 4. Start the Web UI

Launch the local PLynx web server (bound to `127.0.0.1:8080`) and open your browser:

```bash
plynx ui
```

### 5. Clean Old Runs (Garbage Collection)

Reclaim disk space by pruning old unpinned runs, orphaned cache entries, and unreferenced blobs:

```bash
plynx clean --days 7
```

---

## Development Setup

To build and run PLynx from source:

```bash
# 1. Clone repository and navigate to v2
git clone https://github.com/plynx-team/plynx.git
cd plynx/v2

# 2. Sync workspace dependencies
uv sync

# 3. Build UI assets
cd ui
npm ci
npm run build
cd ..

# 4. Run tests and linting
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest

# 5. Build wheels
uv run python scripts/build.py
```

---

## Documentation

* [Architecture & Invariants](docs/ARCHITECTURE.md)
* [Protocol & Schema Specifications](docs/PROTOCOL.md)
* [Pack Rules & Best Practices](docs/PACK_RULES.md)
* [Guide: Creating a Workflow](docs/guides/create_workflow.md)
* [Guide: Authoring a Node Pack](docs/guides/author_pack.md)
* [Guide: Debugging with `run-node`](docs/guides/debug_failed_node.md)

---

## License

Apache-2.0
