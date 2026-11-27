import { useState } from "react";
import { answerCheckpoint } from "../api/client";
import type {
  CheckpointQuestionState,
  CheckpointState,
} from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";

export type CheckpointAnswers = Record<string, string | string[]>;

export interface CheckpointCardProps {
  runId: string;
  checkpoint: CheckpointState;
  onAnswered?: (
    nodeId: string,
    checkpointId: string,
    answer: string | CheckpointAnswers,
  ) => void;
}

const SINGLE_QUESTION_ID = "default";

interface DraftAnswer {
  /** Selected option(s). One item for single-select. */
  selected: string[];
  /** Freeform ("Other") text, or the whole answer when the question has no options. */
  freeform: string;
}

/** Questions of a checkpoint; rows without ``questions`` fall back to one ``default`` question. */
export function checkpointQuestions(
  checkpoint: CheckpointState,
): CheckpointQuestionState[] {
  if (checkpoint.questions && checkpoint.questions.length > 0) {
    return checkpoint.questions;
  }
  return [
    {
      id: SINGLE_QUESTION_ID,
      question: checkpoint.question,
      header: "",
      options: checkpoint.options ?? [],
      multi_select: false,
      allow_freeform: checkpoint.allow_freeform,
    },
  ];
}

function isBatch(questions: CheckpointQuestionState[]): boolean {
  return !(questions.length === 1 && questions[0].id === SINGLE_QUESTION_ID);
}

function resolveAnswer(
  q: CheckpointQuestionState,
  draft: DraftAnswer | undefined,
): string | string[] | null {
  const freeform = draft?.freeform.trim() ?? "";
  const selected = draft?.selected ?? [];
  if (q.multi_select) {
    const values = [...selected, ...(freeform ? [freeform] : [])];
    return values.length > 0 ? values : null;
  }
  if (freeform) return freeform;
  return selected[0] ?? null;
}

