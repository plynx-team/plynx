import type {
  NodeRunState,
  NodeSpec,
  Stage,
  StageGateState,
} from "../api/types.gen";
import { NodeRow } from "./NodeRow";
import { StageApprovalCard } from "./StageApprovalCard";

export interface StageCardProps {
  runId: string;
  stageId: string;
  stageDef?: Stage;
  gateState?: StageGateState;
  nodes: Array<{
    id: string;
    spec?: NodeSpec;
    state?: NodeRunState;
  }>;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string) => void;
}

export function StageCard({
  runId,
  stageId,
  stageDef,
  gateState,
  nodes,
  selectedNodeId,
  onSelectNode,
}: StageCardProps) {
  const title = stageDef?.title || (stageId !== "default" ? stageId : "Workflow Stage");
  const totalNodes = nodes.length;
  const completedNodes = nodes.filter(
    (n) => n.state?.status === "SUCCESS",
  ).length;
  const hasFailure = nodes.some((n) => n.state?.status === "FAILED");
  const isRunning = nodes.some(
    (n) =>
      n.state?.status === "RUNNING" ||
      n.state?.status === "BUILDING_ENVIRONMENT",
  );
  const isWaiting =
    gateState?.status === "WAITING" ||
    nodes.some((n) => n.state?.status === "WAITING_FOR_USER");
  const isComplete = totalNodes > 0 && completedNodes === totalNodes;

  let stageStatusBadge = "bg-slate-900 text-slate-400 border-slate-800";
  let stageStatusText = "PENDING";

  if (hasFailure) {
    stageStatusBadge = "bg-rose-950 text-rose-300 border-rose-800";
    stageStatusText = "FAILED";
  } else if (isWaiting) {
    stageStatusBadge = "bg-amber-950 text-amber-300 border-amber-800";
    stageStatusText = gateState?.status === "WAITING" ? "GATE WAITING" : "WAITING";
  } else if (isRunning) {
    stageStatusBadge = "bg-sky-950 text-sky-300 border-sky-800 animate-pulse";
    stageStatusText = "RUNNING";
  } else if (isComplete) {
    stageStatusBadge = "bg-emerald-950 text-emerald-300 border-emerald-800";
    stageStatusText = "COMPLETED";
  }

  const percent = totalNodes > 0 ? Math.round((completedNodes / totalNodes) * 100) : 0;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5 space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h2 className="text-base font-bold text-white">{title}</h2>
            {stageDef?.require_approval && (
              <span className="rounded bg-indigo-950 border border-indigo-800 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-300">
                approval gate {gateState?.status === "APPROVED" ? "✓" : "⏳"}
              </span>
            )}
          </div>
          <p className="font-mono text-xs text-slate-500">stage: {stageId}</p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 font-mono">
            {completedNodes}/{totalNodes} completed
          </span>
          <span
            className={`rounded border px-2 py-0.5 text-xs font-semibold tracking-wide ${stageStatusBadge}`}
          >
            {stageStatusText}
          </span>
        </div>
      </div>

      {/* Stage progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full transition-all duration-300 ${
            hasFailure
              ? "bg-rose-500"
              : isComplete
              ? "bg-emerald-500"
              : "bg-sky-500"
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Nodes list */}
      <div className="space-y-2 pt-1">
        {nodes.map((node) => (
          <NodeRow
            key={node.id}
            nodeId={node.id}
            nodeState={node.state}
            spec={node.spec}
            isSelected={selectedNodeId === node.id}
            onSelect={onSelectNode}
          />
        ))}
      </div>

      {/* Approval Card if gate is waiting */}
      {gateState?.status === "WAITING" && (
        <div className="pt-2">
          <StageApprovalCard
            runId={runId}
            stageId={stageId}
            stageTitle={title}
            gateState={gateState}
          />
        </div>
      )}
    </div>
  );
}
