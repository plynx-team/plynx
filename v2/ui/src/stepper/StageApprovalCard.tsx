import { useState } from "react";
import { approveStage } from "../api/client";
import type { StageGateState } from "../api/types.gen";

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

  // If already approved, disappear!
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
      className="rounded-lg border-2 border-indigo-600/80 bg-indigo-950/40 p-5 shadow-lg space-y-4 animate-in fade-in duration-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-900/60 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500 text-xs font-bold text-white">
            &check;
          </span>
          <h3 className="text-sm font-bold text-indigo-200">
            Stage Gate: Approval Required
          </h3>
        </div>
        <span className="font-mono text-xs text-indigo-400/80">
          stage: {stageId}
        </span>
      </div>

      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-100">
          Stage <span className="font-bold text-white">&ldquo;{title}&rdquo;</span> has finished execution.
        </p>
        <p className="text-xs text-slate-400">
          Downstream stages are paused until you review the results and approve continuation.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded border border-rose-800 bg-rose-950/80 p-2.5 text-xs text-rose-300"
        >
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          type="button"
          disabled={submitting}
          onClick={handleApprove}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          {submitting ? "Approving..." : "Approve & Continue"}
        </button>
      </div>
    </div>
  );
}
