import type { NodeRunState, NodeSpec, NodeStatus } from "../api/types.gen";
import type { NodeDiff } from "../graph/runDiff";
import { FeatherIcon } from "../components/FeatherIcon";
import { formatDuration } from "../components/RunList";
import { getCacheHint, getStatusHint } from "../graph/types";

export function nodeStatusBadgeClasses(status: NodeStatus): string {
  return `status-badge ${status}`;
}

export interface NodeRowProps {
  nodeId: string;
  nodeState?: NodeRunState;
  spec?: NodeSpec;
  nodeDiff?: NodeDiff;
  isSelected?: boolean;
  onSelect?: (nodeId: string) => void;
}

export function NodeRow({
  nodeId,
  nodeState,
  spec,
  nodeDiff,
  isSelected = false,
  onSelect,
}: NodeRowProps) {
  const isNotInRun = nodeDiff ? nodeDiff.status === "not_in_run" : !nodeState;
  const isNewInRun = nodeDiff ? nodeDiff.status === "new_in_run" : !spec;
  const status = nodeState?.status;
  const title = spec?.title || spec?.op || nodeId;
  const op = spec?.op;

  return (
    <div
      onClick={() => onSelect?.(nodeId)}
      className={`list-row !block ${isSelected ? "selected" : ""} ${
        isNotInRun ? "opacity-60" : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FeatherIcon
            name={isNotInRun ? "slash" : "cpu"}
            size={13}
            style={{
              color: isNotInRun
                ? "var(--color-status-failed)"
                : "var(--color-primary)",
            }}
          />
          <span
            className={`font-mono text-xs font-bold ${
              isNotInRun ? "line-through text-neutral-400" : ""
            }`}
          >
            {nodeId}
          </span>
          {title !== nodeId && (
            <span
              className={`text-xs font-medium ${
                isNotInRun ? "line-through" : ""
              }`}
              style={{ color: "var(--text-secondary)" }}
            >
              &bull; {title}
            </span>
          )}
          {isNewInRun && (
            <span className="status-badge !border-[#00d8ff] !text-[#00d8ff] !text-[10px] !px-1.5 !py-0">
              NEW
            </span>
          )}
          {nodeState?.cache_hit && (
            <span
              data-testid="cache-hit-badge"
              className="status-badge READY !text-[10px] !px-1.5 !py-0 cursor-help"
              title={getCacheHint(nodeState)}
            >
              cache hit
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {nodeState?.attempt && nodeState.attempt > 1 && (
            <span
              className="text-[11px] font-mono"
              style={{ color: "var(--text-tertiary)" }}
            >
              attempt {nodeState.attempt}
            </span>
          )}
          <span
            className="text-xs font-mono"
            style={{ color: "var(--text-secondary)" }}
          >
            {formatDuration(nodeState?.started_at, nodeState?.finished_at)}
          </span>
          {isNotInRun ? (
            <span
              className="status-badge NOT_IN_RUN cursor-help"
              title={getStatusHint(status, true, nodeState?.error)}
            >
              NOT IN RUN
            </span>
          ) : (
            <span
              className={`${nodeStatusBadgeClasses(status ?? "PENDING")} cursor-help`}
              title={getStatusHint(status, false, nodeState?.error)}
            >
              {status ?? "PENDING"}
            </span>
          )}
        </div>
      </div>

      {op && (
        <div
          className="mt-1 flex items-center justify-between text-[11px] font-mono"
          style={{ color: "var(--text-tertiary)" }}
        >
          <span>op: {op}</span>
          {nodeState?.exit_code !== undefined &&
            nodeState?.exit_code !== null && (
              <span>exit: {nodeState.exit_code}</span>
            )}
        </div>
      )}

      {nodeState?.error && (
        <div
          className="mt-1.5 rounded p-2 text-xs font-mono"
          style={{
            border: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {nodeState.error}
        </div>
      )}
    </div>
  );
}
