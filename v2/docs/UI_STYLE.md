# UI Style & Layout Specification (PLynx v2)

Rigid visual and interaction contract for `ui/`. All components must conform to this specification. Never use Tailwind `slate-*` or `emerald-*` defaults; use the neutral dark gray & Photoshop-blue tokens and docked desktop IDE layout defined below.

---

## 1. Design Tokens & Typography (`ui/src/index.css`)

Include the legacy v1 CSS custom properties verbatim in `:root`:

```css
:root {
  --font-sans: 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
  --font-size-sm: 12px;
  --font-size-base: 14px;
  --font-size-lg: 16px;
  --font-weight-regular: 400;
  --font-weight-semibold: 600;

  /* Photoshop-inspired Gray & Blue Theme */
  --bg-app: #1e1e1e;
  --bg-canvas: #232323;
  --bg-header: #262626;
  --bg-panel: #2b2b2b;
  --bg-panel-secondary: #242424;
  --bg-card: #333333;
  --bg-card-hover: #3e3e3e;
  --bg-button: #303030;
  --bg-button-hover: #3d3d3d;

  --border-subtle: #363636;
  --border-default: #404040;
  --border-strong: #525252;

  --color-primary: #2680eb;
  --color-primary-hover: #3d91f5;
  --color-primary-active: #1b6cd4;
  --color-primary-selected: #244b7a;
  --color-primary-subtle: rgba(38, 128, 235, 0.18);

  --text-primary: #ebebeb;
  --text-secondary: #b0b0b0;
  --text-tertiary: #787878;

  /* Status Colors */
  --color-status-success: #38c172;
  --color-status-ready: #48bb78;
  --color-status-running: #00d8ff;
  --color-status-in-queue: #ffa726;
  --color-status-failed: #f44336;
  --color-status-canceled: #d946ef;
  --color-status-created: #b0b0b0;
  --color-status-static: #ecc94b;

  /* Semantic Feedback */
  --color-success: #38c172;
  --color-warning: #ffa726;
  --color-error: #f44336;
  --color-info: #00d8ff;
}
```

### Base Element Rules
- `html, body, #root`: `height: 100%; max-height: 100%; margin: 0; background-color: var(--bg-app); color: var(--text-primary); font-family: var(--font-sans); font-size: var(--font-size-base);`
- `input, select, textarea`: `border: 1px solid var(--border-default); border-radius: 2px; background-color: var(--bg-panel-secondary); color: var(--text-primary); font-family: var(--font-sans);`
- Scrollbars: `8px` width/height, track `var(--bg-app)`, thumb `var(--border-default)` (hover `var(--border-strong)`), `border-radius: 4px`.

---

## 2. Icons & Static Assets (`feather-icons` + `ui/public/`)

- **Icons (`feather-icons`)**:
  - Use the `feather-icons` package and a typed `<FeatherIcon name="..." size={16} />` component (ported from legacy `ui/src/components/Common/Icon.tsx` and recorded in `docs/LEGACY_MAP.md`).
  - Do **not** copy static `/icons/*.svg` files or render icons with `<img src="/icons/...">`. Render inline `<svg>` via `FeatherIcon` so `stroke="currentColor"` inherits button/port text and hover colors natively.
  - Standard Feather icon mappings:
    - Toolbar view toggles: `sliders` (Stepper), `grid` (Graph), `list` (Runs)
    - Toolbar actions: `save` (Save), `check-square` (Validate), `shuffle` / `layout` (Rearrange), `play` (Run), `copy` (Duplicate), `trash-2` / `x` (Delete / Cancel), `rotate-ccw` (Resume / Refresh)
    - Port & media types: `file-text` (`str` / text), `hash` (`int` / `float`), `toggle-left` (`bool`), `code` (`dict` / `list` / json), `file` (`file`), `folder` (`directory`), `image` (image media), `help-circle` (help tooltip), `eye` (Preview), `link-2` (Bind/Unbind reference), `search` (Search)
- **Brand Assets (`ui/public/`)**:
  - Copy only `ui/public/logo.png` and `ui/public/favicon.png` from legacy `ui/public/` (and record in `docs/LEGACY_MAP.md`).

---

## 3. Application Shell & Top Header (`.Header`)