export function CheckpointCard({
  runId,
  checkpoint,
  onAnswered,
}: CheckpointCardProps) {
  const [drafts, setDrafts] = useState<Record<string, DraftAnswer>>({});
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (checkpoint.answered_at !== null && checkpoint.answered_at !== undefined) {
    return null;
  }

  const questions = checkpointQuestions(checkpoint);
  const batch = isBatch(questions);
  const graphPatch = checkpoint.graph_patch;

  const resolved = questions.map((q) => resolveAnswer(q, drafts[q.id]));
  const complete = resolved.every((value) => value !== null);

  const updateDraft = (id: string, patch: Partial<DraftAnswer>) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...(prev[id] ?? { selected: [], freeform: "" }), ...patch },
    }));
  };

  const handlePatchDecision = async (decision: "Approve Patch" | "Reject") => {
    if (submitting) return;
    try {
      setSubmitting(true);
      setError(null);
      await answerCheckpoint(
        runId,
        checkpoint.node_id,
        checkpoint.checkpoint_id,
        decision,
      );
      onAnswered?.(checkpoint.node_id, checkpoint.checkpoint_id, decision);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const handleSubmit = async () => {
    if (!complete || submitting) return;
    const answers: CheckpointAnswers = {};
    questions.forEach((q, idx) => {
      answers[q.id] = resolved[idx] as string | string[];
    });
    const payload: string | CheckpointAnswers = batch
      ? answers
      : (answers[SINGLE_QUESTION_ID] as string);
    try {
      setSubmitting(true);
      setError(null);
      await answerCheckpoint(
        runId,
        checkpoint.node_id,
        checkpoint.checkpoint_id,
        payload,
      );
      onAnswered?.(checkpoint.node_id, checkpoint.checkpoint_id, payload);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const testId = `checkpoint-card-${checkpoint.checkpoint_id}`;

  if (graphPatch) {
    const addedEntries = Object.entries(graphPatch.add_nodes ?? {});
    const rewireEntries = Object.entries(graphPatch.rewire_inputs ?? {});

    return (
      <div
        data-testid={testId}
        className="rounded p-3.5 space-y-3"
        style={{
          backgroundColor: "var(--bg-panel)",
          border: "1px solid var(--border-strong)",
          borderLeft: "4px solid var(--color-primary)",
        }}
      >
        <div
          className="flex flex-wrap items-center justify-between gap-2 pb-2"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div className="flex items-center gap-2">
            <FeatherIcon
              name="git-pull-request"
              size={15}
              style={{ color: "var(--color-primary)" }}
            />
            <h3 className="text-xs font-bold uppercase tracking-wide">
              Proposed Graph Patch (Confirm)
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

        <div className="space-y-1">
          <div
            className="text-[11px] font-bold uppercase tracking-wide"
            style={{ color: "var(--text-secondary)" }}
          >
            Reason
          </div>
          <p className="text-xs">{graphPatch.reason}</p>
        </div>

        <div
          data-testid={`patch-diff-preview-${checkpoint.checkpoint_id}`}
          className="rounded p-2.5 space-y-2 font-mono text-xs"
          style={{
            backgroundColor: "var(--bg-canvas)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          {addedEntries.length > 0 && (
            <div className="space-y-1">
              <div style={{ color: "var(--color-status-success)" }}>
                + Add Nodes ({addedEntries.length})
              </div>
              {addedEntries.map(([nid, spec]) => (
                <div
                  key={nid}
                  className="pl-2 py-0.5 rounded"
                  style={{ backgroundColor: "rgba(56, 193, 114, 0.1)" }}
                >
                  <span className="font-bold">+ {nid}</span>:{" "}
                  <span>{String(spec.op ?? "")}</span>
                  {spec.inputs ? (
                    <span style={{ color: "var(--text-secondary)" }}>
                      {" "}
                      {JSON.stringify(spec.inputs)}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          )}

          {rewireEntries.length > 0 && (
            <div className="space-y-1">
              <div style={{ color: "var(--color-warning)" }}>
                ~ Rewire Inputs
              </div>
              {rewireEntries.map(([targetNid, ports]) =>
                Object.entries(ports).map(([portName, newVal]) => (
                  <div
                    key={`${targetNid}.${portName}`}
                    className="pl-2 py-0.5 rounded"
                    style={{ backgroundColor: "rgba(255, 167, 38, 0.1)" }}
                  >
                    <span className="font-bold">
                      ~ {targetNid}.{portName}
                    </span>{" "}
                    &larr;{" "}
                    <span>
                      {typeof newVal === "string"
                        ? newVal
                        : JSON.stringify(newVal)}
                    </span>
                  </div>
                )),
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            data-testid={`btn-approve-patch-${checkpoint.checkpoint_id}`}
            disabled={submitting}
            onClick={() => void handlePatchDecision("Approve Patch")}
            className="control-button primary"
          >
            <FeatherIcon name="check" size={13} />
            <span className="control-button-text">
              {submitting ? "Applying..." : "Approve Patch"}
            </span>
          </button>
          <button
            type="button"
            data-testid={`btn-reject-patch-${checkpoint.checkpoint_id}`}
            disabled={submitting}
            onClick={() => void handlePatchDecision("Reject")}
            className="control-button danger"
          >
            <FeatherIcon name="x" size={13} />
            <span className="control-button-text">Reject</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <form
      data-testid={testId}
      className="rounded p-3.5 space-y-3"
      style={{
        backgroundColor: "var(--bg-panel)",
        border: "1px solid var(--border-strong)",
        borderLeft: "4px solid var(--color-warning)",
      }}
      onSubmit={(e) => {
        e.preventDefault();
        void handleSubmit();
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

      {questions.map((q) => {
        const draft = drafts[q.id];
        const groupName = `${checkpoint.checkpoint_id}-${q.id}`;
        const hasOptions = q.options.length > 0;
        return (
          <fieldset
            key={q.id}
            data-testid={`checkpoint-question-${q.id}`}
            className="space-y-2"
            disabled={submitting}
          >
            {q.header && (
              <legend className="text-xs font-bold uppercase tracking-wide">
                {q.header}
              </legend>
            )}
            <p className="text-sm font-semibold">{q.question}</p>

            {hasOptions &&
              q.options.map((opt) => (
                <label
                  key={opt}
                  className="flex items-center gap-2 text-xs cursor-pointer"
                >
                  <input
                    type={q.multi_select ? "checkbox" : "radio"}
                    name={groupName}
                    value={opt}
                    checked={draft?.selected.includes(opt) ?? false}
                    onChange={(e) => {
                      const prev = draft?.selected ?? [];
                      if (q.multi_select) {
                        updateDraft(q.id, {
                          selected: e.target.checked
                            ? [...prev, opt]
                            : prev.filter((item) => item !== opt),
                        });
                      } else {
                        updateDraft(q.id, { selected: [opt], freeform: "" });
                      }
                    }}
                  />
                  <span>{opt}</span>
                </label>
              ))}

            {(!hasOptions || q.allow_freeform) && (
              <input
                type="text"
                aria-label={
                  hasOptions ? `Other answer for ${q.id}` : `Answer for ${q.id}`
                }
                placeholder={hasOptions ? "Other..." : "Type your answer..."}
                value={draft?.freeform ?? ""}
                onChange={(e) =>
                  updateDraft(q.id, {
                    freeform: e.target.value,
                    ...(hasOptions && !q.multi_select && e.target.value
                      ? { selected: [] }
                      : {}),
                  })
                }
                className="w-full h-8 px-2.5 text-xs"
              />
            )}
          </fieldset>
        );
      })}

      <button
        type="submit"
        disabled={submitting || !complete}
        className="control-button primary"
      >
        <span className="control-button-text">
          {submitting ? "Submitting..." : "Submit Answers"}
        </span>
      </button>
    </form>
  );
}
