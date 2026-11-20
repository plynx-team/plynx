import type { NodeRunState, NodeSpec, NodeStatus } from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";
import { formatDuration } from "../components/RunList";

export function nodeStatusBadgeClasses(status: NodeStatus): string {
  return `status-badge ${status}`;
}

export interface NodeRowProps {
  nodeId: string;
  nodeState?: NodeRunState;
  spec?: NodeSpec;
  isSelected?: boolean;
  onSelect?: (nodeId: string) => void;
}

export function NodeRow({
  nodeId,
  nodeState,
  spec,
  isSelected = false,
  onSelect,
}: NodeRowProps) {
  const status: NodeStatus = nodeState?.status ?? "PENDING";
  const title = spec?.title || spec?.op || nodeId;
  const op = spec?.op;

  return (
    <div
      onClick={() => onSelect?.(nodeId)}
      className={`list-item !block ${isSelected ? "selected" : ""}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FeatherIcon
            name="cpu"
            size={13}
            style={{ color: "var(--color-primary)" }}
          />
          <span className="font-mono text-xs font-bold">{nodeId}</span>
          {title !== nodeId && (
            <span
              className="text-xs font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              &bull; {title}
            </span>
          )}
          {nodeState?.cache_hit && (
            <span
              data-testid="cache-hit-badge"
              className="status-badge READY !text-[10px] !px-1.5 !py-0"
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
          <span className={nodeStatusBadgeClasses(status)}>{status}</span>
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
