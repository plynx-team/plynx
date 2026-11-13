# Plynx AI Instructions

Plynx is a domain-agnostic platform for building and running reproducible workflows (DAGs).

## Core Philosophy

1. **Everything is a `Node`**: Workflows, operations, sub-graphs, and files all use the same [`Node`](plynx/db/node.py) model. Sub-graphs are stored in a node's `_nodes` parameter (`ParameterTypes.LIST_NODE`).
2. **Atomic Operations**: Operations are isolated tasks that only share explicit `inputs`, `parameters`, and `outputs`. This enables caching and distributed execution.
3. **Plugin-Driven**: Core behavior is defined in [`config.yaml`](template_config.yaml) and loaded dynamically via [`plugin_manager.py`](plynx/utils/plugin_manager.py).
4. **Pythonic First**: Maintain and improve clean, idiomatic Python (3.10+) across the backend. The frontend (`ui/`) runs on React 18 and Vite; keep changes clean and functional, as broader frontend optimization may happen in the future.

## Codebase Structure

- [`plynx/base/`](plynx/base/): Abstract interfaces for plugins:
  - [`BaseExecutor`](plynx/base/executor.py): Executes or launches nodes (`run`, `launch`, `kill`, `validate`).
  - [`BaseResource`](plynx/base/resource.py): Handles input/output preparation, post-processing, and UI previews.
  - [`BaseHub`](plynx/base/hub.py): Searches and provides operations (from DB or static Python modules).
- [`plynx/db/`](plynx/db/): MongoDB models and managers. Models inherit from [`DBObject`](plynx/db/db_object.py) and use `@dataclass_json` + `@dataclass`.
- [`plynx/plugins/`](plynx/plugins/): Concrete implementations of `executors`, `resources`, and `hubs`.
- [`plynx/node/`](plynx/node/): Decorator SDK (`@operation`, `@input`, `@output`, `@param`) to define operations as Python functions/classes.
- [`plynx/service/`](plynx/service/): Backend services (`worker`, `worker_server`, `execute`, `cache`, `users`).
- [`plynx/web/`](plynx/web/): Flask REST API endpoints.
- [`plynx/constants/`](plynx/constants/): Enums (`Collections`, `NodeRunningStatus`, `NodeStatus`, `ParameterTypes`).
- [`plynx/utils/`](plynx/utils/): Config, MongoDB connector, file storage (`file_handler`), and DAG graph utilities (`node_utils`).
- [`tests/`](tests/): Pytest unit and integration tests.
- [`ui/`](ui/): React 18 web app built with Vite (`@mui/material`, `reactflow`). Commands: `npm start`, `npm run build`, `npm test`, `npm run lint`.

## Rules

- @[Python Rules](.agents/rules/python.md)
- @[Knowledge Base Rules](.agents/rules/knowledge_base.md)
