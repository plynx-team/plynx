import React, { useEffect, useState } from "react";
import {
  createRun,
  fetchOps,
  fetchWorkflow,
  fetchWorkflowInputs,
  uploadFile,
} from "../api/client";
import type {
  OpEntry,
  Workflow,
  WorkflowDocument,
  WorkflowInputSpec,
  WorkflowLayout,
} from "../api/types.gen";
import { getOrderedStageIds } from "../graph/layout";
import { useRouter } from "../router/Router";
import { ControlButton, ControlPanel, ControlSeparator } from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";

interface InputValueState {
  value: unknown;
  rawText: string;
  isUploading?: boolean;
  uploadedPath?: string;
  uploadFileName?: string;
}

export function extractUnboundInputs(
  workflow: Workflow,
  opsMap?: Record<string, OpEntry>,
): Array<WorkflowInputSpec> {
  if (!opsMap) return [];
  const unbound: Array<WorkflowInputSpec> = [];
  for (const [nodeId, node] of Object.entries(workflow.nodes ?? {})) {
    const op = opsMap[node.op];
    if (!op || !op.valid) continue;
    for (const port of op.inputs ?? []) {
      const hasInput = node.inputs && port.name in node.inputs;
      if (!hasInput && port.required && port.default === null) {
        unbound.push({
          node_id: nodeId,
          name: port.name,
          type: port.type,
          media: port.media ?? null,
          required: port.required,
          default: port.default ?? null,
          stage_id: node.stage || "main",
        });
      }
    }
  }
  return unbound;
}

export interface RunInputsFormProps {
  workflowPath: string;
  asModal?: boolean;
  onClose?: () => void;
  onRunStarted?: (runId: string) => void;
  inMemoryWorkflow?: Workflow | null;
  inMemoryLayout?: WorkflowLayout | null;
  opsMap?: Record<string, OpEntry>;
}

