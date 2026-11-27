---
name: plynx-create-workflow
description: Create, validate, run, and debug PLynx YAML workflows and custom Node Packs in this workspace.
---

# Create a PLynx Workflow

Follow this 5-step procedure whenever authoring or updating PLynx workflows or custom operations:

1. **Load current schemas and ops**: Run `plynx agent-guide` and `plynx ops --json`. Reuse existing `standard_io` or `custom_packs/` ops before writing new Python code.
2. **Design at Goldilocks granularity**: Aim for 3–8 coherent nodes across 2–4 stages. Split expensive or non-deterministic steps (`AgentOp`, network I/O, parsing) from fast deterministic formatting so `plynx-cache-1` hits on downstream tweaks. Separate read/preview ops (`SIDE_EFFECTS = SideEffect.NONE` or `SideEffect.READ`) from irreversible external write ops (`SIDE_EFFECTS = SideEffect.WRITE`, `CACHEABLE = False`: email, messaging, `HttpPostJson`, `git push`, DB/API writes), and place `WRITE` ops in a dedicated final stage after a `require_approval: true` stage gate.
3. **Author YAML and general-purpose ops**: Write `workflows/<name>.yaml` (`version: 1`, top-level `stages:` and `nodes:`). When new Python ops are needed in `custom_packs/<pack>/` (`Op`, `@op`, `AgentOp`, `StageValidatorOp`), declare accurate `SIDE_EFFECTS` (`SideEffect.NONE | READ | WRITE`) so future agents and humans know whether the op is safe to debug, keep ops context-free and reusable across workflows (never hardcode demo strings or fake heuristics, and ensure `TITLE`/docstrings are 100% accurate for any input), then run `uv lock` in the pack directory.
4. **Validate and check edge cases without side effects**: Run `plynx validate workflows/<name>.yaml` and resolve errors and unguarded-`WRITE` warnings. When refactoring ops or debugging, inspect historical `.plynx/runs/<run_id>/nodes/<node_id>/{inputs.json,result.json}` read-only for corner cases and test external/refactored ops with `pytest` mocks.
5. **Run and iterate safely**: Inspect `side_effects` in `plynx ops --json`. `"none"` ops may be run and debugged freely (`plynx run`, `plynx run-node <node_dir>`, `plynx resume <run_id>`); `"read"` ops are safe from external mutations (watch API/LLM cost). `"write"` ops are blocked by `plynx run-node` unless `--allow-side-effects` is passed—**never** pass `--allow-side-effects` or approve a pre-write stage gate without explicit user confirmation.
