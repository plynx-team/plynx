import type { Workflow } from "../api/types.gen";
import {
  ControlButton,
  ControlPanel,
  ControlSeparator,
} from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";
import type { EditorViewMode } from "./WorkflowEditor";

export interface WorkflowEditorToolbarProps {
  viewMode: EditorViewMode;
  onToggleViewMode: (mode: EditorViewMode) => void;
  workflow: Workflow | null;
  workflowPath: string;
  saving: boolean;
  isDirty: boolean;
  isInspectingRun: boolean;
  lastSavedAt: number | null;
  canUndo: boolean;
  canRedo: boolean;
  selectedNodeId?: string;
  selectedStageId?: string;
  selectedEdgeId?: string;
  stageCount: number;
  onSave: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onRunClick: () => void;
  onAutoLayout: () => void;
  onOpenAddStage: () => void;
  onDuplicateNode: () => void;
  onDeleteNode: () => void;
  onDeleteStage: (stageId: string) => void;
  onDeleteEdge: () => void;
}

export function WorkflowEditorToolbar({
  viewMode,
  onToggleViewMode,
  workflow,
  workflowPath,
  saving,
  isDirty,
  isInspectingRun,
  lastSavedAt,
  canUndo,
  canRedo,
  selectedNodeId,
  selectedStageId,
  selectedEdgeId,
  stageCount,
  onSave,
  onUndo,
  onRedo,
  onRunClick,
  onAutoLayout,
  onOpenAddStage,
  onDuplicateNode,
  onDeleteNode,
  onDeleteStage,
  onDeleteEdge,
}: WorkflowEditorToolbarProps) {
  return (
    <ControlPanel>
      <div className="control-toggle" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={viewMode === "stepper"}
          onClick={() => onToggleViewMode("stepper")}
          className={`control-button first ${
            viewMode === "stepper" ? "selected" : ""
          }`}
        >
          <FeatherIcon name="sliders" size={14} />
          <span className="control-button-text">Stepper</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={viewMode === "graph"}
          onClick={() => onToggleViewMode("graph")}
          className={`control-button last ${
            viewMode === "graph" ? "selected" : ""
          }`}
        >
          <FeatherIcon name="grid" size={14} />
          <span className="control-button-text">Graph</span>
        </button>
      </div>

      <ControlSeparator />

      <ControlButton
        icon="save"
        text={saving ? "Saving..." : "Save"}
        data-testid="btn-save-workflow"
        variant={isDirty ? "primary" : "default"}
        disabled={!workflow || saving || isInspectingRun}
        onClick={onSave}
      />

      <ControlButton
        icon="rotate-ccw"
        text="Undo"
        data-testid="btn-undo"
        disabled={!canUndo}
        onClick={onUndo}
        title="Undo (Ctrl+Z / ⌘Z)"
      />

      <ControlButton
        icon="rotate-cw"
        text="Redo"
        data-testid="btn-redo"
        disabled={!canRedo}
        onClick={onRedo}
        title="Redo (Ctrl+Shift+Z / ⌘⇧Z)"
      />

      <ControlButton
        icon="play"
        text="Run Workflow"
        data-testid="btn-run-workflow"
        variant="primary"
        onClick={onRunClick}
      />

      <ControlButton
        icon="layout"
        text="Auto Layout"
        data-testid="btn-auto-layout"
        disabled={!workflow || isInspectingRun}
        onClick={onAutoLayout}
      />

      <ControlButton
        icon="layers"
        text="+ Stage"
        data-testid="btn-add-stage"
        disabled={!workflow || isInspectingRun}
        onClick={onOpenAddStage}
      />

      <ControlSeparator />

      <ControlButton
        icon="copy"
        text="Duplicate Node"
        data-testid="btn-duplicate-node"
        disabled={!selectedNodeId || isInspectingRun}
        onClick={onDuplicateNode}
      />

      <ControlButton
        icon="trash-2"
        text="Delete Node"
        data-testid="btn-delete-node"
        variant="danger"
        disabled={!selectedNodeId || isInspectingRun}
        onClick={onDeleteNode}
      />

      {selectedStageId && (
        <ControlButton
          icon="trash-2"
          text="Delete Stage"
          data-testid="btn-delete-stage-toolbar"
          variant="danger"
          disabled={stageCount <= 1 || isInspectingRun}
          onClick={() => onDeleteStage(selectedStageId)}
        />
      )}

      {selectedEdgeId && (
        <ControlButton
          icon="scissors"
          text="Disconnect Edge"
          data-testid="btn-delete-edge"
          disabled={isInspectingRun}
          onClick={onDeleteEdge}
        />
      )}

      <div className="ml-auto flex items-center gap-2.5 pr-2 text-xs">
        <span
          className="font-mono truncate max-w-[260px]"
          style={{ color: "var(--text-secondary)" }}
          title={workflowPath}
        >
          {workflow?.name || workflowPath}
        </span>
        {isDirty ? (
          <span
            data-testid="dirty-indicator"
            className="status-badge WAITING"
          >
            Unsaved changes
          </span>
        ) : lastSavedAt ? (
          <span data-testid="save-status" className="status-badge READY">
            Saved
          </span>
        ) : null}
      </div>
    </ControlPanel>
  );
}
