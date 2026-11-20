import { useState } from "react";
import { approveStage, uploadFile } from "../api/client";
import type { OpEntry, StageGateState, Workflow } from "../api/types.gen";
import { ControlButton } from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";

interface InputValueState {
  value: unknown;
  rawText: string;
  isUploading?: boolean;
  uploadedPath?: string;
  uploadFileName?: string;
}

export interface MissingStageInput {
  nodeId: string;
  name: string;
  type: string;
  media?: string | null;
  required: boolean;
  default?: unknown;
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
          required: port.required,
          default: port.default,
        });
      }
    }
  }

  const handleScalarChange = (key: string, rawVal: string, type: string) => {
    let parsedVal: unknown = rawVal;
    if (type === "int") {
      const num = parseInt(rawVal, 10);
      parsedVal = isNaN(num) ? "" : num;
    } else if (type === "float") {
      const num = parseFloat(rawVal);
      parsedVal = isNaN(num) ? "" : num;
    } else if (type === "json") {
      try {
        parsedVal = JSON.parse(rawVal);
      } catch {
        parsedVal = rawVal;
      }
    }

    setFormValues((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        value: parsedVal,
        rawText: rawVal,
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

  const handleBoolChange = (key: string, checked: boolean) => {
    setFormValues((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        value: checked,
        rawText: String(checked),
      },
    }));
  };

  const handleFileUpload = async (key: string, file: File) => {
    setFormValues((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        isUploading: true,
        uploadFileName: file.name,
      },
    }));

    try {
      const res = await uploadFile(file);
      setFormValues((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          isUploading: false,
          value: res.path,
          rawText: res.path,
          uploadedPath: res.path,
        },
      }));
      if (validationErrors[key]) {
        setValidationErrors((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    } catch (err: unknown) {
      setFormValues((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          isUploading: false,
        },
      }));
      setValidationErrors((prev) => ({
        ...prev,
        [key]: `Upload failed: ${err instanceof Error ? err.message : String(err)}`,
      }));
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

          if (input.required) {
            if (
              val === undefined ||
              val === null ||
              val === "" ||
              (input.type === "json" && (!state || state.rawText.trim() === ""))
            ) {
              errors[key] = `${input.name} is required`;
              continue;
            }
          }

          if (val !== undefined && val !== "") {
            finalInputs[key] = val;
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

                {spec.type === "file" || spec.type === "directory" ? (
                  <div className="space-y-1.5">
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const files = e.dataTransfer.files;
                        if (files.length > 0) {
                          void handleFileUpload(key, files[0]);
                        }
                      }}
                      className="flex flex-col items-center justify-center rounded border border-dashed p-3 text-center cursor-pointer"
                      style={{
                        borderColor: "var(--border-strong)",
                        backgroundColor: "var(--bg-panel)",
                      }}
                      onClick={() => {
                        const el = document.getElementById(`stage-file-upload-${key}`) as HTMLInputElement | null;
                        el?.click();
                      }}
                    >
                      <input
                        id={`stage-file-upload-${key}`}
                        type="file"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files && e.target.files.length > 0) {
                            void handleFileUpload(key, e.target.files[0]);
                          }
                        }}
                      />
                      {state.isUploading ? (
                        <span className="text-xs" style={{ color: "var(--color-info)" }}>
                          Uploading {state.uploadFileName}...
                        </span>
                      ) : state.uploadedPath ? (
                        <div className="text-xs flex items-center gap-1.5" style={{ color: "var(--color-success)" }}>
                          <span>&check;</span>
                          <span>Uploaded: {state.uploadFileName} ({state.uploadedPath})</span>
                        </div>
                      ) : (
                        <p className="text-xs font-medium">Drop {spec.type} here, or click to browse</p>
                      )}
                    </div>
                    <input
                      id={`stage-input-${key}`}
                      type="text"
                      placeholder="Or enter path / upload path manually..."
                      value={state.rawText}
                      onChange={(e) => handleScalarChange(key, e.target.value, "str")}
                      className="w-full px-2 py-1 text-xs font-mono"
                    />
                  </div>
                ) : spec.type === "bool" ? (
                  <div className="flex items-center gap-2 pt-0.5">
                    <input
                      id={`stage-input-${key}`}
                      type="checkbox"
                      checked={Boolean(state.value)}
                      onChange={(e) => handleBoolChange(key, e.target.checked)}
                      className="h-3.5 w-3.5"
                    />
                    <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                      Enable
                    </span>
                  </div>
                ) : spec.type === "json" ? (
                  <textarea
                    id={`stage-input-${key}`}
                    rows={3}
                    placeholder="Enter JSON object or array..."
                    value={state.rawText}
                    onChange={(e) => handleScalarChange(key, e.target.value, "json")}
                    className="w-full p-2 font-mono text-xs"
                  />
                ) : (
                  <input
                    id={`stage-input-${key}`}
                    type={spec.type === "int" || spec.type === "float" ? "number" : "text"}
                    step={spec.type === "int" ? "1" : spec.type === "float" ? "any" : undefined}
                    placeholder="Enter value..."
                    value={state.rawText}
                    onChange={(e) => handleScalarChange(key, e.target.value, spec.type)}
                    className="w-full px-2 py-1 text-xs"
                  />
                )}

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
