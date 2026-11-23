# TODO (after v2.0.0)

Deferred by the owner. None of this is in v2.0.0. Do not start it without being asked. Dates are when it was deferred (Ivan Khomyakov, 2026-11-16) unless stated.

## Planned refactoring (decided, not yet scheduled)

- **AgentOp.** Delegating a node to an external agent CLI (Claude Code, Codex, Cursor, Antigravity) with `--resume <session_id>`, `ALLOW_EXTRA_INPUTS`, extra context in the prompt and in the cache key. Wait for owner feedback on checkpoints (the "foo or woo" test) first.
- **MCP server.** Lets an IDE agent validate, inspect, and trigger workflows and pass the active agent provider.
- **Agent skills.** Ready-made skills for Cursor, Claude Code, Antigravity that create workflows and debug nodes (the basic docs ship in 7.3).

## Candidates

- `Executor.launch()` implementation for an external engine.
- Remember checkpoint answers across fresh runs (a memory store).
- Hash the whole pack source tree into the cache key (closes the shared-helper blind spot).
- Dynamic fan-out (`map:`) and list nodes.
- `include:` and sub-workflows.
- Step debugger and breakpoints.
- Inline editing of output artifacts.
- API key vault and model selector.
- Pack marketplace: `plynx pack install <name>`.
- Tauri desktop app.
- WebMIDI / Strudel and RealSense / OAK-D verticals. Keep artifacts binary-friendly meanwhile.
- Multi-user storage abstraction.

