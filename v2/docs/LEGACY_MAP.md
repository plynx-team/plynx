# Legacy map (v1 -> v2)

The legacy code is at the repo root (`master`, tag `v1.12.0`). It is a **reference**. Paths here are relative to the repo root, one level above the v2 root. Read a legacy file before you copy it. Paths below were checked to exist on 2026-11-16. Their content was only partly read, so the "use" column is a pointer, not a promise.

Policy (owner, 2026-11-16): copying a legacy file into v2 and modifying it is allowed. Do not import legacy code. Log each copy in the table at the end.

## Python side

| Legacy path | Disposition | v2 target / note |
|---|---|---|
| `plynx/db/node_cache.py` (`generate_key`) | Reference | v1 key = sorted input values + parameter values + `original_node_id`, minus `IGNORED_CACHE_PARAMETERS`. v2 uses the formula in PROTOCOL.md section 6. Compare behavior, do not copy. |
| `plynx/db/node_cache_manager.py` | Reference | Cache lookup flow. v2 uses `cache_index` in SQLite. |
| `plynx/plugins/executors/dag.py` | Reference | Scheduling and dependency counting. v2 uses `graphlib`. |
| `plynx/plugins/executors/local.py`, `executors/python/local.py` | Reference | How v1 runs bash and Python nodes. v2 uses the harness. |
| `plynx/plugins/resources/common.py`, `resources/python/common.py` | Copy and modify | Preview generation for file, pdf, image, csv, tsv, json, dir types. Re-home as UI previewers or small server helpers (`GET .../outputs/{name}`). |
| `plynx/utils/thumbnails.py` | Copy and modify (if needed) | Thumbnails for the UI. Optional. |
| `plynx/node/` (`@operation`, `@input`, `@output`, `@param`) | Reference | v1 decorator SDK. v2 has `Op` and `@op` in `plynx-sdk`. |
| `plynx/constants/node_enums.py`, `parameter_types.py`, `resource_enums.py` | Reference | Compare against v2 statuses and types. Do not carry over `RESTORED`, `STATIC`, `SPECIAL`, `list_node`. |
| `plynx/utils/node_utils.py` | Reference | v1 graph utilities. |
| `plynx/service/execute.py` | Reference | Single-node execution entry. Compare with `plynx run-node`. |
| `plynx/bin/cli.py` | Reference | v1 CLI names. |
| `plynx/web/`, `plynx/db/`, `plynx/service/worker*.py`, `plynx/base/`, `plynx/utils/{db_connector,file_handler,plugin_manager,hub_node_registry,config}.py`, `plynx/plugins/hubs/` | Drop | MongoDB, Flask, workers, hubs, remote storage, auth. Non-goals. |

## UI side (`ui/src/`)

| Legacy path | Disposition | v2 target / note |
|---|---|---|
| `components/Dialogs/PreviewDialog.tsx`, `FileDialog.tsx` | Copy and modify | Seed for `ui/src/previewers/`. Replace MUI with Tailwind. |
| `components/Graph/` (`index.tsx`, `nodes/OperationNode.tsx`, `PropertiesBar.tsx`, `OutputItem.tsx`, `HubPanel*`) | Reference, copy small parts | Graph editor behavior to match: node look, ports, properties bar, palette. v2 uses `@xyflow/react`. Check the React Flow version first. |
| `components/Node/` (`ParameterItem.tsx`, `InOutList.tsx`, ...), `components/Common/{ParameterItem,ValueCodeItem,ValueColorItem,ValueList,RenderValueElement}.tsx` | Copy and modify | Widgets for literals: text, number, enum, list, code, color. |
| `components/Common/{SearchBar,HotKeys,Tooltip}.tsx` | Copy and modify | Palette search, shortcuts. |
| `components/{LogIn,LogInRedirect,UserView}/`, `cookie.ts`, `Common/passwordUtils.ts` | Drop | Auth. |
| `components/Dashboard/`, `NodeList/` | Reference | Lists of workflows and runs. v2 has Run list and Workflow picker. |
| `components/Editor/` | Reference | v1 workflow editor page. |

## Side-by-side verification checklist

Run the legacy stack with its own tools from the repo root (`docker-compose`, `make`). Do not change legacy files to do it. Then compare with v2:

- [ ] A cacheable node run twice: second run is a cache hit and runs no process (task 3.5).
- [ ] Changing one parameter re-runs only that node and its dependents (task 3.6).
- [ ] Parallel branches run concurrently (task 0.7 / 1.5).
- [ ] A failed node blocks only dependents (task 0.7).
- [x] Output previews for pdf, image, csv, json, text (task 6.7).
- [x] Parameter widgets: text, number, enum, list, code, color (task 6.11).
- [x] Graph editor: add node from palette, wire ports, delete, reload keeps the graph (tasks 6.9 to 6.12).

## Copy log

Add a row per copied file in the same commit as the copy.

| Date | Legacy source | v2 destination | Changes |
|---|---|---|---|
| 2026-11-17 | `ui/src/components/Dialogs/PreviewDialog.tsx` | `v2/ui/src/previewers/ArtifactPreviewDialog.tsx` | Ported to React 19 functional component with Tailwind CSS modal |
| 2026-11-17 | `plynx/plugins/resources/common.py` | `v2/ui/src/previewers/{Csv,Json,Image,Pdf,Text,Markdown}Previewer.tsx` | Ported preview logic from Python classes to React components |
| 2026-11-19 | `ui/src/index.css`, `ui/src/App.css`, `ui/src/components/header/style.css`, `ui/src/components/controls.css`, `ui/src/components/NodeList/{List,items}.css` | `v2/ui/src/index.css` | Ported Photoshop dark gray & blue theme tokens, 40px Header, control-panel, control-button, and ListPage styles |
| 2026-11-19 | `ui/src/components/Common/Icon.tsx` | `v2/ui/src/components/FeatherIcon.tsx` | Ported `feather-icons` inline SVG renderer with typed port/media icon helpers |
| 2026-11-19 | `ui/src/components/Common/{ControlButton,SearchBar}.tsx` | `v2/ui/src/components/ControlPanel.tsx` | Ported toolbar buttons, segmented toggles, separator, and search input to functional React 19 components using `FeatherIcon` |
| 2026-11-19 | `ui/public/{logo,favicon}.png` | `v2/ui/public/{logo,favicon}.png` | Copied PLynx header logo and favicon |
| 2026-11-19 | `ui/src/components/Graph/nodes/{OperationNode.tsx,OperationNode.css}`, `ui/src/components/Graph/style.css` | `v2/ui/src/graph/{WorkflowNode,GraphView}.tsx`, `v2/ui/src/index.css` | Ported `#2a2a2a` node cards, status-tinted uppercase headers, `#00d8ff` conic-gradient running glow, inline scalar inputs/previews, and `.BackgroundLabels` canvas watermark |
| 2026-11-19 | `ui/src/components/Graph/{HubPanel.tsx,HubPanel.css,PropertiesBar.tsx,OutputItem.css}`, `ui/src/components/Common/ParameterItem.css` | `v2/ui/src/graph/{OpPalette,NodeInspector,LiteralWidget}.tsx`, `v2/ui/src/components/LogsPanel.tsx` | Ported 250px left `.hub-panel`, 300px right `.PropertiesBar` (`40%/60%` two-column rows & workflow properties fallback), and collapsible bottom Logs drawer |
