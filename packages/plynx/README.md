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

```bash
mkdir my-project && cd my-project
plynx init
```

Create `workflows/hello.yaml`:

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

Validate, run, and inspect:

```bash
plynx validate workflows/hello.yaml
plynx run --answer pick.cp_0=Hello workflows/hello.yaml
plynx runs
plynx ops
plynx ui
```

## Documentation

- [GitHub Repository](https://github.com/plynx-team/plynx)
- [Guide: Creating a Workflow](https://github.com/plynx-team/plynx/blob/main/docs/guides/create_workflow.md)
- [Guide: Authoring a Node Pack](https://github.com/plynx-team/plynx/blob/main/docs/guides/author_pack.md)
- [Guide: Debugging a Failed Node](https://github.com/plynx-team/plynx/blob/main/docs/guides/debug_failed_node.md)
- [User Agent Reference](https://github.com/plynx-team/plynx/blob/main/docs/AGENT_GUIDE.md)
- [Changelog](https://github.com/plynx-team/plynx/blob/main/CHANGELOG.md)

## License

Apache-2.0
