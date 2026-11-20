import type {
  NodeRunState,
  NodeSpec,
  OpEntry,
  RunState,
  Stage,
  WorkflowDocument,
} from "../api/types.gen";
import type { WorkflowRunDiff } from "../graph/runDiff";
import { CheckpointCard } from "./CheckpointCard";
import { StageCard } from "./StageCard";

export interface StepperViewProps {
  runState: RunState;
  workflowDoc?: WorkflowDocument | null;
  runDiff?: WorkflowRunDiff | null;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string) => void;
  opsMap?: Record<string, OpEntry>;
  onApproved?: (stageId: string) => void;
}

export function StepperView({
  runState,
  workflowDoc,
  runDiff = null,
  selectedNodeId,
  onSelectNode,
  opsMap,
  onApproved,
}: StepperViewProps) {
  const workflow = workflowDoc?.workflow;
  const stagesDef = {
    ...(runState.workflow_snapshot?.stages || {}),
    ...(workflow?.stages || {}),
  };
  const nodesDef = workflow?.nodes || {};

  const allNodeIds = Array.from(
    new Set([
      ...Object.keys(nodesDef),
      ...Object.keys(runState.nodes),
      ...Object.keys(runDiff?.nodes ?? {}),
    ]),
  );

  const stageGroups: Record<
    string,
    Array<{ id: string; spec?: NodeSpec; state?: NodeRunState }>
  > = {};

  for (const stageId of Object.keys(stagesDef)) {
    stageGroups[stageId] = [];
  }

  for (const nodeId of allNodeIds) {
    const spec =
      nodesDef[nodeId] ?? runState.workflow_snapshot?.nodes?.[nodeId];
    const state = runState.nodes[nodeId];
    const stageId = spec?.stage || "default";

    if (!stageGroups[stageId]) {
      stageGroups[stageId] = [];
    }
    stageGroups[stageId].push({ id: nodeId, spec, state });
  }

  const stageIds = Object.keys(stageGroups).filter(
    (id) => stageGroups[id].length > 0 || stagesDef[id] !== undefined,
  );

  const totalNodes = allNodeIds.length;
  const completedNodes = allNodeIds.filter(
    (id) => runState.nodes[id]?.status === "SUCCESS",
  ).length;
  const cacheHitCount = allNodeIds.filter(
    (id) => runState.nodes[id]?.cache_hit,
  ).length;
  const overallPercent =
    totalNodes > 0 ? Math.round((completedNodes / totalNodes) * 100) : 0;
  const isRunActive =
    runState.status === "RUNNING" || runState.status === "WAITING_FOR_USER";

  return (
    <div className="p-3 space-y-3">
      {/* Overall Progress Header */}
      <div
        className="rounded p-3 space-y-2"
        style={{
          backgroundColor: "var(--bg-panel)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-semibold">Overall Progress</span>
            <span
              className="font-mono"
              style={{ color: "var(--text-secondary)" }}
            >
              {completedNodes} of {totalNodes} nodes completed ({overallPercent}
              %)
            </span>
          </div>
          {cacheHitCount > 0 && (
            <span className="status-badge READY !text-xs">
              {cacheHitCount} {cacheHitCount === 1 ? "node" : "nodes"} cache hit
            </span>
          )}
        </div>

        <div
          className="h-1.5 w-full overflow-hidden rounded-sm"
          style={{ backgroundColor: "var(--bg-panel-secondary)" }}
        >
          <div
            className="h-full transition-all duration-300"
            style={{
              width: `${overallPercent}%`,
              backgroundColor:
                runState.status === "FAILED"
                  ? "var(--color-status-failed)"
                  : "var(--color-status-success)",
            }}
          />
        </div>
      </div>

      {/* Active Checkpoints */}
      {isRunActive &&
        runState.checkpoints
          .filter((cp) => !cp.answered_at)
          .map((cp) => (
            <CheckpointCard
              key={`${cp.node_id}-${cp.checkpoint_id}`}
              runId={runState.id}
              checkpoint={cp}
            />
          ))}

      {/* Stage Cards */}
      <div className="space-y-3">
        {stageIds.map((stageId) => {
          const stageDef: Stage | undefined = stagesDef[stageId];
          const gateState = runState.stage_gates[stageId];
          const nodes = stageGroups[stageId];

          return (
            <StageCard
              key={stageId}
              runId={runState.id}
              stageId={stageId}
              stageDef={stageDef}
              gateState={gateState}
              runActive={isRunActive}
              runDiff={runDiff}
              nodes={nodes}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
              workflow={workflow}
              runInputs={runState.run_inputs}
              opsMap={opsMap}
              onApproved={onApproved}
            />
          );
        })}
      </div>
    </div>
  );
}
