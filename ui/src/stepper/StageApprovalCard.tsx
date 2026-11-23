import { useState } from "react";
import { approveStage } from "../api/client";
import type { OpEntry, StageGateState, Workflow } from "../api/types.gen";
import { ControlButton } from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";
import { PortInput } from "../components/PortInput";

interface InputValueState {
  value: unknown;
  rawText: string;
}

export interface MissingStageInput {
  nodeId: string;
  name: string;
  type: string;
  media?: string | null;
  options?: ReadonlyArray<string | number> | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  required: boolean;
  default?: unknown;
  description?: string | null;
}

export interface StageApprovalCardProps {
  runId: string;
  stageId: string;
  stageTitle?: string;
  gateState: StageGateState;
  workflow?: Workflow | null;
  runInputs?: Record<string, unknown>;
  opsMap?: Record<string, OpEntry>;
  onApproved?: (stageId: string) => void;
}

export function StageApprovalCard({
  runId,
  stageId,
  stageTitle,
  gateState,
  workflow,
  runInputs,
  opsMap,
  onApproved,
}: StageApprovalCardProps) {
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, InputValueState>>({});
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  if (gateState.status === "APPROVED") {
    return null;
  }

  // Detect missing required inputs for this stage
  const missingInputs: Array<MissingStageInput> = [];
  if (workflow?.nodes) {
    for (const [nodeId, node] of Object.entries(workflow.nodes)) {
      const nodeStage = node.stage || "main";
      if (nodeStage !== stageId) continue;
      const opEntry = opsMap?.[node.op];
      if (!opEntry) continue;

      for (const port of opEntry.inputs) {
        if (!port.required || port.default !== null) continue;
        // Check if bound in node.inputs
        if (node.inputs && port.name in node.inputs) continue;
        // Check if provided in runInputs
        const key = `${nodeId}.${port.name}`;
        if (runInputs && (key in runInputs || port.name in runInputs)) {
          const val = runInputs[key] ?? runInputs[port.name];
          if (val !== undefined && val !== null && val !== "") continue;
        }
        missingInputs.push({
          nodeId,
          name: port.name,
          type: port.type,
          media: port.media,
          options: port.options,
          min: port.min,
          max: port.max,
          step: port.step,
          required: port.required,
          default: port.default,
          description: port.description,
        });
      }
    }
  }

  const handlePortChange = (key: string, nextVal: unknown, nextRaw?: string) => {
    setFormValues((prev) => ({
      ...prev,
      [key]: {
        value: nextVal,
        rawText:
          nextRaw !== undefined
            ? nextRaw
            : nextVal === undefined || nextVal === null
              ? ""
              : typeof nextVal === "object"
                ? JSON.stringify(nextVal)
                : String(nextVal),
      },
    }));

    if (validationErrors[key]) {
      setValidationErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const handleApprove = async () => {
    try {
      setSubmitting(true);
      setError(null);

      let inputsPayload: Record<string, unknown> | undefined = undefined;
      if (missingInputs.length > 0) {
        const errors: Record<string, string> = {};
        const finalInputs: Record<string, unknown> = {};

        for (const input of missingInputs) {
          const key = `${input.nodeId}.${input.name}`;
          const state = formValues[key];
          const val = state ? state.value : undefined;

          if (input.type === "json") {
            const raw = state ? state.rawText.trim() : "";
            if (input.required && !raw) {
              errors[key] = `${input.name} is required`;
              continue;
            }
            if (raw) {
              try {
                finalInputs[key] = JSON.parse(raw);
              } catch {
                errors[key] = `Invalid JSON for ${input.name}`;
                continue;
              }
            }
          } else if (input.type === "bool") {
            const boolVal = typeof val === "boolean" ? val : Boolean(val);
            finalInputs[key] = boolVal;
          } else {
            if (input.required) {
              if (val === undefined || val === null || val === "") {
                errors[key] = `${input.name} is required`;
                continue;
              }
            }

            if (val !== undefined && val !== "") {
              finalInputs[key] = val;
            }
          }
        }

        if (Object.keys(errors).length > 0) {
          setValidationErrors(errors);
          setSubmitting(false);
          return;
        }

        inputsPayload = finalInputs;
      }

      if (inputsPayload && Object.keys(inputsPayload).length > 0) {
        await approveStage(runId, stageId, inputsPayload);
      } else {
        await approveStage(runId, stageId);
      }
      onApproved?.(stageId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const title = stageTitle || stageId;
  const hasMissingInputs = missingInputs.length > 0;

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
            name={hasMissingInputs ? "edit-3" : "check-circle"}
            size={15}
            style={{ color: "var(--color-primary)" }}
          />
          <h3 className="text-xs font-bold uppercase tracking-wide">
            {hasMissingInputs ? "Stage Inputs: Input Required" : "Stage Gate: Approval Required"}
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
        {hasMissingInputs ? (
          <>
            <p className="text-sm font-medium">
              Stage <span className="font-bold">&ldquo;{title}&rdquo;</span> requires inputs before running.
            </p>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              The previous stage has completed 100%. Please provide the required inputs below to continue execution.
            </p>
          </>
        ) : (
          <>
            <p className="text-sm font-medium">
              Stage <span className="font-bold">&ldquo;{title}&rdquo;</span> has finished execution.
            </p>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Downstream stages are paused until you review the results and approve continuation.
            </p>
          </>
        )}
      </div>

      {/* Render input fields if missing inputs exist */}
      {hasMissingInputs && (
        <div className="space-y-3 py-1">
          {missingInputs.map((spec) => {
            const key = `${spec.nodeId}.${spec.name}`;
            const state = formValues[key] || { value: "", rawText: "" };
            const hasError = !!validationErrors[key];

            return (
              <div key={key} className="space-y-1 rounded p-2" style={{ backgroundColor: "var(--bg-panel-secondary)" }}>
                <div className="flex items-center justify-between">
                  <label htmlFor={`stage-input-${key}`} className="text-xs font-semibold flex items-center gap-1">
                    <span>{spec.name}</span>
                    {spec.required && <span style={{ color: "var(--color-error)" }}>*</span>}
                  </label>
                  <div className="flex items-center gap-2 font-mono text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                    <span>node: {spec.nodeId}</span>
                    <span>&bull;</span>
                    <span>{spec.type}{spec.media ? ` (${spec.media})` : ""}</span>
                  </div>
                </div>

                <PortInput
                  id={`stage-input-${key}`}
                  port={spec}
                  value={state.value}
                  rawText={state.rawText}
                  onChange={(val, raw) => handlePortChange(key, val, raw)}
                  fileDropZone={true}
                  allowListEditor={false}
                  showPresets={false}
                />

                {hasError && (
                  <p className="text-[11px] font-medium" style={{ color: "var(--color-error)" }}>
                    {validationErrors[key]}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

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
          icon={hasMissingInputs ? "play" : "check"}
          text={
            submitting
              ? hasMissingInputs
                ? "Submitting Inputs..."
                : "Approving..."
              : hasMissingInputs
              ? "Submit Inputs & Continue"
              : "Approve & Continue"
          }
          variant="primary"
          disabled={submitting}
          onClick={() => void handleApprove()}
        />
      </div>
    </div>
  );
}
