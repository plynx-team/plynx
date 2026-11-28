import type {
  CheckpointState,
  NodeRunState,
  NodeSpec,
  OpEntry,
  Stage,
  StageGateState,
  Workflow,
} from "../api/types.gen";
import type { WorkflowRunDiff } from "../graph/runDiff";
import { stageValidatorNodeId } from "../graph/types";
import { FeatherIcon } from "../components/FeatherIcon";
import { formatDuration } from "../components/RunList";
import { CheckpointCard } from "./CheckpointCard";
import { NodeRow } from "./NodeRow";
import { StageApprovalCard } from "./StageApprovalCard";

export interface StageCardProps {
  runId: string;
  stageId: string;
  stageDef?: Stage;
  gateState?: StageGateState;
  validatorState?: NodeRunState;
  validatorCheckpoints?: ReadonlyArray<CheckpointState>;
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
  onCheckpointAnswered?: () => void;
}

export function StageCard({
  runId,
  stageId,
  stageDef,
  gateState,
  validatorState,
  validatorCheckpoints = [],
  runActive = true,
  runDiff = null,
  nodes,
  selectedNodeId,
  onSelectNode,
  workflow,
  runInputs,
  opsMap,
  onApproved,
  onCheckpointAnswered,
}: StageCardProps) {
  const title =
    stageDef?.title || (stageId !== "default" ? stageId : "Workflow Stage");
  const validatorSpec = stageDef?.validator ?? null;
  const validatorNodeId = stageValidatorNodeId(stageId);
  const openValidatorCheckpoints = validatorCheckpoints.filter(
    (cp) => !cp.answered_at,
  );
  const isValidatorRunning =
    openValidatorCheckpoints.length === 0 &&
    (validatorState?.status === "RUNNING" ||
      validatorState?.status === "BUILDING_ENVIRONMENT");
  const totalNodes = nodes.length;
  const completedNodes = nodes.filter(
    (n) => n.state?.status === "SUCCESS",
  ).length;
  const hasFailure =
    nodes.some((n) => n.state?.status === "FAILED" && !n.spec?.meta?.superseded_by) ||
    validatorState?.status === "FAILED";
  const isRunning =
    nodes.some(
      (n) =>
        n.state?.status === "RUNNING" ||
        n.state?.status === "BUILDING_ENVIRONMENT",
    ) ||
    isValidatorRunning;
  const isWaiting =
    gateState?.status === "WAITING" ||
    validatorState?.status === "WAITING_FOR_USER" ||
    openValidatorCheckpoints.length > 0 ||
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
            opEntry={node.spec ? opsMap?.[node.spec.op] : undefined}
            nodeDiff={runDiff?.nodes?.[node.id]}
            isSelected={selectedNodeId === node.id}
            onSelect={onSelectNode}
          />
        ))}
      </div>

      {/* Stage Validator Row */}
      {validatorSpec && (
        <div
          className="px-2 pb-2"
          style={{ borderTop: "1px dashed var(--border-subtle)" }}
        >
          <div
            role="button"
            tabIndex={0}
            data-testid={`stage-validator-row-${stageId}`}
            onClick={() => onSelectNode?.(validatorNodeId)}
            className={`mt-2 list-row !block cursor-pointer ${
              selectedNodeId === validatorNodeId ? "selected" : ""
            } ${isValidatorRunning ? "stage-validator-running" : ""}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FeatherIcon
                  name="shield"
                  size={13}
                  style={{ color: "var(--color-primary)" }}
                />
                <span className="text-xs font-bold">
                  Stage Validator:{" "}
                  {opsMap?.[validatorSpec.op]?.title || validatorSpec.op}
                </span>
                <span
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/30"
                  style={{ color: "var(--text-secondary)" }}
                >
                  mode: {validatorSpec.mode || "on_anomaly"}
                </span>
                <span
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-black/30"
                  style={{ color: "var(--text-secondary)" }}
                >
                  edits: {validatorSpec.allow_graph_edits || "confirm"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {validatorState && (
                  <span
                    className="text-xs font-mono"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {formatDuration(
                      validatorState.started_at,
                      validatorState.finished_at,
                    )}
                  </span>
                )}
                <span
                  data-testid={`stage-validator-row-status-${stageId}`}
                  className={`status-badge ${
                    openValidatorCheckpoints.length > 0 ||
                    validatorState?.status === "WAITING_FOR_USER"
                      ? "WAITING"
                      : validatorState?.status || "CREATED"
                  }`}
                >
                  {openValidatorCheckpoints.length > 0 ||
                  validatorState?.status === "WAITING_FOR_USER"
                    ? "PATCH_PROPOSED"
                    : validatorState?.status === "SUCCESS"
                      ? "PASSED"
                      : validatorState?.status || "DRAFT"}
                </span>
              </div>
            </div>
            {validatorState?.error && (
              <div
                className="mt-1.5 rounded p-2 text-xs font-mono"
                style={{
                  border: "1px solid var(--color-error)",
                  backgroundColor: "rgba(244, 67, 54, 0.15)",
                  color: "#ff8a80",
                }}
              >
                {validatorState.error}
              </div>
            )}
          </div>

          {runActive &&
            openValidatorCheckpoints.map((cp) => (
              <div key={cp.checkpoint_id} className="mt-2">
                <CheckpointCard
                  runId={runId}
                  checkpoint={cp}
                  onAnswered={() => onCheckpointAnswered?.()}
                />
              </div>
            ))}
        </div>
      )}

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
