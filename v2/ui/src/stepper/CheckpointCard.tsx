import { useState } from "react";
import { answerCheckpoint } from "../api/client";
import type { CheckpointState } from "../api/types.gen";

export interface CheckpointCardProps {
  runId: string;
  checkpoint: CheckpointState;
  onAnswered?: (nodeId: string, checkpointId: string, answer: string) => void;
}

export function CheckpointCard({
  runId,
  checkpoint,
  onAnswered,
}: CheckpointCardProps) {
  const [freeformText, setFreeformText] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // If already answered, disappear!
  if (checkpoint.answered_at !== null && checkpoint.answered_at !== undefined) {
    return null;
  }

  const handleAnswer = async (answer: string) => {
    if (!answer.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      await answerCheckpoint(
        runId,
        checkpoint.node_id,
        checkpoint.checkpoint_id,
        answer,
      );
      onAnswered?.(checkpoint.node_id, checkpoint.checkpoint_id, answer);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const options = checkpoint.options ?? [];

  return (
    <div
      data-testid={`checkpoint-card-${checkpoint.checkpoint_id}`}
      className="rounded-lg border-2 border-amber-600/80 bg-amber-950/40 p-5 shadow-lg space-y-4 animate-in fade-in duration-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-amber-900/60 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-xs font-bold text-slate-950">
            ?
          </span>
          <h3 className="text-sm font-bold text-amber-200">
            User Input Required (Checkpoint)
          </h3>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-amber-400/80">
          <span>node: {checkpoint.node_id}</span>
          <span>&bull;</span>
          <span>id: {checkpoint.checkpoint_id}</span>
        </div>
      </div>

      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-100">
          {checkpoint.question}
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

      <div className="space-y-3 pt-1">
        {/* Option buttons */}
        {options.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {options.map((opt) => (
              <button
                key={opt}
                type="button"
                disabled={submitting}
                onClick={() => handleAnswer(opt)}
                className="rounded-md border border-amber-600/60 bg-amber-900/60 px-4 py-2 text-xs font-semibold text-amber-100 shadow-sm hover:bg-amber-800 hover:border-amber-500 disabled:opacity-50 transition-colors"
              >
                {opt}
              </button>
            ))}
          </div>
        )}

        {/* Freeform input field */}
        {checkpoint.allow_freeform && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleAnswer(freeformText);
            }}
            className="flex flex-col gap-2 sm:flex-row sm:items-center"
          >
            <input
              type="text"
              aria-label="Freeform answer"
              placeholder="Type your answer..."
              value={freeformText}
              onChange={(e) => setFreeformText(e.target.value)}
              disabled={submitting}
              className="flex-1 rounded-md border border-amber-900/80 bg-slate-950/80 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:border-amber-600 focus:outline-none"
            />
            <button
              type="submit"
              disabled={submitting || !freeformText.trim()}
              className="rounded-md bg-amber-600 px-3.5 py-1.5 text-xs font-semibold text-slate-950 shadow-sm hover:bg-amber-500 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Submitting..." : "Submit Answer"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
