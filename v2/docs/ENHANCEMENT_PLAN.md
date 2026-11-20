# Plynx v2 UI & Engine Enhancement Plan

This document tracks the design decisions, architectural models, and implementation checklist for the 6 requested enhancements.

---

## 1. Architectural & State Models

### Item 1: History Depth Limit
- **Model**: Set default `limit` in `PushHistoryOptions` to 300.
- **Memory Footprint**: Average JSON workflow document is 10–20 KB. 300 snapshots represent ~3–6 MB in JavaScript heap memory, keeping memory usage minimal while offering generous undo history.
- **Coalescing**: Retain 600ms coalescing window for rapid keyboard edits (literals, titles, parameters) so continuous typing produces cohesive snapshots rather than 1 per character.

### Item 2: Elide Stage Block for Single-Stage `main`
- **Model**: Minimalist Canvas Model.
- **Rule**: If a workflow contains only the default `main` stage (`orderedStageIds.length === 1 && orderedStageIds[0] === "main"`):
  - Do not render a bounding `StageGroupNode`.
  - Child nodes render directly on the root canvas (`parentId = undefined`, `position = absoluteCoordinates`).
  - `built.stageGroupPositions["main"]` resolves to `{ x: 0, y: 0 }`, ensuring node drag-stop and coordinate calculations are unchanged.
- **Multi-Stage Transition**: As soon as a second stage is added (`+ Stage` or dropping into a new stage), `main` and the other stages render bounding boxes. If extra stages are deleted until only `main` remains, the container dissolves seamlessly.

### Item 3: Staged Input Prompting & Execution
- **Context & User Question**:
  > *"I noticed when I added an Operation into the second stage. I did not connect an input to it. When strted a run, it asked me right away that I need to fill it. I believe we agreed that I only would ask for this value when the previous stage completes 100%. Do you see any controversy? If not, please make sure that a user enters the inputs for the stage only when the previous stage is done"*
- **Controversy / Design Analysis**:
  1. *Upfront vs. Just-In-Time (JIT)*:
     - In batch CLI execution (headless CI/CD), users typically provide all parameters upfront via flags (`--set node.param=value`).
     - In the interactive UI, the entire value of multi-stage pipelines is often that Stage 2's parameters depend on Stage 1's intermediate results or human inspection. Forcing the user to guess Stage 2 inputs before Stage 1 even runs defeats this workflow.
  2. *Engine Mechanics*:
     - Currently, `POST /runs` accepts `inputs: Record<string, unknown>`.
     - In `validator.py`, unbound inputs are classified as `severity="warning"`, so the backend does not block running a workflow if a later stage has unbound inputs.
     - When Stage 1 completes, Stage 2's nodes become ready. If an unbound required input is missing, the node would fail with a missing parameter error during Python execution unless intercepted.
  3. *Recommended Model (Interactive Stage Input Gate)*:
     - **At Run Launch**: `RunInputsForm` only prompts for unbound inputs belonging to the **first stage** (or stages that have ready nodes). Unbound inputs for later stages are excluded or shown as "Deferred to Stage X".
     - **Between Stages**: When Stage 1 completes 100%, if Stage 2 has unbound required inputs:
       - The run transitions to `WAITING_FOR_USER` with a `StageInputPrompt` (extending the existing `stage_gates` mechanism or prompt card).
       - In `StepperView` and `GraphView`, an interactive input card appears (similar to `StageApprovalCard` / `CheckpointCard`) prompting the user: *"Stage 2 requires inputs before running"*.
       - Submitting the inputs injects them into the run state and resumes Stage 2 execution!

### Item 4: Canvas Drop Auto-Detection & Stage Highlighting
- **Model**: Spatial AABB Containment.
- **Rule**:
  - `OpPalette`: Remove the `Target Stage` selector dropdown. The palette becomes clean and solely focused on browsing and dragging operations.
  - While dragging over the canvas (`onDragOver`):
    - Compute cursor canvas coordinate `(flowX, flowY)`.
    - Test against all rendered stage bounding boxes: `stage.x <= flowX <= stage.x + stage.width && stage.y <= flowY <= stage.y + stage.height`.
    - Active hovered stage receives a visual highlight (`isDropTarget: true`, glowing primary border).
  - On drop (`onDrop`):
    - If dropped inside stage `S`, assign `node.stage = S`.
    - If dropped in empty space:
      - If single-stage `main`: assign to `main`.
      - If multiple stages exist: assign to the stage closest to the drop point, or default to `main`.

