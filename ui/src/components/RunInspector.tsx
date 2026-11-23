import { useMemo } from "react";
import type {
  OpEntry,
  OutputPortSpec,
  RunState,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import { GraphView } from "../graph/GraphView";
import {
  buildOutputPreviewTarget,
  NodeInspector,
  type ArtifactPreviewTarget,
} from "../graph/NodeInspector";
import { computeWorkflowRunDiff, type WorkflowRunDiff } from "../graph/runDiff";
import { CheckpointCard } from "../stepper/CheckpointCard";
import { StageApprovalCard } from "../stepper/StageApprovalCard";
import { StepperView } from "../stepper/StepperView";
import { LogsPanel } from "./LogsPanel";

export type RunViewMode = "stepper" | "graph";

export interface RunInspectorProps {
  runState: RunState;
  viewMode: RunViewMode;
  ops: ReadonlyArray<OpEntry>;
  opsMap: Record<string, OpEntry>;
  /** Current live editor workflow (optional, used only for computing diff vs run snapshot). */
  editorWorkflow?: Workflow | null;
  /** Fallback layout if the run has no layout_snapshot. */
  fallbackLayout?: WorkflowLayout | null;
  /** Precomputed run diff (if omitted, computed from editorWorkflow vs runState). */
  runDiff?: WorkflowRunDiff | null;
  selectedNodeId?: string;
  onSelectNode: (nodeId: string | undefined) => void;
  onPreviewArtifact: (target: ArtifactPreviewTarget) => void;
  onApproved?: (stageId: string) => void;
  /** Optional header strip above LogsPanel showing selected node id + status. */
  showLogsHeader?: boolean;
  /** Render the right-side NodeInspector inside RunInspector (default true). */
  showNodeInspector?: boolean;
}

/**
 * Unified read-only run snapshot inspector shared between `/runs/:id` (RunDetail)
 * and in-editor Run Inspection mode (WorkflowEditor).
 *
 * Always renders the run's true `workflow_snapshot` and `layout_snapshot` (falling back
 * to `editorWorkflow` / `fallbackLayout` only when a legacy run lacks snapshots).
 */
export function RunInspector({
  runState,
  viewMode,
  ops,
  opsMap,
  editorWorkflow = null,
  fallbackLayout = null,
  runDiff: externalRunDiff,
  selectedNodeId,
  onSelectNode,
  onPreviewArtifact,
  onApproved,
  showLogsHeader = false,
  showNodeInspector = true,
}: RunInspectorProps) {
  const snapshotWorkflow = runState.workflow_snapshot ?? editorWorkflow ?? null;
  const snapshotLayout = runState.layout_snapshot ?? fallbackLayout ?? null;

  const computedDiff = useMemo(
    () =>
      externalRunDiff !== undefined
        ? externalRunDiff
        : editorWorkflow
          ? computeWorkflowRunDiff(editorWorkflow, runState)
          : null,
    [externalRunDiff, editorWorkflow, runState],
  );

  const handlePreviewNodeOutput = (nodeId: string, output: OutputPortSpec) => {
    onPreviewArtifact(buildOutputPreviewTarget(runState.id, nodeId, output));
  };

  const openCheckpoints = runState.checkpoints.filter((cp) => !cp.answered_at);
  const waitingGates = Object.values(runState.stage_gates).filter(
    (g) => g.status === "WAITING",
  );

  return (
    <div className="flex flex-1 min-h-0 flex-row overflow-hidden">
      {/* Center Workspace + Bottom Docked Logs Drawer */}
      <div
        className="flex flex-1 min-w-0 flex-col overflow-hidden relative"
        style={{ backgroundColor: "var(--bg-canvas)" }}
      >
        {/* Visually present view mode title for accessibility and tests */}
        <h2 className="sr-only">
          {viewMode === "stepper"
            ? "Workflow Stages (Stepper)"
            : "Workflow DAG (Graph)"}
        </h2>

        {/* Open Checkpoints & Stage Approvals overlay in Graph view */}
        {viewMode === "graph" &&
          (waitingGates.length > 0 || openCheckpoints.length > 0) && (
            <div className="p-2.5 space-y-2 shrink-0 max-h-[40vh] overflow-y-auto">
              {waitingGates.map((gate) => (
                <StageApprovalCard
                  key={gate.stage_id}
                  runId={runState.id}
                  stageId={gate.stage_id}
                  stageTitle={
                    snapshotWorkflow?.stages?.[gate.stage_id]?.title ||
                    gate.stage_id
                  }
                  gateState={gate}
                  workflow={snapshotWorkflow}
                  runInputs={runState.run_inputs}
                  opsMap={opsMap}
                  onApproved={onApproved}
                />
              ))}
              {openCheckpoints.map((cp) => (
                <CheckpointCard
                  key={`${cp.node_id}-${cp.checkpoint_id}`}
                  runId={runState.id}
                  checkpoint={cp}
                />
              ))}
            </div>
          )}

        <div
          className={`flex-1 min-h-0 ${
            viewMode === "graph" ? "overflow-hidden h-full" : "overflow-y-auto"
          }`}
        >
          {viewMode === "stepper" ? (
            <StepperView
              runState={runState}
              workflowDoc={
                snapshotWorkflow
                  ? { workflow: snapshotWorkflow, layout: snapshotLayout }
                  : null
              }
              runDiff={computedDiff}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
              opsMap={opsMap}
              onApproved={onApproved}
            />
          ) : (
            <GraphView
              workflow={snapshotWorkflow}
              layout={snapshotLayout}
              runState={runState}
              runDiff={computedDiff}
              ops={ops}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
              onPreviewOutput={handlePreviewNodeOutput}
              readOnly={true}
              heightClassName="h-full"
            />
          )}
        </div>

        {/* Bottom Docked Logs Drawer when a node is selected */}
        {selectedNodeId && (
          <div>
            {showLogsHeader && (
              <div
                className="flex items-center justify-between px-3 py-1 text-xs"
                style={{
                  backgroundColor: "var(--bg-panel)",
                  borderTop: "1px solid var(--border-subtle)",
                }}
              >
                <span className="font-mono">
                  Selected Node: <strong>{selectedNodeId}</strong> (
                  {runState.nodes[selectedNodeId]?.status ?? "PENDING"})
                </span>
              </div>
            )}
            <LogsPanel
              runId={runState.id}
              nodeId={selectedNodeId}
              onClose={() => onSelectNode(undefined)}
            />
          </div>
        )}
      </div>

      {/* Right Docked PropertiesBar */}
      {showNodeInspector && snapshotWorkflow && (
        <NodeInspector
          nodeId={selectedNodeId}
          workflow={snapshotWorkflow}
          opsMap={opsMap}
          runState={runState}
          nodeDiff={
            selectedNodeId ? computedDiff?.nodes?.[selectedNodeId] : undefined
          }
          readOnly={true}
          onPreviewArtifact={onPreviewArtifact}
        />
      )}
    </div>
  );
}
