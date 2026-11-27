---
name: plynx-create-workflow
description: Create, validate, run, and debug PLynx YAML workflows and custom Node Packs in this workspace.
---

# Create a PLynx Workflow

Follow this 5-step procedure whenever authoring or updating PLynx workflows or custom operations:

1. **Load current schemas and ops**: Run `plynx agent-guide` and `plynx ops --json`. Reuse existing `standard_io` or `custom_packs/` ops before writing new Python code.
2. **Design at Goldilocks granularity**: Aim for 3–8 coherent nodes across 2–4 stages. Split expensive or non-deterministic steps (`AgentOp`, network I/O, parsing) from fast deterministic formatting so `plynx-cache-1` hits on downstream tweaks.
3. **Author YAML and general-purpose ops**: Write `workflows/<name>.yaml` (`version: 1`, top-level `stages:` and `nodes:`). When new Python ops are needed in `custom_packs/<pack>/` (`Op`, `@op`, `AgentOp`, `StageValidatorOp`), keep them context-free and reusable across workflows (pass workflow-specific prompts, options, or thresholds as input ports; never hardcode demo strings or fake heuristics, and ensure `TITLE`/docstrings are 100% accurate for any input), then run `uv lock` in the pack directory.
4. **Validate statically**: Run `plynx validate workflows/<name>.yaml` and fix all errors before executing.
5. **Run and iterate**: Run `plynx run --non-interactive workflows/<name>.yaml` (use `--set`, `--input`, `--answer`, `--agent-provider`, `--agent-model` as needed). Debug failures in isolation with `plynx run-node <node_dir>`, then continue with `plynx resume <run_id>`.
