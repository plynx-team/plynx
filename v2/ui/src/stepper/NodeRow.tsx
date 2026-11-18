import type { NodeRunState, NodeSpec, NodeStatus } from "../api/types.gen";
import { formatDuration } from "../components/RunList";

export function nodeStatusBadgeClasses(status: NodeStatus): string {
  switch (status) {
    case "SUCCESS":
      return "bg-emerald-950 text-emerald-300 border-emerald-800";
    case "RUNNING":
      return "bg-sky-950 text-sky-300 border-sky-800 animate-pulse";
    case "BUILDING_ENVIRONMENT":
      return "bg-indigo-950 text-indigo-300 border-indigo-800 animate-pulse";
    case "WAITING_FOR_USER":
      return "bg-amber-950 text-amber-300 border-amber-800";
    case "FAILED":
      return "bg-rose-950 text-rose-300 border-rose-800";
    case "CANCELED":
      return "bg-slate-900 text-slate-400 border-slate-700";
    case "BLOCKED":
      return "bg-slate-900 text-slate-400 border-slate-700";
    case "PENDING":
      return "bg-slate-950 text-slate-500 border-slate-800";
  }
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
      className={`group flex flex-col gap-2 rounded-md border p-3 transition-colors cursor-pointer ${
        isSelected
          ? "border-emerald-600/70 bg-slate-900/90 shadow-sm"
          : "border-slate-800/80 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/50"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-xs font-bold text-slate-200">
            {nodeId}
          </span>
          {title !== nodeId && (
            <span className="text-xs text-slate-400 font-medium">
              &bull; {title}
            </span>
          )}
          {nodeState?.cache_hit && (
            <span
              data-testid="cache-hit-badge"
              className="inline-flex items-center rounded bg-teal-950 px-1.5 py-0.5 text-[10px] font-semibold text-teal-300 border border-teal-800"
            >
              cache hit
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {nodeState?.attempt && nodeState.attempt > 1 && (
            <span className="text-[11px] text-slate-500 font-mono">
              attempt {nodeState.attempt}
            </span>
          )}
          <span className="text-xs text-slate-400 font-mono">
            {formatDuration(nodeState?.started_at, nodeState?.finished_at)}
          </span>
          <span
            className={`rounded border px-2 py-0.5 text-xs font-medium tracking-wide ${nodeStatusBadgeClasses(
              status,
            )}`}
          >
            {status}
          </span>
        </div>
      </div>

      {op && (
        <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>op: {op}</span>
          {nodeState?.exit_code !== undefined && nodeState?.exit_code !== null && (
            <span>exit: {nodeState.exit_code}</span>
          )}
        </div>
      )}

      {nodeState?.error && (
        <div className="rounded border border-rose-900/70 bg-rose-950/40 p-2 text-xs text-rose-300 font-mono">
          {nodeState.error}
        </div>
      )}
    </div>
  );
}
