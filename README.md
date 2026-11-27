# PLynx

**PLynx** is a local-first workflow engine for building and running reproducible DAGs. Workflows are plain YAML; operations are plain Python (`Op` or `@op`) running in isolated `uv` environments. Outputs are content-addressed and cached locally in `.plynx/`.

## Highlights

- **Local-First**: Runs against local files, SQLite (WAL), and a content-addressed blob store in `.plynx/`. No database server or daemon required.
- **Isolated Environments**: Custom Node Packs run in isolated `uv` virtual environments with pinned `uv.lock` dependencies. Built-in `standard_io` ops run with stdlib only.
- **Content-Addressed Caching**: Cache keys hash the op entrypoint, op source file bytes, pack `uv.lock`, input file/directory hashes, scalar parameters, and checkpoint answers, with automatic early cutoff.
- **Human-in-the-Loop**: `checkpoint()` prompts and stage approval gates (`require_approval: true`) pause runs for terminal or web UI input and resume cleanly.
- **Web UI**: Stepper view and editable React Flow DAG canvas with live SSE logs, run inspection, and artifact previews.
- **Scratch Debugging**: Reproduce and fix any failed node in an isolated scratch copy with `plynx run-node <node_dir>`, then resume with `plynx resume <run_id>`.

## Installation

Prerequisites: Python **3.11+** and [uv](https://docs.astral.sh/uv/) (required for isolated third-party Node Packs).

```bash
# Run directly without installing
uvx plynx --help

# Install globally with uv (recommended)
uv tool install plynx

# Or install with pip
pip install plynx
```

## Quickstart

Initialize a workspace in any directory:

```bash
mkdir my-project && cd my-project
plynx init
```

Create a starter workflow `workflows/hello.yaml`:

```yaml
version: 1
name: hello
stages:
  ask:
    title: "1. Ask"
  greet:
    title: "2. Greet"
nodes:
  pick:
    op: standard_io/interactive:AskChoice
    stage: ask
    inputs:
      question: "Pick a greeting:"
      options_csv: "Hello, Welcome"
  echo:
    op: standard_io/demo:Echo
    stage: greet
    inputs:
      text: $pick.choice
```

Validate and run it:

```bash
# 1. Static validation (no code executed)
plynx validate workflows/hello.yaml

# 2. Run interactively (prompts in terminal) or pass answers non-interactively
plynx run --answer pick.cp_0=Hello workflows/hello.yaml

# 3. Inspect runs and available operations
plynx runs
plynx ops

# 4. Launch the local web UI (http://127.0.0.1:8080)
plynx ui

# 5. Prune old unpinned runs and unreferenced blobs
plynx clean --days 7
```

## Built-in Operations (`standard_io`)

The `plynx` wheel ships with **15 stdlib-only operations** in `standard_io`:

- **`Core / Text & Data`**: `Echo`, `Concat`, `TemplateFormat`, `MathOp`, `JsonExtract`, `JsonMerge`, `CsvSummary`
- **`Core / Files`**: `ReadText`, `WriteText`, `ListDirectory`, `BundleDirectory`, `MarkdownReport`
- **`Core / Interactive`**: `AskChoice`
- **`Core / Agents`**: `AgentPrompt`, `StageSupervisor`

Run `plynx ops` (or `plynx ops --json`) in any workspace to list all built-in and custom operations with their full port schemas.

## Examples (Repository Only)

This repository includes optional demo packs (`examples/custom_packs/`: `doc_review`, `media_studio`, `pedalboard_studio`, `podcast_studio`) and showcase workflows in `examples/workflows/`:

| Workflow | Focus |
| :--- | :--- |
| [`foo_or_woo.yaml`](examples/workflows/foo_or_woo.yaml) | Minimal 2-node checkpoint workflow using `standard_io`. |
| [`interactive_wizard_staged.yaml`](examples/workflows/interactive_wizard_staged.yaml) | Multi-stage interactive survey with `require_approval: true` and Markdown report. |
| [`adaptive_doc_review.yaml`](examples/workflows/adaptive_doc_review.yaml) | End-to-end agentic workflow with `self.warn()`, `StageSupervisor` graph repair, and batch multi-question `checkpoint_batch()`. |
| [`data_bundle_pipeline.yaml`](examples/workflows/data_bundle_pipeline.yaml) | Data pipeline covering CSV, JSON, math, directory bundling, and Markdown output. |
| [`generative_art_studio.yaml`](examples/workflows/generative_art_studio.yaml) | Procedural image generation (Mandelbrot, geometric patterns, filters, metadata). |
| [`midi_groove_studio.yaml`](examples/workflows/midi_groove_studio.yaml) | Multi-track MIDI sequencing, synthesis, mixing, and mastering. |
| [`bach_prelude_c_major.yaml`](examples/workflows/bach_prelude_c_major.yaml) | Acoustic piano synthesis and Pedalboard spatial effects. |
| [`podcast_producer_macos.yaml`](examples/workflows/podcast_producer_macos.yaml) | macOS speech synthesis (`say`), sidechain ducking, and show notes. *(macOS only)* |

## AI Coding Agents

`plynx init` materializes a thin-shim skill at `.agents/skills/plynx-create-workflow/SKILL.md`, and PLynx ships a self-contained reference for AI coding agents. From any workspace, print it with:

```bash
plynx agent-guide
```

## Documentation

- [Guide: Creating a Workflow](docs/guides/create_workflow.md)
- [Guide: Authoring a Node Pack](docs/guides/author_pack.md)
- [Guide: Setting Up Agentic Workflows](docs/guides/agentic_workflows.md)
- [Guide: Debugging a Failed Node](docs/guides/debug_failed_node.md)
- [User Agent Reference](docs/AGENT_GUIDE.md)
- [Architecture & Invariants](docs/ARCHITECTURE.md)
- [Protocol & Schema Specifications](docs/PROTOCOL.md)

## Development Setup

```bash
git clone https://github.com/plynx-team/plynx.git
cd plynx
uv sync
cd ui && npm ci && npm run build && cd ..

# Launch the local web UI from the workspace (or: uv run python -m plynx.cli ui)
uv run plynx ui

# Run checks, tests, and wheel build
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
uv run python scripts/build.py
```

## License

Apache-2.0
