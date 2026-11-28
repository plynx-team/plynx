---
name: plynx-create-workflow
description: Create, validate, run, and debug PLynx YAML workflows and custom Node Packs in this workspace.
---

# Create a PLynx Workflow

Design for the operator who will run this without the author. Follow the handoff and repair guidance in `plynx agent-guide`: define what evidence makes an output acceptable, and exercise both a recoverable input change and a case that requires human clarification.

Follow this 5-step procedure whenever authoring or updating PLynx workflows or custom operations:

1. **Load current schemas and ops**: Run `plynx agent-guide` and `plynx ops --json`. Reuse existing `standard_io` or `custom_packs/` ops before writing new Python code.
2. **Design at Goldilocks granularity**: Aim for 3–8 coherent nodes across 2–4 stages. Split expensive or non-deterministic steps (`AgentOp`, network I/O, parsing) from fast deterministic formatting so `plynx-cache-1` hits on downstream tweaks. Separate read/preview ops (`SIDE_EFFECTS = SideEffect.NONE` or `SideEffect.READ`) from irreversible external write ops (`SIDE_EFFECTS = SideEffect.WRITE`, `CACHEABLE = False`: email, messaging, `HttpPostJson`, `git push`, DB/API writes), and place `WRITE` ops in a dedicated final stage after a `require_approval: true` stage gate.
3. **Author detached ops first, then YAML**: When new Python ops are needed in `custom_packs/<pack>/` (`Op`, `@op`, `AgentOp`, `StageValidatorOp`), design and unit-test them on **≥2 distinct synthetic input shapes** *before* wiring `workflows/<name>.yaml` (`version: 1`, top-level `stages:` and `nodes:`). Declare accurate `SIDE_EFFECTS` (`SideEffect.NONE | READ | WRITE`), parameterize variable data schemas (columns, keys, delimiters, prompts) via simple typed ports without inventing YAML expression DSLs or over-abstracting fixed vendor API schemas, ensure `TITLE`/docstrings are 100% accurate for arbitrary inputs, and run `uv lock` in the pack directory.
4. **Validate and check edge cases without side effects**: Run `plynx validate workflows/<name>.yaml` and resolve errors and unguarded-`WRITE` warnings. When refactoring ops or debugging, inspect historical `.plynx/runs/<run_id>/nodes/<node_id>/{inputs.json,result.json}` read-only for corner cases and test external/refactored ops with `pytest` mocks.
5. **Run and iterate safely**: Inspect `side_effects` in `plynx ops --json`. `"none"` ops may be run and debugged freely (`plynx run`, `plynx run-node <node_dir>`, `plynx resume <run_id>`); `"read"` ops are safe from external mutations (watch API/LLM cost). `"write"` ops are blocked by `plynx run-node` unless `--allow-side-effects` is passed—**never** pass `--allow-side-effects` or approve a pre-write stage gate without explicit user confirmation.