export function RunInputsForm({
  workflowPath,
  asModal = false,
  onClose,
  onRunStarted,
  inMemoryWorkflow,
  inMemoryLayout,
  opsMap,
}: RunInputsFormProps) {
  const { navigate } = useRouter();
  const [workflowDoc, setWorkflowDoc] = useState<WorkflowDocument | null>(null);
  const [inputs, setInputs] = useState<ReadonlyArray<WorkflowInputSpec>>([]);
  const [formValues, setFormValues] = useState<
    Record<string, InputValueState>
  >({});
  const [noCache, setNoCache] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    if (inMemoryWorkflow) {
      const doc: WorkflowDocument = {
        workflow: inMemoryWorkflow,
        layout: inMemoryLayout ?? null,
      };

      const resolveInputs = async () => {
        let currentOps = opsMap;
        if (!currentOps || Object.keys(currentOps).length === 0) {
          try {
            const opsList = await fetchOps();
            currentOps = {};
            for (const op of opsList) {
              currentOps[op.id] = op;
            }
          } catch {
            currentOps = {};
          }
        }
        return extractUnboundInputs(inMemoryWorkflow, currentOps);
      };

      resolveInputs()
        .then((inputSpecs) => {
          if (!active) return;
          setWorkflowDoc(doc);
          setInputs(inputSpecs);

          const initialValues: Record<string, InputValueState> = {};
          for (const spec of inputSpecs) {
            const key = `${spec.node_id}.${spec.name}`;
            const defaultValue =
              spec.default !== undefined && spec.default !== null
                ? spec.default
                : "";
            initialValues[key] = {
              value: defaultValue,
              rawText:
                typeof defaultValue === "object"
                  ? JSON.stringify(defaultValue)
                  : String(defaultValue),
            };
          }
          setFormValues(initialValues);
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (!active) return;
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        });

      return () => {
        active = false;
      };
    }

    Promise.all([
      fetchWorkflow(workflowPath),
      fetchWorkflowInputs(workflowPath),
    ])
      .then(([doc, inputSpecs]) => {
        if (!active) return;
        setWorkflowDoc(doc);
        setInputs(inputSpecs);

        const initialValues: Record<string, InputValueState> = {};
        for (const spec of inputSpecs) {
          const key = `${spec.node_id}.${spec.name}`;
          const defaultValue =
            spec.default !== undefined && spec.default !== null
              ? spec.default
              : "";
          initialValues[key] = {
            value: defaultValue,
            rawText:
              typeof defaultValue === "object"
                ? JSON.stringify(defaultValue)
                : String(defaultValue),
          };
        }
        setFormValues(initialValues);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [workflowPath, inMemoryWorkflow, inMemoryLayout, opsMap]);

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
        [key]: `Upload failed: ${
          err instanceof Error ? err.message : String(err)
        }`,
      }));
    }
  };

  const inputsByStage: Record<string, Array<WorkflowInputSpec>> = {};
  for (const input of inputs) {
    const stage = input.stage_id || "main";
    if (!inputsByStage[stage]) {
      inputsByStage[stage] = [];
    }
    inputsByStage[stage].push(input);
  }

  const orderedStageIds = workflowDoc
    ? getOrderedStageIds(workflowDoc.workflow)
    : Object.keys(inputsByStage);
  const initialStageId = orderedStageIds[0] || "main";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: Record<string, string> = {};
    const finalInputs: Record<string, unknown> = {};

    for (const spec of inputs) {
      const key = `${spec.node_id}.${spec.name}`;
      const state = formValues[key];
      const val = state ? state.value : undefined;
      const stage = spec.stage_id || "main";
      const isInitialStage =
        stage === initialStageId || orderedStageIds.length <= 1;

      // Only require inputs for the initial stage at run launch time. Later stages prompt just-in-time.
      if (spec.required && isInitialStage) {
        if (
          val === undefined ||
          val === null ||
          val === "" ||
          (spec.type === "json" && state.rawText.trim() === "")
        ) {
          errors[key] = `${spec.name} is required`;
          continue;
        }
      }

      if (val !== undefined && val !== "") {
        finalInputs[key] = val;
      }
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const res = await createRun({
        workflow_path: workflowPath,
        inputs: finalInputs,
        no_cache: noCache,
        workflow: inMemoryWorkflow ?? undefined,
        layout: inMemoryLayout ?? undefined,
      });
      if (onRunStarted) {
        onRunStarted(res.run_id);
      } else {
        navigate(`/runs/${res.run_id}`);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const stageKeys = Object.keys(inputsByStage);

  const formBody = (
    <div className="p-4 space-y-4">
      <div
        className="PropertiesBoxContent flex items-start justify-between gap-4 p-3"
      >
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold">
              {workflowDoc?.workflow.name || workflowPath}
            </h1>
            {inMemoryWorkflow && (
              <span
                data-testid="badge-unsaved-draft"
                className="status-badge NOT_IN_RUN !text-[9px]"
                title="Running in-memory draft from editor"
              >
                Unsaved Draft
              </span>
            )}
          </div>
          {workflowDoc?.workflow.description && (
            <p
              className="mt-0.5 text-xs"
              style={{ color: "var(--text-secondary)" }}
            >
              {workflowDoc.workflow.description}
            </p>
          )}
          <p
            className="mt-1 font-mono text-xs"
            style={{ color: "var(--text-tertiary)" }}
          >
            Path: {workflowPath}
          </p>
        </div>
        {!asModal && (
          <ControlButton
            icon="grid"
            text="Edit Graph"
            onClick={() => navigate(`/editor/${workflowPath}`)}
          />
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="rounded p-2.5 text-xs"
          style={{
            border: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <div
          className="PropertiesBoxContent p-6 text-center text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          Loading workflow inputs...
        </div>
      ) : (
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {inputs.length === 0 ? (
            <div className="PropertiesBoxContent p-5 text-center">
              <p className="text-sm font-semibold">
                No unbound input parameters required
              </p>
              <p
                className="mt-1 text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                All inputs are wired or have default values. You can run this
                workflow immediately.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {stageKeys.map((stageKey) => {
                const stageInputs = inputsByStage[stageKey];
                const stageTitle =
                  workflowDoc?.workflow.stages?.[stageKey]?.title ||
                  (stageKey !== "default" && stageKey !== "main"
                    ? stageKey
                    : "Workflow Inputs");
                const isInitialStage =
                  stageKey === initialStageId || orderedStageIds.length <= 1;

                return (
                  <div key={stageKey} className="PropertiesBox">
                    <div className="PropertiesBoxHeader flex items-center justify-between">
                      <h2>{stageTitle}</h2>
                      {!isInitialStage && (
                        <span
                          className="text-[11px] font-normal px-1.5 py-0.5 rounded"
                          style={{
                            backgroundColor: "var(--bg-panel-secondary)",
                            color: "var(--text-secondary)",
                            border: "1px solid var(--border-subtle)",
                          }}
                        >
                          Deferred to Stage Execution
                        </span>
                      )}
                    </div>
                    {!isInitialStage && (
                      <div
                        className="px-3 py-1.5 text-[11px]"
                        style={{
                          backgroundColor: "rgba(33, 150, 243, 0.08)",
                          color: "var(--color-info)",
                          borderBottom: "1px solid var(--border-subtle)",
                        }}
                      >
                        Inputs for this stage can be entered now, or deferred
                        until Stage &ldquo;{stageTitle}&rdquo; executes.
                      </div>
                    )}
                    <div className="PropertiesBoxContent space-y-3">
                      {stageInputs.map((spec) => {
                        const key = `${spec.node_id}.${spec.name}`;
                        const state = formValues[key] || {
                          value: "",
                          rawText: "",
                        };
                        const hasError = !!validationErrors[key];

                        return (
                          <div key={key} className="space-y-1.5 py-1">
                            <div className="flex items-center justify-between">
                              <label
                                htmlFor={`input-${key}`}
                                className="text-xs font-semibold flex items-center gap-1"
                              >
                                <span>{spec.name}</span>
                                {spec.required && isInitialStage && (
                                  <span style={{ color: "var(--color-error)" }}>
                                    *
                                  </span>
                                )}
                                {spec.required && !isInitialStage && (
                                  <span
                                    className="text-[10px] font-normal"
                                    style={{ color: "var(--text-tertiary)" }}
                                  >
                                    (deferred)
                                  </span>
                                )}
                              </label>
                              <div
                                className="flex items-center gap-2 font-mono text-[11px]"
                                style={{ color: "var(--text-tertiary)" }}
                              >
                                <span>node: {spec.node_id}</span>
                                <span>&bull;</span>
                                <span>
                                  {spec.type}
                                  {spec.media ? ` (${spec.media})` : ""}
                                </span>
                              </div>
                            </div>

                            {spec.type === "file" ||
                            spec.type === "directory" ? (
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
                                    backgroundColor:
                                      "var(--bg-panel-secondary)",
                                  }}
                                  onClick={() => {
                                    const el = document.getElementById(
                                      `file-upload-${key}`,
                                    ) as HTMLInputElement | null;
                                    el?.click();
                                  }}
                                >
                                  <input
                                    id={`file-upload-${key}`}
                                    type="file"
                                    className="hidden"
                                    onChange={(e) => {
                                      if (
                                        e.target.files &&
                                        e.target.files.length > 0
                                      ) {
                                        void handleFileUpload(
                                          key,
                                          e.target.files[0],
                                        );
                                      }
                                    }}
                                  />
                                  {state.isUploading ? (
                                    <span
                                      className="text-xs"
                                      style={{ color: "var(--color-info)" }}
                                    >
                                      Uploading {state.uploadFileName}...
                                    </span>
                                  ) : state.uploadedPath ? (
                                    <div
                                      className="text-xs flex items-center gap-1.5"
                                      style={{ color: "var(--color-success)" }}
                                    >
                                      <span>&check;</span>
                                      <span>
                                        Uploaded: {state.uploadFileName} (
                                        {state.uploadedPath})
                                      </span>
                                    </div>
                                  ) : (
                                    <>
                                      <p className="text-xs font-medium">
                                        Drop {spec.type} here, or click to
                                        browse
                                      </p>
                                      {spec.default !== undefined &&
                                        spec.default !== null && (
                                          <p
                                            className="mt-0.5 text-[11px]"
                                            style={{
                                              color: "var(--text-tertiary)",
                                            }}
                                          >
                                            Default: {String(spec.default)}
                                          </p>
                                        )}
                                    </>
                                  )}
                                </div>
                                <input
                                  id={`input-${key}`}
                                  type="text"
                                  placeholder="Or enter path / upload path manually..."
                                  value={state.rawText}
                                  onChange={(e) =>
                                    handleScalarChange(
                                      key,
                                      e.target.value,
                                      "str",
                                    )
                                  }
                                  className="w-full px-2 py-1 text-xs font-mono"
                                />
                              </div>
                            ) : spec.type === "bool" ? (
                              <div className="flex items-center gap-2 pt-0.5">
                                <input
                                  id={`input-${key}`}
                                  type="checkbox"
                                  checked={Boolean(state.value)}
                                  onChange={(e) =>
                                    handleBoolChange(key, e.target.checked)
                                  }
                                  className="h-3.5 w-3.5"
                                />
                                <span
                                  className="text-xs"
                                  style={{ color: "var(--text-secondary)" }}
                                >
                                  Enable (default:{" "}
                                  {String(Boolean(spec.default))})
                                </span>
                              </div>
                            ) : spec.type === "json" ? (
                              <textarea
                                id={`input-${key}`}
                                rows={3}
                                placeholder={
                                  spec.default !== undefined &&
                                  spec.default !== null
                                    ? JSON.stringify(spec.default)
                                    : "Enter JSON object or array..."
                                }
                                value={state.rawText}
                                onChange={(e) =>
                                  handleScalarChange(
                                    key,
                                    e.target.value,
                                    "json",
                                  )
                                }
                                className="w-full p-2 font-mono text-xs"
                              />
                            ) : (
                              <input
                                id={`input-${key}`}
                                type={
                                  spec.type === "int" || spec.type === "float"
                                    ? "number"
                                    : "text"
                                }
                                step={
                                  spec.type === "int"
                                    ? "1"
                                    : spec.type === "float"
                                    ? "any"
                                    : undefined
                                }
                                placeholder={
                                  spec.default !== undefined &&
                                  spec.default !== null
                                    ? `Default: ${String(spec.default)}`
                                    : "Enter value..."
                                }
                                value={state.rawText}
                                onChange={(e) =>
                                  handleScalarChange(
                                    key,
                                    e.target.value,
                                    spec.type,
                                  )
                                }
                                className="w-full px-2 py-1 text-xs"
                              />
                            )}

                            {hasError && (
                              <p
                                className="text-[11px] font-medium"
                                style={{ color: "var(--color-error)" }}
                              >
                                {validationErrors[key]}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div
            className="flex flex-wrap items-center justify-between gap-3 pt-3"
            style={{ borderTop: "1px solid var(--border-subtle)" }}
          >
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={noCache}
                onChange={(e) => setNoCache(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              <span>
                Force re-run (disable cache lookup: <code>--no-cache</code>)
              </span>
            </label>

            <div className="flex items-center gap-2">
              <ControlButton
                icon="x"
                text="Cancel"
                onClick={() => {
                  if (onClose) {
                    onClose();
                  } else {
                    navigate("/workflows");
                  }
                }}
              />
              <button
                type="submit"
                disabled={submitting}
                className="control-button primary"
              >
                <FeatherIcon name="play" size={14} />
                <span className="control-button-text">
                  {submitting ? "Starting Run..." : "Start Run"}
                </span>
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );

  if (asModal) {
    return (
      <div
        role="dialog"
        aria-modal="true"
        data-testid="run-inputs-modal"
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      >
        <div className="PreviewDialogWindow max-h-[90vh] w-full max-w-2xl overflow-y-auto">
          <div
            className="flex items-center justify-between px-4 py-2.5"
            style={{
              backgroundColor: "var(--bg-header)",
              borderBottom: "1px solid var(--border-subtle)",
            }}
          >
            <div className="flex items-center gap-2">
              <FeatherIcon
                name="play"
                size={14}
                style={{ color: "var(--color-primary)" }}
              />
              <span className="text-sm font-bold">Run Workflow</span>
            </div>
            {onClose && (
              <button
                type="button"
                aria-label="Close run modal"
                data-testid="btn-close-run-modal"
                onClick={onClose}
                className="p-1"
                style={{ color: "var(--text-secondary)" }}
              >
                <FeatherIcon name="x" size={16} />
              </button>
            )}
          </div>
          {formBody}
        </div>
      </div>
    );
  }

  return (
    <div className="ListPage">
      <ControlPanel>
        <ControlButton
          icon="arrow-left"
          text="Workflows"
          onClick={() => navigate("/workflows")}
        />
        <ControlSeparator />
        <ControlButton
          icon="grid"
          text="Edit Graph"
          onClick={() => navigate(`/editor/${workflowPath}`)}
        />
      </ControlPanel>
      <div className="flex-1 overflow-y-auto">{formBody}</div>
    </div>
  );
}
