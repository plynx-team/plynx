import type {
  NodeRunState,
  NodeSpec,
  RunState,
  Stage,
  WorkflowDocument,
} from "../api/types.gen";
import { CheckpointCard } from "./CheckpointCard";
import { StageCard } from "./StageCard";

export interface StepperViewProps {
  runState: RunState;
  workflowDoc?: WorkflowDocument | null;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string) => void;
}

export function StepperView({
  runState,
  workflowDoc,
  selectedNodeId,
  onSelectNode,
}: StepperViewProps) {
  const workflow = workflowDoc?.workflow;
  const stagesDef = workflow?.stages || {};
  const nodesDef = workflow?.nodes || {};

  // All node IDs present in either workflow spec or run state
  const allNodeIds = Array.from(
    new Set([...Object.keys(nodesDef), ...Object.keys(runState.nodes)]),
  );

  // Group nodes by stage
  const stageGroups: Record<
    string,
    Array<{ id: string; spec?: NodeSpec; state?: NodeRunState }>
  > = {};

  // Initialize stages defined in workflow
  for (const stageId of Object.keys(stagesDef)) {
    stageGroups[stageId] = [];
  }

  for (const nodeId of allNodeIds) {
    const spec = nodesDef[nodeId];
    const state = runState.nodes[nodeId];
    const stageId = spec?.stage || "default";

    if (!stageGroups[stageId]) {
      stageGroups[stageId] = [];
    }
    stageGroups[stageId].push({ id: nodeId, spec, state });
  }

  // Remove empty stages that are not in workflow stages
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

  return (
    <div className="space-y-6">
      {/* Overall Progress Header */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-slate-200">Overall Progress</span>
            <span className="font-mono text-slate-400">
              {completedNodes} of {totalNodes} nodes completed ({overallPercent}%)
            </span>
          </div>
          {cacheHitCount > 0 && (
            <span className="rounded bg-teal-950 border border-teal-800 px-2 py-0.5 text-xs font-semibold text-teal-300">
              {cacheHitCount} {cacheHitCount === 1 ? "node" : "nodes"} cache hit
            </span>
          )}
        </div>

        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full transition-all duration-300 ${
              runState.status === "FAILED"
                ? "bg-rose-500"
                : runState.status === "SUCCESS"
                ? "bg-emerald-500"
                : "bg-emerald-500"
            }`}
            style={{ width: `${overallPercent}%` }}
          />
        </div>
      </div>

      {/* Active Checkpoints */}
      {runState.checkpoints
        .filter((cp) => !cp.answered_at)
        .map((cp) => (
          <CheckpointCard
            key={`${cp.node_id}-${cp.checkpoint_id}`}
            runId={runState.id}
            checkpoint={cp}
          />
        ))}

      {/* Stage Cards */}
      <div className="space-y-4">
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
              nodes={nodes}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
            />
          );
        })}
      </div>
    </div>
  );
}
