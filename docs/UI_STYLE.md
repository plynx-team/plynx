# UI Style & Invariants (PLynx v2)

Visual, interaction, and styling invariants for `ui/`.

## 1. Design Tokens & Theme

- **Tokens**: Defined in `ui/src/index.css`. Photoshop-inspired neutral dark gray (`--bg-app: #1e1e1e`, `--bg-canvas: #232323`, `--bg-panel: #2b2b2b`) and blue accents (`--color-primary: #2680eb`). Never use default Tailwind `slate-*` or `emerald-*`.
- **Typography**: Sans-serif (`var(--font-sans)`, Source Sans Pro / system fallback) for general UI; Monospace (`var(--font-mono)`, IBM Plex Mono) for technical IDs, run IDs, and code.
- **Scrollbars**: Custom 8px rounded scrollbars styled with `var(--bg-app)` and `var(--border-default)`.

## 2. Icons & Assets

- **Icons**: Render via typed `<FeatherIcon name="..." size={16} />` from `feather-icons` package with `stroke="currentColor"`. No static SVG icon files or `img` icon tags.
- **Brand Assets**: Only `logo.png` and `favicon.png` under `ui/public/`.

## 3. Application Shell & Top Navigation

- **Layout**: Full-viewport desktop IDE (`100vh`, flex column, `overflow: hidden`, no outer padding or centered wrappers).
- **Header (`.Header`)**: Fixed 40px bar with logo, navigation links (`Workflows`, `Runs`), and subtle bottom border.
- **Control Panel (`.control-panel`)**: 40px toolbar with segmented view toggles (`Graph`, `Stepper`, `Runs`) and action buttons (`Save`, `Run`, `Auto Layout`, etc.).

## 4. Unified Workspace (3-Pane Docked Layout)

- **Left Dock (250px)**: Two collapsible accordion sections:
  - *Runs & Mode* (`RunsHistoryPane`): Pinned `Working Draft` at top, followed by paginated runs of the workflow.
  - *Operations* (`.hub-panel`): Search input, stage selector, and draggable operation cards. Collapses automatically in Run Inspection mode.
- **Center Workspace**:
  - *Editor Mode*: Clean blueprint canvas (`var(--bg-canvas)`), neutral headers, draggable nodes.
  - *Run Inspection Mode*: Read-only snapshot overlay with inset status border, HUD banner (`Inspecting Run #<id>`), run diffs (`NOT IN RUN`, `DIFF`), and collapsible logs drawer.
- **Right Dock (300px, `.PropertiesBar`)**:
  - Workflow properties when nothing is selected; selected node properties (title, op ID, markdown docs, input controls, output links, and inline artifact previews) when a node is selected.

## 5. Graph Canvas & Node Cards

- **Canvas**: React Flow with `#232323` background, `#383838` grid dots, subtle dashed stage group frames (`StageGroupNode`), and bottom-left watermark.
- **Node Cards (`.flow-node`)**: 240px wide, rounded corners (10px), status-tinted Blender-style header with status icon, rotating border glow animation when `RUNNING`, socket zone (type-colored circular handle dots), and pill widget zone for unwired inputs.

## 6. Stepper View, Checkpoints & Gates

- **Stepper**: Scrollable stages with progress bar, completion counts, and status-highlighted node rows.
- **Stage validator** has a soft cyan pulse while running in Graph and Stepper. Reduced-motion settings keep the cyan outline static.
- **Prompts**: Checkpoint and Stage Approval cards with distinct left accent borders, clear question text, and action buttons.

## 7. List Pages & Modals

- **List Pages (`/workflows`, `/runs`)**: Search bar, table headers, monospace run IDs/paths, and status badges.
- **Preview Modal (`ArtifactPreviewDialog`)**: Dark panel with note banner, download button, and monospace preview content.
