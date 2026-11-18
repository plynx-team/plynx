import type { NodeProps } from "@xyflow/react";
import type { StageGroupGraphNode } from "./types";

export function StageGroupNode({ data }: NodeProps<StageGroupGraphNode>) {
  const gateStatus = data.gateState?.status;

  return (
    <div
      data-testid={`stage-group-${data.stageId}`}
      className="h-full w-full rounded-xl border border-dashed border-slate-700/80 bg-slate-900/35 pointer-events-none"
    >
      <div className="flex items-center justify-between border-b border-slate-800/70 bg-slate-900/70 px-3.5 py-2 rounded-t-xl">
        <div className="flex items-center gap-2 min-w-0">
          <span className="truncate text-xs font-bold tracking-wide text-slate-200">
            {data.title}
          </span>
          <span className="font-mono text-[10px] text-slate-500">
            ({data.stageId})
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {gateStatus === "WAITING" ? (
            <span className="rounded border border-amber-700 bg-amber-950/90 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
              WAITING APPROVAL
            </span>
          ) : gateStatus === "APPROVED" ? (
            <span className="rounded border border-emerald-800 bg-emerald-950/80 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
              APPROVED
            </span>
          ) : data.requireApproval ? (
            <span className="rounded border border-slate-700 bg-slate-800/80 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
              Gate
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
