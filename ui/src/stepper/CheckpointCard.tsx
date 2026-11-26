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

  const resolved = questions.map((q) => resolveAnswer(q, drafts[q.id]));
  const complete = resolved.every((value) => value !== null);

  const updateDraft = (id: string, patch: Partial<DraftAnswer>) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...(prev[id] ?? { selected: [], freeform: "" }), ...patch },
    }));
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
