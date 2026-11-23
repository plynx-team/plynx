import type {
  NodeRunState,
  NodeSpec,
  OpEntry,
  Stage,
  StageGateState,
  Workflow,
} from "../api/types.gen";
import type { WorkflowRunDiff } from "../graph/runDiff";
import { FeatherIcon } from "../components/FeatherIcon";
import { NodeRow } from "./NodeRow";
import { StageApprovalCard } from "./StageApprovalCard";

export interface StageCardProps {
  runId: string;
  stageId: string;
  stageDef?: Stage;
  gateState?: StageGateState;
  runActive?: boolean;
  runDiff?: WorkflowRunDiff | null;
  nodes: Array<{
    id: string;
    spec?: NodeSpec;
    state?: NodeRunState;
  }>;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string) => void;
  workflow?: Workflow | null;
  runInputs?: Record<string, unknown>;
  opsMap?: Record<string, OpEntry>;
  onApproved?: (stageId: string) => void;
}

export function StageCard({
  runId,
  stageId,
  stageDef,
  gateState,
  runActive = true,
  runDiff = null,
  nodes,
  selectedNodeId,
  onSelectNode,
  workflow,
  runInputs,
  opsMap,
  onApproved,
}: StageCardProps) {
  const title =
    stageDef?.title || (stageId !== "default" ? stageId : "Workflow Stage");
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

  let stageStatusClass = "status-badge PENDING";
  let stageStatusText = "PENDING";

  if (hasFailure) {
    stageStatusClass = "status-badge FAILED";
    stageStatusText = "FAILED";
  } else if (isWaiting) {
    stageStatusClass = "status-badge WAITING";
    stageStatusText =
      gateState?.status === "WAITING" ? "GATE WAITING" : "WAITING";
  } else if (isRunning) {
    stageStatusClass = "status-badge RUNNING";
    stageStatusText = "RUNNING";
  } else if (isComplete) {
    stageStatusClass = "status-badge COMPLETED";
    stageStatusText = "COMPLETED";
  }

  const percent =
    totalNodes > 0 ? Math.round((completedNodes / totalNodes) * 100) : 0;

  return (
    <div
      className="rounded"
      style={{
        backgroundColor: "var(--bg-panel)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      {/* Stage Header */}
      <div
        className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
        style={{
          backgroundColor: "var(--bg-header)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="flex items-center gap-2">
          <FeatherIcon
            name="layers"
            size={14}
            style={{ color: "var(--color-primary)" }}
          />
          <h2 className="text-sm font-bold">{title}</h2>
          <span
            className="font-mono text-xs"
            style={{ color: "var(--text-tertiary)" }}
          >
            ({stageId})
          </span>
          {stageDef?.require_approval && (
            <span className="status-badge WAITING !text-[10px]">
              approval gate {gateState?.status === "APPROVED" ? "✓" : "⏳"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span
            className="text-xs font-mono"
            style={{ color: "var(--text-secondary)" }}
          >
            {completedNodes}/{totalNodes} completed
          </span>
          <span className={stageStatusClass}>{stageStatusText}</span>
        </div>
      </div>

      {/* Stage progress bar */}
      <div
        className="h-1 w-full overflow-hidden"
        style={{ backgroundColor: "var(--bg-panel-secondary)" }}
      >
        <div
          className="h-full transition-all duration-300"
          style={{
            width: `${percent}%`,
            backgroundColor: hasFailure
              ? "var(--color-status-failed)"
              : isComplete
              ? "var(--color-status-success)"
              : "var(--color-primary)",
          }}
        />
      </div>

      {/* Nodes list */}
      <div className="p-2 space-y-1">
        {nodes.map((node) => (
          <NodeRow
            key={node.id}
            nodeId={node.id}
            nodeState={node.state}
            spec={node.spec}
            nodeDiff={runDiff?.nodes?.[node.id]}
            isSelected={selectedNodeId === node.id}
            onSelect={onSelectNode}
          />
        ))}
      </div>

      {/* Approval Card if gate is waiting and run is active */}
      {runActive && gateState?.status === "WAITING" && (
        <div className="p-2 pt-0">
          <StageApprovalCard
            runId={runId}
            stageId={stageId}
            stageTitle={title}
            gateState={gateState}
            workflow={workflow}
            runInputs={runInputs}
            opsMap={opsMap}
            onApproved={onApproved}
          />
        </div>
      )}
    </div>
  );
}
