---
name: plynx-create-workflow
description: Create, validate, run, and debug PLynx YAML workflows and custom Node Packs in this workspace.
---

# Create a PLynx Workflow

Follow this 5-step procedure whenever authoring or updating PLynx workflows or custom operations:

1. **Load current schemas and ops**: Run `plynx agent-guide` and `plynx ops --json`. Reuse existing `standard_io` or `custom_packs/` ops before writing new Python code.
2. **Design at Goldilocks granularity**: Aim for 3–8 coherent nodes across 2–4 stages. Split expensive or non-deterministic steps (`AgentOp`, network I/O, parsing) from fast deterministic formatting so `plynx-cache-1` hits on downstream tweaks. Place irreversible external side-effecting ops (`CACHEABLE = False`: email, messaging, `git push`, DB/API writes) in a dedicated final stage with `require_approval: true` on the preceding stage (or a `dry_run: bool` input).
3. **Author YAML and general-purpose ops**: Write `workflows/<name>.yaml` (`version: 1`, top-level `stages:` and `nodes:`). When new Python ops are needed in `custom_packs/<pack>/` (`Op`, `@op`, `AgentOp`, `StageValidatorOp`), keep them context-free and reusable across workflows (pass workflow-specific prompts, options, or thresholds as input ports; never hardcode demo strings or fake heuristics, and ensure `TITLE`/docstrings are 100% accurate for any input), then run `uv lock` in the pack directory.
4. **Validate and check edge cases without side effects**: Run `plynx validate workflows/<name>.yaml` and fix all errors. When refactoring ops or debugging, inspect historical `.plynx/runs/<run_id>/nodes/<node_id>/{inputs.json,result.json}` read-only for corner cases and test external/refactored ops with `pytest` mocks.
5. **Run and iterate safely**: Pure local deterministic ops may be run freely with `plynx run --non-interactive workflows/<name>.yaml` (use `--set`, `--input`, `--answer`, `--agent-provider`, `--agent-model` as needed), `plynx run-node <node_dir>`, and `plynx resume <run_id>`. **Always ask the user for explicit confirmation** before executing or replaying any node/stage that mutates external state or incurs non-trivial API/LLM cost.
