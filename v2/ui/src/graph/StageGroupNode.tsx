import type { NodeProps } from "@xyflow/react";
import { FeatherIcon } from "../components/FeatherIcon";
import type { StageGroupGraphNode } from "./types";

export function StageGroupNode({ data }: NodeProps<StageGroupGraphNode>) {
  const gateStatus = data.gateState?.status;

  return (
    <div
      data-testid={`stage-group-${data.stageId}`}
      className="h-full w-full rounded-lg pointer-events-none"
      style={{
        border: "1px dashed #3c3c3c",
        backgroundColor: "rgba(38, 38, 38, 0.28)",
      }}
    >
      <div
        className="flex items-center justify-between px-3 py-1.5 rounded-t-lg"
        style={{
          borderBottom: "1px solid #363636",
          backgroundColor: "rgba(38, 38, 38, 0.75)",
        }}
      >
        <div className="flex items-center gap-1.5 min-w-0">
          <FeatherIcon
            name="layers"
            size={12}
            style={{ color: "var(--text-secondary)" }}
          />
          <span
            className="truncate text-xs font-semibold"
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

        <div className="flex items-center gap-1.5 shrink-0">
          {gateStatus === "WAITING" ? (
            <span className="status-badge WAITING text-[10px]">
              WAITING APPROVAL
            </span>
          ) : gateStatus === "APPROVED" ? (
            <span className="status-badge APPROVED text-[10px]">APPROVED</span>
          ) : data.requireApproval ? (
            <span className="status-badge CREATED text-[10px]">Gate</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
