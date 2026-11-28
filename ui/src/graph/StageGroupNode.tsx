import type { NodeProps } from "@xyflow/react";
import { FeatherIcon } from "../components/FeatherIcon";
import { stageValidatorNodeId, type StageGroupGraphNode } from "./types";

function getValidatorDisplayStatus(data: StageGroupGraphNode["data"]): {
  label: string;
  badgeClass: string;
} {
  const st = data.validatorState?.status;
  if (data.validatorHasOpenPatch || st === "WAITING_FOR_USER") {
    return { label: "PATCH_PROPOSED", badgeClass: "status-badge WAITING" };
  }
  if (st === "SUCCESS") {
    return {
      label: data.validatorAppliedPatch ? "PATCHED" : "PASSED",
      badgeClass: "status-badge SUCCESS",
    };
  }
  if (st === "RUNNING" || st === "BUILDING_ENVIRONMENT") {
    return { label: "RUNNING", badgeClass: "status-badge RUNNING" };
  }
  if (st === "FAILED") {
    return { label: "FAILED", badgeClass: "status-badge FAILED" };
  }
  if (st === "PENDING") {
    return { label: "PENDING", badgeClass: "status-badge PENDING" };
  }
  return {
    label: data.validator?.mode || "on_anomaly",
    badgeClass: "status-badge CREATED",
  };
}

export function StageGroupNode({ data }: NodeProps<StageGroupGraphNode>) {
  const gateStatus = data.gateState?.status;
  const isSelected = Boolean(data.isSelected);
  const isDropTarget = Boolean(data.isDropTarget);
  const isEmpty = data.nodeCount === 0;
  const validatorStatus = getValidatorDisplayStatus(data);

  return (
    <div
      data-testid={`stage-group-${data.stageId}`}
      data-is-drop-target={isDropTarget ? "true" : undefined}
      className={`h-full w-full rounded-lg pointer-events-none relative transition-all duration-150 ${
        isDropTarget ? "is-drop-target ring-2 ring-[var(--color-primary)] ring-opacity-50" : ""
      }`}
      style={{
        border: isDropTarget
          ? "2px solid var(--color-primary)"
          : isSelected
          ? "2px solid var(--color-primary)"
          : "1px dashed #3c3c3c",
        backgroundColor: isDropTarget
          ? "rgba(38, 128, 235, 0.16)"
          : isSelected
          ? "rgba(38, 128, 235, 0.08)"
          : "rgba(38, 38, 38, 0.28)",
        boxShadow: isDropTarget
          ? "0 0 20px rgba(38, 128, 235, 0.35), inset 0 0 16px rgba(38, 128, 235, 0.12)"
          : undefined,
      }}
    >
      {/* Top drag area / header bar: gives a generous draggable zone across the top of the stage */}
      {!isEmpty && (
        <div
          data-testid={`stage-drag-area-${data.stageId}`}
          className="stage-drag-handle pointer-events-auto absolute top-0 left-0 right-0 h-9 rounded-t-lg cursor-grab active:cursor-grabbing"
          title="Drag stage to move with subnodes"
        />
      )}

      {/* Windowless Stage Title: compact interactive textbox pinned in top-left corner */}
      <div className="absolute top-2.5 left-3 flex items-center gap-2 max-w-[calc(100%-24px)] select-none z-10">
        <div
          role="button"
          tabIndex={0}
          data-testid={`stage-badge-${data.stageId}`}
          onClick={(e) => {
            e.stopPropagation();
            data.onSelectStage?.(data.stageId);
          }}
          className={`pointer-events-auto flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#2a2a2a] text-xs shadow-sm transition-colors ${
            !isEmpty
              ? "stage-drag-handle cursor-grab active:cursor-grabbing"
              : "cursor-pointer"
          } ${
            isDropTarget || isSelected
              ? "border border-[var(--color-primary)] text-[var(--color-primary)]"
              : "border border-[#3c3c3c] hover:border-[var(--color-primary)]"
          }`}
          title={
            isEmpty
              ? "Click to inspect and edit stage properties"
              : "Drag to move stage with subnodes. Click to inspect."
          }
        >
          <FeatherIcon
            name="layers"
            size={11}
            style={{
              color:
                isDropTarget || isSelected
                  ? "var(--color-primary)"
                  : "var(--text-secondary)",
            }}
          />
          <span
            className="truncate font-semibold text-xs"
            style={{
              color:
                isDropTarget || isSelected
                  ? "var(--color-primary)"
                  : "var(--text-primary)",
            }}
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

        {isEmpty && data.onDeleteStage && (
          <button
            type="button"
            aria-label={`Delete empty stage ${data.stageId}`}
            data-testid={`btn-delete-empty-stage-${data.stageId}`}
            onClick={(e) => {
              e.stopPropagation();
              data.onDeleteStage?.(data.stageId);
            }}
            title="Delete empty stage"
            className="pointer-events-auto p-1 rounded hover:bg-[#3c3c3c] text-[var(--text-tertiary)] hover:text-[var(--color-error)] transition-colors"
          >
            <FeatherIcon name="trash-2" size={11} />
          </button>
        )}
      </div>

      {isEmpty && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center pointer-events-none">
          <span
            className="text-xs italic"
            style={{ color: "var(--text-tertiary)" }}
          >
            Empty stage: add operations or select this stage in the palette
          </span>
        </div>
      )}

      {/* Stage Validator Pill / Footer Bar */}
      {data.validator && (
        <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between pointer-events-none z-10">
          <div
            role="button"
            tabIndex={0}
            data-testid={`stage-validator-pill-${data.stageId}`}
            onClick={(e) => {
              e.stopPropagation();
              const valId = stageValidatorNodeId(data.stageId);
              if (data.onSelectValidator) {
                data.onSelectValidator(data.stageId, valId);
              } else {
                data.onSelectStage?.(data.stageId);
              }
            }}
            className={`pointer-events-auto flex items-center justify-between gap-2 w-full px-2.5 py-1 rounded bg-[#252525]/95 text-xs shadow-sm cursor-pointer transition-colors ${
              data.isValidatorSelected
                ? "border border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]"
                : "border border-[#3e3e3e] hover:border-[var(--color-primary)]"
            } ${validatorStatus.label === "RUNNING" ? "stage-validator-running" : ""}`}
            title={`Stage Validator: ${data.validatorTitle || data.validator.op} (${data.validator.mode || "on_anomaly"})`}
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <FeatherIcon
                name="shield"
                size={11}
                style={{ color: "var(--color-primary)" }}
              />
              <span className="truncate font-semibold text-[11px]">
                {data.validatorTitle || data.validator.op}
              </span>
              <span
                className="font-mono text-[10px] px-1 rounded bg-black/30 shrink-0"
                style={{ color: "var(--text-secondary)" }}
              >
                {data.validator.mode || "on_anomaly"}
              </span>
            </div>
            <span
              data-testid={`stage-validator-status-${data.stageId}`}
              className={`${validatorStatus.badgeClass} !text-[9px] shrink-0`}
            >
              {validatorStatus.label}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
