import React, { useEffect, useState } from "react";
import {
  createRun,
  fetchWorkflow,
  fetchWorkflowInputs,
  uploadFile,
} from "../api/client";
import type {
  WorkflowDocument,
  WorkflowInputSpec,
} from "../api/types.gen";
import { Link, useRouter } from "../router/Router";

interface InputValueState {
  value: unknown;
  rawText: string;
  isUploading?: boolean;
  uploadedPath?: string;
  uploadFileName?: string;
}

export function RunInputsForm({ workflowPath }: { workflowPath: string }) {
  const { navigate } = useRouter();
  const [workflowDoc, setWorkflowDoc] = useState<WorkflowDocument | null>(null);
  const [inputs, setInputs] = useState<ReadonlyArray<WorkflowInputSpec>>([]);
  const [formValues, setFormValues] = useState<Record<string, InputValueState>>({});
  const [noCache, setNoCache] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

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
          const defaultValue = spec.default !== undefined && spec.default !== null ? spec.default : "";
          initialValues[key] = {
            value: defaultValue,
            rawText: typeof defaultValue === "object" ? JSON.stringify(defaultValue) : String(defaultValue),
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
  }, [workflowPath]);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: Record<string, string> = {};
    const finalInputs: Record<string, unknown> = {};

    for (const spec of inputs) {
      const key = `${spec.node_id}.${spec.name}`;
      const state = formValues[key];
      const val = state ? state.value : undefined;

      if (spec.required) {
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
      });
      navigate(`/runs/${res.run_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  // Group inputs by stage_id
  const inputsByStage: Record<string, Array<WorkflowInputSpec>> = {};
  for (const input of inputs) {
    const stage = input.stage_id || "default";
    if (!inputsByStage[stage]) {
      inputsByStage[stage] = [];
    }
    inputsByStage[stage].push(input);
  }

  const stageKeys = Object.keys(inputsByStage);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <Link to="/workflows" className="hover:text-slate-200">
          &larr; Workflows
        </Link>
        <span>/</span>
        <span className="font-mono text-slate-300">{workflowPath}</span>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6">
        <h1 className="text-xl font-bold tracking-tight text-white">
          {workflowDoc?.workflow.name || workflowPath}
        </h1>
        {workflowDoc?.workflow.description && (
          <p className="mt-1 text-sm text-slate-400">
            {workflowDoc.workflow.description}
          </p>
        )}
        <p className="mt-2 font-mono text-xs text-slate-500">
          Path: {workflowPath}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-rose-900 bg-rose-950/60 p-3 text-sm text-rose-300"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
          Loading workflow inputs...
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {inputs.length === 0 ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6 text-center">
              <p className="text-sm font-medium text-slate-300">
                No unbound input parameters required
              </p>
              <p className="mt-1 text-xs text-slate-500">
                All inputs are wired or have default values. You can run this workflow immediately.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {stageKeys.map((stageKey) => {
                const stageInputs = inputsByStage[stageKey];
                const stageTitle =
                  workflowDoc?.workflow.stages?.[stageKey]?.title ||
                  (stageKey !== "default" ? stageKey : "Workflow Inputs");

                return (
                  <div
                    key={stageKey}
                    className="rounded-lg border border-slate-800 bg-slate-900/40 p-5 space-y-4"
                  >
                    <h2 className="text-sm font-semibold text-slate-200">
                      {stageTitle}
                    </h2>

                    <div className="space-y-4">
                      {stageInputs.map((spec) => {
                        const key = `${spec.node_id}.${spec.name}`;
                        const state = formValues[key] || {
                          value: "",
                          rawText: "",
                        };
                        const hasError = !!validationErrors[key];

                        return (
                          <div
                            key={key}
                            className="space-y-1.5 rounded-md border border-slate-800/80 bg-slate-950/50 p-4"
                          >
                            <div className="flex items-center justify-between">
                              <label
                                htmlFor={`input-${key}`}
                                className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"
                              >
                                <span>{spec.name}</span>
                                {spec.required && (
                                  <span className="text-rose-400">*</span>
                                )}
                              </label>
                              <div className="flex items-center gap-2 font-mono text-[11px] text-slate-500">
                                <span>node: {spec.node_id}</span>
                                <span>&bull;</span>
                                <span className="rounded bg-slate-800 px-1.5 py-0.2 text-slate-400">
                                  {spec.type}
                                  {spec.media ? ` (${spec.media})` : ""}
                                </span>
                              </div>
                            </div>

                            {/* Render based on spec.type */}
                            {spec.type === "file" || spec.type === "directory" ? (
                              <div className="space-y-2">
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
                                      handleFileUpload(key, files[0]);
                                    }
                                  }}
                                  className="flex flex-col items-center justify-center rounded-md border border-dashed border-slate-700 bg-slate-900/60 p-5 text-center cursor-pointer hover:border-slate-500 hover:bg-slate-900"
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
                                      if (e.target.files && e.target.files.length > 0) {
                                        handleFileUpload(key, e.target.files[0]);
                                      }
                                    }}
                                  />
                                  {state.isUploading ? (
                                    <span className="text-xs text-sky-400 animate-pulse">
                                      Uploading {state.uploadFileName}...
                                    </span>
                                  ) : state.uploadedPath ? (
                                    <div className="text-xs text-emerald-400 flex items-center gap-1.5">
                                      <span>&check;</span>
                                      <span>Uploaded: {state.uploadFileName} ({state.uploadedPath})</span>
                                    </div>
                                  ) : (
                                    <>
                                      <p className="text-xs font-medium text-slate-300">
                                        Drop {spec.type} here, or click to browse
                                      </p>
                                      {spec.default !== undefined && spec.default !== null && (
                                        <p className="mt-1 text-[11px] text-slate-500">
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
                                    handleScalarChange(key, e.target.value, "str")
                                  }
                                  className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-600 focus:border-slate-600 focus:outline-none"
                                />
                              </div>
                            ) : spec.type === "bool" ? (
                              <div className="flex items-center gap-2 pt-1">
                                <input
                                  id={`input-${key}`}
                                  type="checkbox"
                                  checked={Boolean(state.value)}
                                  onChange={(e) =>
                                    handleBoolChange(key, e.target.checked)
                                  }
                                  className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-emerald-600 focus:ring-emerald-600"
                                />
                                <span className="text-xs text-slate-400">
                                  Enable (default: {String(Boolean(spec.default))})
                                </span>
                              </div>
                            ) : spec.type === "json" ? (
                              <textarea
                                id={`input-${key}`}
                                rows={3}
                                placeholder={
                                  spec.default !== undefined && spec.default !== null
                                    ? JSON.stringify(spec.default)
                                    : "Enter JSON object or array..."
                                }
                                value={state.rawText}
                                onChange={(e) =>
                                  handleScalarChange(key, e.target.value, "json")
                                }
                                className="w-full rounded border border-slate-800 bg-slate-900 p-2.5 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-slate-600 focus:outline-none"
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
                                  spec.default !== undefined && spec.default !== null
                                    ? `Default: ${String(spec.default)}`
                                    : "Enter value..."
                                }
                                value={state.rawText}
                                onChange={(e) =>
                                  handleScalarChange(key, e.target.value, spec.type)
                                }
                                className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:border-slate-600 focus:outline-none"
                              />
                            )}

                            {hasError && (
                              <p className="text-[11px] text-rose-400 font-medium">
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

          <div className="flex flex-col gap-4 border-t border-slate-800 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={noCache}
                onChange={(e) => setNoCache(e.target.checked)}
                className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-emerald-600 focus:ring-emerald-600"
              />
              <span>Force re-run (disable cache lookup: <code>--no-cache</code>)</span>
            </label>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigate("/workflows")}
                className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50"
              >
                {submitting ? "Starting Run..." : "Start Run"}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
