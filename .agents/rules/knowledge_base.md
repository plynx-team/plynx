# Knowledge Base (`.kb/`) Rules

A concise architectural and operational knowledge base is maintained in [`.kb/`](../../.kb/INDEX.md) (gitignored).

## Mandatory Agent Workflow

1. **Consult `.kb/` First**:
   - Before running broad codebase searches (`grep`, file scans) or investigating how backend/frontend components interact, read [`.kb/INDEX.md`](../../.kb/INDEX.md) and the relevant topic file:
     - [`.kb/architecture.md`](../../.kb/architecture.md): Data models (`DBObject`, `Node`, `_cached_node`), collections, and plugins (`BaseExecutor`, `BaseResource`, `BaseHub`).
     - [`.kb/execution_and_sync.md`](../../.kb/execution_and_sync.md): Save/auto-run flow, `basic-dag-workflow` vs. `python-workflow` execution, worker queues, caching, and `auto_sync`.
     - [`.kb/frontend.md`](../../.kb/frontend.md): React 18 / ReactFlow UI components (`Editor`, `Graph`, `OperationNode`, `PropertiesBar`, `ListPage`) and state flow.
     - [`.kb/dev_and_ops.md`](../../.kb/dev_and_ops.md): `make dev` Docker services, MongoDB container inspection, and required linter/test checks.
2. **Keep `.kb/` Up to Date**:
   - Whenever you make a significant change to architecture, data models, execution/sync behavior, API contracts, frontend state management, or dev tooling, update the corresponding `.kb/*.md` file(s) in the same turn.
3. **Keep `.kb/` Concise**:
   - Entries must remain high-signal, architectural, and brief. Document invariants, data flows, and contracts rather than copying large code blocks.