Full-viewport desktop IDE layout (`display: flex; flex-direction: column; height: 100vh; overflow: hidden`). No centered `max-w-*` page wrapper or outer page padding.

- **Top Header (`.Header`)**:
  - `height: 40px; flex-shrink: 0; background-color: var(--bg-header); border-bottom: 1px solid var(--border-subtle); padding: 0 12px;`
  - Left logo (`/logo.png`, `height: 28px`) + navigation links (`Workflows`, `Runs`) separated by `18px` vertical `1px solid var(--border-default)` dividers (`.separator`).
  - Navigation items (`.Item`): full `40px` height, `padding: 0 14px`, `border-bottom: 3px solid transparent`.
    - Hover: `color: var(--text-primary); border-bottom-color: var(--border-strong);`
    - Active: `color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary);`

---

## 4. Sub-Header Control Panel Toolbar (`.control-panel` & `.control-button`)

Every primary view (`ListPage` and Unified `WorkflowEditor` / `RunDetail`) renders an edge-to-edge `.control-panel` directly beneath `.Header`:

- **`.control-panel`**:
  - `min-height: 40px; background-color: var(--bg-panel); padding: 4px 8px; border-top: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle); display: flex; align-items: center; gap: 4px;`
- **`.control-button`**:
  - `height: 32px; padding: 4px 10px; gap: 6px; border-radius: 3px; background-color: var(--bg-button); border: 1px solid var(--border-default); color: var(--text-primary); font-size: 14px;`
  - Contains `16x16` `<FeatherIcon name="..." size={16} />` + `.control-button-text`.
  - Hover: `background-color: var(--bg-button-hover); border-color: var(--border-strong);`
  - Active: `background-color: var(--color-primary); border-color: var(--color-primary);`
  - Selected (`.selected`): `background-color: var(--color-primary-selected); border-color: var(--color-primary);`
- **Segmented View Toggles (`.control-toggle`)**:
  - Adjacent `.control-button` items with `margin: 0; border-radius: 0` (`first` has `4px 0 0 4px`, `last` has `0 4px 4px 0`).
- **Vertical Divider (`.control-separator`)**:
  - `1px` vertical bar `#444`, `margin: 6px 8px`.

---

## 5. Unified Workflow & Run Workspace

Clicking a workflow in `/workflows` opens the unified workspace directly:
- **Control Panel Toolbar**:
  - View mode toggle group (`.control-toggle`): **`Stepper`** (`sliders`) | **`Graph`** (`grid`) | **`Runs`** (`list`, filtered to runs of this workflow).
  - Separator.
  - Action buttons: **`Save`** (`save`, with dirty indicator), **`Validate`** (`check-square`), **`Rearrange`** (`layout`, auto-layout), **`Run`** (`play`), plus **`Duplicate`** (`copy`) / **`Delete`** (`trash-2`) when a node/edge is selected, and **`Cancel`** (`x`) / **`Resume`** (`rotate-ccw`) when viewing an active/failed run.
  - When clicking **`Run`**, if the workflow has unbound required inputs (or if the user opens run options), show a compact v1-styled Run Inputs modal/drawer; if all inputs have defaults or are wired, start immediately (or allow one-click launch).
