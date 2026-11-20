import type { NodeProps } from "@xyflow/react";
import { FeatherIcon } from "../components/FeatherIcon";
import type { StageGroupGraphNode } from "./types";

export function StageGroupNode({ data }: NodeProps<StageGroupGraphNode>) {
  const gateStatus = data.gateState?.status;

  return (
    <div
      data-testid={`stage-group-${data.stageId}`}
      className="h-full w-full rounded-lg pointer-events-none relative"
      style={{
        border: "1px dashed #3c3c3c",
        backgroundColor: "rgba(38, 38, 38, 0.28)",
      }}
    >
      {/* Windowless Stage Title: compact textbox pinned in top-left corner */}
      <div className="absolute top-2.5 left-3 flex items-center gap-2 max-w-[calc(100%-24px)] pointer-events-none select-none">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#2a2a2a] border border-[#3c3c3c] text-xs shadow-sm">
          <FeatherIcon
            name="layers"
            size={11}
            style={{ color: "var(--text-secondary)" }}
          />
          <span
            className="truncate font-semibold text-xs"
            style={{ color: "var(--text-primary)" }}
          >
            {data.title}
          </span>
          <span
            className="font-mono text-[10px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            ({data.stageId})
          </span>
        </div>

        {gateStatus === "WAITING" ? (
          <span className="status-badge WAITING text-[10px] px-1.5 py-0.5 rounded bg-[#2a2a2a] border border-[#3c3c3c]">
            WAITING APPROVAL
          </span>
        ) : gateStatus === "APPROVED" ? (
          <span className="status-badge APPROVED text-[10px] px-1.5 py-0.5 rounded bg-[#2a2a2a] border border-[#3c3c3c]">
            APPROVED
          </span>
        ) : data.requireApproval ? (
          <span className="status-badge CREATED text-[10px] px-1.5 py-0.5 rounded bg-[#2a2a2a] border border-[#3c3c3c]">
            Gate
          </span>
        ) : null}
      </div>
    </div>
  );
}
