---
name: plynx-create-workflow
description: Create, validate, run, and debug PLynx YAML workflows and custom Node Packs in this workspace.
---

# Create a PLynx Workflow

Follow this 5-step procedure whenever authoring or updating PLynx workflows or custom operations:

1. **Load current schemas and ops**: Run `plynx agent-guide` and `plynx ops --json`. Reuse existing `standard_io` or `custom_packs/` ops before writing new Python code.
2. **Design at Goldilocks granularity**: Aim for 3–8 coherent nodes across 2–4 stages. Split expensive or non-deterministic steps (`AgentOp`, network I/O, parsing) from fast deterministic formatting so `plynx-cache-1` hits on downstream tweaks.
3. **Author YAML (and custom ops if needed)**: Write `workflows/<name>.yaml` (`version: 1`, top-level `stages:` and `nodes:`). For new ops, create a stdlib-light pack in `custom_packs/<pack>/` using `Op`, `@op`, `AgentOp`, or `StageValidatorOp`, and run `uv lock` inside the pack directory.
4. **Validate statically**: Run `plynx validate workflows/<name>.yaml` and fix all errors before executing.
5. **Run and iterate**: Run `plynx run --non-interactive workflows/<name>.yaml` (use `--set`, `--input`, `--answer`, `--agent-provider`, `--agent-model` as needed). Debug failures in isolation with `plynx run-node <node_dir>`, then continue with `plynx resume <run_id>`.