- **3-Pane Docked Workspace (`flex: 1; min-height: 0; display: flex; flex-direction: row; overflow: hidden`)**:
  1. **Left Docked Sidebar — Operations Hub (`.hub-panel`, `width: 250px` in editable Graph mode)**:
     - `background-color: var(--bg-panel-secondary); border-right: 1px solid var(--border-subtle);`
     - Top search input (`/` or `Cmd+K`) + target stage selector.
     - Collapsible category tree with `.hub-arrow` chevron and `.hub-entry-group-title` (`font-weight: 600`, hover `var(--bg-card-hover)`).
     - Compact draggable operation items (`.hub-item-node`): `background-color: var(--bg-card); padding: 5px; border-radius: 3px; margin: 2px 0; display: grid; grid-template-columns: 27px 1fr 16px;` (icon, title, `?` description tooltip).
  2. **Center Workspace (`flex: 1; min-width: 0; display: flex; flex-direction: column; background-color: var(--bg-canvas)`)**:
     - Top area (`flex: 1; min-height: 0`): either **Graph Canvas** or **Stepper View** (or **Workflow Runs List**).
     - Bottom area (when viewing a run with a selected node): **Collapsible Logs Drawer** docked to the bottom edge of the center pane (`border-top: 1px solid var(--border-subtle); background-color: var(--bg-app)`).
  3. **Right Docked Sidebar — Properties Bar (`.PropertiesBar`, `width: 300px; min-width: 300px`)**:
     - `background-color: var(--bg-panel); border-left: 1px solid var(--border-subtle); padding: 5px; overflow-y: auto;`
     - When no node is selected: shows **`Properties of <Workflow Name>`** (workflow title, description, concurrency, stages summary, latest run summary).
     - When a node is selected: shows **`Properties of <Node Title>`** with `.PropertiesBox` sections:
       - **Metadata & Stage**: Title, Stage selector, Op ID (`<pack>/<module>:<Op>`).
       - **Description (Markdown)**: Formatted Markdown description rendered via `MarkdownPreviewer`.
       - **Inputs / Parameters**: `.PropertiesBoxContent` (`background-color: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 5px;`) containing `.ParameterItem` rows (`display: grid; grid-template-columns: 38% 1fr; margin: 5px 0; align-items: center;`) with literal widgets and reference bind/unbind controls.
       - **Outputs & Inline Previews**: `.OutputItem` rows (`display: grid; grid-template-columns: 42% 58%; padding: 2px 0;`) with `.OutputItemPreview` (`color: var(--color-primary)`) opening `ArtifactPreviewDialog`, plus an **inline live output preview box** directly below each completed output port inside the `PropertiesBar`.

---

## 6. Graph Canvas & Node Cards (`.flow-node` — Blender / Photoshop Node Style)

- **Canvas**:
  - `background-color: var(--bg-canvas)` (`#232323`).
  - React Flow `<Background color="#383838" gap={16} size={1.5} />`.
  - Controls button background `#2b2b2b`, border `#444`, hover `#444`, text `#eee`.
  - MiniMap background `#1e1e1e`, mask `rgba(30, 30, 30, 0.6)`, node fill `#666`.
  - Default edges: `strokeWidth: 4px; stroke: #777; stroke-opacity: 0.7;`. Selected edge: `stroke: var(--color-primary) !important; stroke-opacity: 0.95;`.
  - Bottom-left watermark (`.BackgroundLabels`): fixed/absolute at `bottom: 16px`, `pointer-events: none`, `.Title` `font-size: 26px; color: rgba(235, 235, 235, 0.75);`.
  - Stage group frames (`StageGroupNode`): subtle border (`1px dashed #3c3c3c`), translucent header (`rgba(38, 38, 38, 0.75)`), non-intrusive so node dragging and selection match legacy v1 feel.
- **Node Card (`.flow-node`)**:
  - `width: 240px`, `border: 2px solid #3c3c3c`, `border-radius: 10px`, `background-color: #2a2a2a`, `user-select: none`.
  - Selected state: `border: 2px solid var(--color-primary)` (`#2680eb`).
  - **Blender-Style Header (`.flow-node-header`)**:
    - `border-top-left-radius: 8px; border-top-right-radius: 8px; border-bottom: 1px solid #383838; min-height: 28px; padding: 6px 8px 4px 8px;`
    - Full header bar color encodes execution status + left status icon (`check-circle` for `SUCCESS`, spinning `loader` for `RUNNING`/`BUILDING_ENVIRONMENT`, `help-circle` for `WAITING_FOR_USER`, `alert-circle` for `FAILED`, `slash` for `CANCELED`/`BLOCKED`, `cpu` for idle) + `zap` bolt icon for cache hits. No text status pill crowding the title.
    - Status-tinted header background:
      - `PENDING` / `BUILDING_ENVIRONMENT`: `rgba(70, 70, 70, 0.75)`
      - `RUNNING`: `rgba(0, 75, 85, 0.85)`
      - `WAITING_FOR_USER`: `rgba(140, 95, 30, 0.8)`
      - `SUCCESS`: `rgba(25, 85, 45, 0.85)`
      - `FAILED`: `rgba(110, 20, 20, 0.85)`
      - `CANCELED` / `BLOCKED`: `rgba(75, 25, 75, 0.75)`
  - **Running Border Glow Animation**:
    - When node status is `RUNNING` or `BUILDING_ENVIRONMENT`, render the rotating conic-gradient border glow (`--color-status-running: #00d8ff`, `animation: border 2s linear infinite` with `filter: blur(10px)` on `::after`).
  - **Expandable Multiline / Markdown Description Section**:
    - Hidden when description is empty. When present, a compact chevron toggle in the node card expands/collapses a formatted Markdown description block (`MarkdownPreviewer`) directly below the header.
  - **Body (`.flow-node-body`) — ComfyUI / Blender Two-Zone Socket & Pill Widget Layout**:
    - **Top Two-Column Socket Zone (`.flow-node-sockets`)**:
      - Left column: Input sockets (`.flow-node-socket-row.input`) with **type-colored circular `10px` Handle dots** (`getPortIconColor(port.type)`).
      - Right column: Output sockets (`.flow-node-socket-row.output`) with port name, a compact inline `eye` icon button on the same row when the output artifact is ready, and **type-colored circular `10px` Handle dots**.
    - **Bottom Pill Widget Zone (`.flow-node-widgets`)**:
      - Every **unwired input port** renders in a ComfyUI sunken pill row (`.comfy-widget-pill`, `background-color: #1c1c1c; border: 1px solid #383838; border-radius: 12px;`) with the port icon + label on the left and the editable value (`str`, `int`, `float`, `bool`, enum `options`, `file`/`directory`) on the right, plus an inline expand toggle (`maximize-2` / `minimize-2`) that switches the pill into a recessed multiline prompt/JSON editor (`.comfy-widget-multiline`).

