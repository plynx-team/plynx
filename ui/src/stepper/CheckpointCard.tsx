import { useState } from "react";
import { answerCheckpoint } from "../api/client";
import type { CheckpointState } from "../api/types.gen";
import { ControlButton } from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";

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
      className="rounded p-3.5 space-y-3"
      style={{
        backgroundColor: "var(--bg-panel)",
        border: "1px solid var(--border-strong)",
        borderLeft: "4px solid var(--color-warning)",
      }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-2 pb-2"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2">
          <FeatherIcon
            name="help-circle"
            size={15}
            style={{ color: "var(--color-warning)" }}
          />
          <h3 className="text-xs font-bold uppercase tracking-wide">
            User Input Required (Checkpoint)
          </h3>
        </div>
        <div
          className="flex items-center gap-2 font-mono text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          <span>node: {checkpoint.node_id}</span>
          <span>&bull;</span>
          <span>id: {checkpoint.checkpoint_id}</span>
        </div>
      </div>

      <p className="text-sm font-semibold">{checkpoint.question}</p>

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

      <div className="space-y-2.5 pt-1">
        {options.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {options.map((opt) => (
              <ControlButton
                key={opt}
                text={opt}
                variant="primary"
                disabled={submitting}
                onClick={() => void handleAnswer(opt)}
              />
            ))}
          </div>
        )}

        {checkpoint.allow_freeform && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleAnswer(freeformText);
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
              className="flex-1 h-8 px-2.5 text-xs"
            />
            <button
              type="submit"
              disabled={submitting || !freeformText.trim()}
              className="control-button primary"
            >
              <span className="control-button-text">
                {submitting ? "Submitting..." : "Submit Answer"}
              </span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
