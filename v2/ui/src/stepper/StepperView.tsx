import type {
  NodeRunState,
  NodeSpec,
  OpEntry,
  RunState,
  Stage,
  WorkflowDocument,
} from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";
import type { WorkflowRunDiff } from "../graph/runDiff";
import { CheckpointCard } from "./CheckpointCard";
import { StageCard } from "./StageCard";

export interface StepperViewProps {
  runState?: RunState | null;
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
    ...(runState?.workflow_snapshot?.stages || {}),
    ...(workflow?.stages || {}),
  };
  const nodesDef = workflow?.nodes || {};

  const allNodeIds = Array.from(
    new Set([
      ...Object.keys(nodesDef),
      ...(runState ? Object.keys(runState.nodes) : []),
      ...Object.entries(runDiff?.nodes ?? {})
        .filter(([, diff]) => diff.status === "new_in_run")
        .map(([id]) => id),
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
      nodesDef[nodeId] ?? runState?.workflow_snapshot?.nodes?.[nodeId];
    const state = runState?.nodes[nodeId];
    const stageId = spec?.stage || "default";

    if (!stageGroups[stageId]) {
      stageGroups[stageId] = [];
    }
    stageGroups[stageId].push({ id: nodeId, spec, state });
  }

  const stageIds = Object.keys(stageGroups).filter(
    (id) => stageGroups[id].length > 0 || stagesDef[id] !== undefined,
  );

  const snapshotNodeIds = runState
    ? Object.keys(runState.workflow_snapshot?.nodes ?? runState.nodes)
    : allNodeIds;
  const totalNodes = snapshotNodeIds.length;
  const completedNodes = runState
    ? snapshotNodeIds.filter((id) => runState.nodes[id]?.status === "SUCCESS")
        .length
    : 0;
  const cacheHitCount = runState
    ? snapshotNodeIds.filter((id) => runState.nodes[id]?.cache_hit).length
    : 0;
  const overallPercent =
    totalNodes > 0 && runState
      ? Math.round((completedNodes / totalNodes) * 100)
      : 0;
  const isRunActive =
    runState &&
    (runState.status === "RUNNING" || runState.status === "WAITING_FOR_USER");

  const activeCheckpoints = isRunActive && runState
    ? runState.checkpoints.filter((cp) => !cp.answered_at)
    : [];
  const waitingStageIds = new Set(
    runState
      ? Object.entries(runState.stage_gates)
          .filter(([, g]) => isRunActive && g.status === "WAITING")
          .map(([sid]) => sid)
      : [],
  );
  const hasActiveFeedback =
    activeCheckpoints.length > 0 || waitingStageIds.size > 0;

  return (
    <div className="p-3 space-y-3">
      {/* Overall Progress Header or Draft Banner */}
      {runState ? (
        <div
          className={`rounded p-3 space-y-2 transition-opacity duration-200 ${
            hasActiveFeedback ? "opacity-40 hover:opacity-100" : ""
          }`}
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
      ) : (
        <div
          data-testid="stepper-draft-banner"
          className="rounded p-3 space-y-1"
          style={{
            backgroundColor: "var(--bg-panel)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div
            className="flex items-center gap-2 text-xs font-semibold"
            style={{ color: "var(--text-secondary)" }}
          >
            <FeatherIcon name="edit-3" size={13} />
            <span>Workflow Draft (Not Running)</span>
          </div>
          <p className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
            This stepper displays stages and nodes in draft mode. Switch to Graph mode to edit or click &quot;Run Workflow&quot; to execute.
          </p>
        </div>
      )}

      {/* Active Checkpoints */}
      {isRunActive &&
        runState &&
        activeCheckpoints.map((cp) => (
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
          const gateState = runState?.stage_gates[stageId];
          const nodes = stageGroups[stageId];
          const isWaitingGate = waitingStageIds.has(stageId);
          const isDimmed = hasActiveFeedback && !isWaitingGate;

          return (
            <div
              key={stageId}
              className={`transition-opacity duration-200 ${
                isDimmed ? "opacity-40 hover:opacity-100" : "opacity-100"
              }`}
            >
              <StageCard
                runId={runState?.id ?? ""}
                stageId={stageId}
                stageDef={stageDef}
                gateState={gateState}
                runActive={Boolean(isRunActive)}
                runDiff={runDiff}
                nodes={nodes}
                selectedNodeId={selectedNodeId}
                onSelectNode={onSelectNode}
                workflow={workflow}
                runInputs={runState?.run_inputs}
                opsMap={opsMap}
                onApproved={onApproved}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