### Item 5: "New Workflow" Creation in Workflows View
- **Model**: Workflow Creation Dialog.
- **Interaction**:
  - Add `+ New Workflow` primary button to `ControlPanel` in `WorkflowPicker.tsx`.
  - Clicking opens `NewWorkflowModal`:
    - Workflow Name (e.g. `data_pipeline`)
    - File path (defaults to `workflows/<name>.yaml`, customizable)
  - On submit: saves an initial clean workflow document via `PUT /workflows/{path}`, then navigates directly to `/editor/{path}`.

### Item 6: Quick-Connect on Wire Drop (Unreal / Blender Style)
- **Model**: Contextual Search & Auto-Wire Dialog.
- **Interaction Flow**:
  1. User drags from an Output handle (source) or Input handle (target) and releases on empty canvas (`onConnectEnd` on `react-flow__pane`).
  2. Compute drop location in flow coordinates (`screenToFlowPosition`).
  3. Open a floating Quick-Connect search popup (`QuickConnectPopover`) anchored at the mouse cursor.
  4. The popup automatically filters the operations palette to operations that have **compatible ports**:
     - Dragged from Output (type `T`, media `M`): lists operations with inputs accepting `T` / `M`.
     - Dragged from Input (type `T`, media `M`): lists operations with outputs producing `T` / `M`.
  5. Search input with instant keyboard navigation (Arrow keys, Enter, Esc).
  6. Each matching operation displays its compatible ports (e.g., `↳ text`).
  7. Selecting an operation:
     - Spawns the node at the drop position.
     - Connects the edge automatically to the selected matching port.
     - Assigns the node to the stage at that canvas coordinate (or `main`).
     - Commits the entire action as a single atomic undoable snapshot in history!

---

## 2. Implementation Checklist

### Phase 1: History Stack Limit (300)
- [x] Update default history limit to `300` in `v2/ui/src/graph/history.ts`.
- [x] Verify unit tests in `v2/ui/src/graph/history.test.ts`.

### Phase 2: Single-Stage `main` Rendering Elision
- [x] Update `v2/ui/src/graph/layout.ts` (`buildGraphElements`): omit `StageGroupNode` if only `main` is present.
- [x] Ensure child node positions on root canvas use absolute coordinates without `parentId`.
- [x] Verify `onNodeDragStop` and dagre auto-layout behavior with and without stage bounding boxes.
- [x] Add unit test verifying that single-stage `main` produces 0 `stageGroup` nodes, and multi-stage produces `N` `stageGroup` nodes.

### Phase 3: Stage Drop Auto-Detection & Palette Simplification
- [x] Remove `Target Stage` dropdown selector from `v2/ui/src/graph/OpPalette.tsx`.
- [x] In `v2/ui/src/graph/GraphView.tsx`, implement stage AABB detection during `onDragOver` and set `hoveredStageId`.
- [x] Update `StageGroupNode.tsx` to display active dropzone styling when hovered (`border-color: var(--color-primary)`, soft glow).
- [x] In `v2/ui/src/graph/WorkflowEditor.tsx`, update `handleDropOp` to resolve stage ID from canvas coordinates.
- [x] Add unit tests for stage drop detection and palette rendering.

### Phase 4: "New Workflow" Button & Creation Modal
- [ ] Add `+ New Workflow` button to `WorkflowPicker.tsx` toolbar.
- [ ] Create `NewWorkflowModal.tsx` component with name validation, path generation, and duplicate checking.
- [ ] Hook into `saveWorkflow` and router navigation (`/editor/:path`).
- [ ] Add unit tests in `WorkflowPicker.test.tsx` for new workflow creation.

### Phase 5: Quick-Connect on Wire Drop (Unreal / Blender Style)
- [ ] In `GraphView.tsx`, hook `onConnectStart` and `onConnectEnd`.
- [ ] Detect release over `.react-flow__pane` and capture drop flow coordinates and origin handle type/node.
- [ ] Create `QuickConnectPopover.tsx` component:
  - Positioned at mouse release point.
  - Type-safe port compatibility matching (`type` and `media` check).
  - Searchable list of compatible ops with nested port choices.
  - Keyboard navigation (Search focus, Up/Down, Enter, Esc).
- [ ] Wire insertion handler in `WorkflowEditor.tsx`: atomic `addNodeToWorkflow` + `connectEdgeInWorkflow` via `commitStateChange`.
- [ ] Add unit tests for quick-connect port filtering, node spawn, and edge wiring.

### Phase 6: Staged Input Prompting & Execution
- [ ] In `RunInputsForm.tsx`, group/filter unbound inputs: only require inputs for the initial active stage (Stage 1) at run launch.
- [ ] Design and implement stage transition input handling when Stage 1 completes 100%:
  - Prompt user for Stage 2 inputs before Stage 2 nodes execute.
  - Allow user to provide inputs via the stepper/graph run view and resume.
- [ ] Add backend/frontend unit and integration tests.
