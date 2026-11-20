import { useState } from "react";
import { approveStage } from "../api/client";
import type { StageGateState } from "../api/types.gen";
import { ControlButton } from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";

export interface StageApprovalCardProps {
  runId: string;
  stageId: string;
  stageTitle?: string;
  gateState: StageGateState;
  onApproved?: (stageId: string) => void;
}

export function StageApprovalCard({
  runId,
  stageId,
  stageTitle,
  gateState,
  onApproved,
}: StageApprovalCardProps) {
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (gateState.status === "APPROVED") {
    return null;
  }

  const handleApprove = async () => {
    try {
      setSubmitting(true);
      setError(null);
      await approveStage(runId, stageId);
      onApproved?.(stageId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const title = stageTitle || stageId;

  return (
    <div
      data-testid={`stage-approval-card-${stageId}`}
      className="rounded p-3.5 space-y-3"
      style={{
        backgroundColor: "var(--bg-panel)",
        border: "1px solid var(--color-primary)",
        borderLeft: "4px solid var(--color-primary)",
      }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-2 pb-2"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2">
          <FeatherIcon
            name="check-circle"
            size={15}
            style={{ color: "var(--color-primary)" }}
          />
          <h3 className="text-xs font-bold uppercase tracking-wide">
            Stage Gate: Approval Required
          </h3>
        </div>
        <span
          className="font-mono text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          stage: {stageId}
        </span>
      </div>

      <div className="space-y-1">
        <p className="text-sm font-medium">
          Stage <span className="font-bold">&ldquo;{title}&rdquo;</span> has
          finished execution.
        </p>
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Downstream stages are paused until you review the results and approve
          continuation.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded p-2 text-xs"
          style={{
            border: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-1">
        <ControlButton
          icon="check"
          text={submitting ? "Approving..." : "Approve & Continue"}
          variant="primary"
          disabled={submitting}
          onClick={() => void handleApprove()}
        />
      </div>
    </div>
  );
}