---

## 7. Stepper View, Checkpoints & Stage Approvals

- **Stepper Container**:
  - Scrollable inside the center workspace (`background-color: var(--bg-canvas); padding: 12px;`).
  - Compact overall progress bar in a `.PropertiesBoxContent`-styled header bar (`background-color: var(--bg-panel); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 8px 12px;`).
- **Stage Panels (`StageCard`)**:
  - `background-color: var(--bg-panel); border: 1px solid var(--border-subtle); border-radius: 4px;`
  - Header bar (`background-color: var(--bg-header); border-bottom: 1px solid var(--border-subtle); padding: 6px 10px;`) with stage title, completion counter, and `.status-badge`.
  - Node rows (`NodeRow`): `.list-item` style (`background-color: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 6px 10px; margin: 3px 0;`), highlighting with `border-color: var(--color-primary); background-color: var(--color-primary-selected);` when selected.
- **Checkpoint Card & Stage Approval Card**:
  - `background-color: var(--bg-panel); border: 1px solid var(--color-primary); border-left: 4px solid var(--color-warning); border-radius: 4px; padding: 10px 12px;`
  - Option buttons use `.control-button` with primary action highlighted in `var(--color-primary)`.

---

## 8. List Pages (`/workflows` and `/runs`) & Preview Dialog

- **List Pages (`.ListPage`)**:
  - Top `.control-panel` with `<SearchBar />` + filter/action `.control-button` items.
  - Scrollable `.list` container (`background-color: var(--bg-panel); flex: 1; overflow: auto; border: 1px solid var(--border-subtle);`).
  - `.list-header` grid row (`color: var(--text-secondary); font-weight: 600; border-bottom: 1px solid var(--border-default); margin: 3px; padding: 5px;`).
  - `.list-item` grid rows (`background-color: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 4px; margin: 3px; padding: 8px 10px; transition: all 0.1s ease-in;`).
    - Hover: `background-color: var(--bg-card-hover); border-color: var(--border-strong);`
    - Active: `background-color: var(--color-primary-selected); border-color: var(--color-primary);`
  - Status column uses `.status-badge.<STATUS>` (`border: 1px solid var(--border-default); border-radius: 5px; background-color: var(--bg-card); padding: 1px 6px; font-weight: 600;`).
- **Preview Modal (`ArtifactPreviewDialog`)**:
  - Matches legacy `PreviewDialog.css`: dark panel window (`background-color: var(--bg-panel); border: 1px solid var(--border-strong)`), `.preview-note-banner` (`background-color: var(--bg-card); border-left: 3px solid var(--color-primary)`), `.preview-download-button`, and `.preview-content-box` (`background-color: var(--bg-canvas); font-family: var(--font-mono)`).
