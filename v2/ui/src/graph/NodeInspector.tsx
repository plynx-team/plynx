import { useState } from "react";
import type {
  NodeSpec,
  OpEntry,
  OutputPortSpec,
  RunState,
  Workflow,
} from "../api/types.gen";
import { nodeStatusBadgeClasses } from "../stepper/NodeRow";
import { DEFAULT_STAGE_ID, getOrderedStageIds, resolveNodePorts } from "./layout";
import { LiteralWidget } from "./LiteralWidget";
import { extractNodeRef } from "./types";
import { getCompatibleUpstreamOutputs, validateStageChange } from "./validation";

export interface ArtifactPreviewTarget {
  title: string;
  url: string;
  filename?: string;
  mediaType?: string;
}

export interface NodeInspectorProps {
  nodeId: string | undefined;
  workflow: Workflow;
  opsMap: Record<string, OpEntry>;
  runState?: RunState | null;
  readOnly?: boolean;
  onUpdateNodeSpec?: (
    nodeId: string,
    updater: (spec: NodeSpec) => NodeSpec,
  ) => void;
  onBindReference?: (
    targetNodeId: string,
    targetPort: string,
    sourceNodeId: string,
    sourcePort: string,
  ) => void;
  onUnbindInput?: (targetNodeId: string, targetPort: string) => void;
  onPreviewArtifact?: (target: ArtifactPreviewTarget) => void;
}

function buildOutputPreviewTarget(
  runId: string,
  nodeId: string,
  output: OutputPortSpec,
): ArtifactPreviewTarget {
  const url = `/api/v1/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(
    nodeId,
  )}/outputs/${encodeURIComponent(output.name)}`;
  if (output.type === "file") {
    return {
      title: `${nodeId}.${output.name}`,
      url,
      mediaType: output.media ?? undefined,
      filename: `${nodeId}-${output.name}`,
    };
  }
  return {
    title: `${nodeId}.${output.name}`,
    url,
    mediaType: "application/json",
    filename: `${nodeId}-${output.name}.json`,
  };
}

export function NodeInspector({
  nodeId,
  workflow,
  opsMap,
  runState,
  readOnly = false,
  onUpdateNodeSpec,
  onBindReference,
  onUnbindInput,
  onPreviewArtifact,
}: NodeInspectorProps) {
  const [stageError, setStageError] = useState<string | null>(null);

  const spec = nodeId ? workflow.nodes?.[nodeId] : undefined;
  if (!nodeId || !spec) {
    return (
      <aside
        data-testid="node-inspector"
        className="w-80 shrink-0 rounded-lg border border-slate-800 bg-slate-900/60 p-4 overflow-y-auto"
      >
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300 border-b border-slate-800 pb-2">
          Node Inspector
        </h2>
        <p className="mt-4 text-xs text-slate-500">
          Select a node on the canvas to edit inputs, bind or unbind port
          references, and preview outputs.
        </p>
      </aside>
    );
  }

  const opEntry = opsMap[spec.op];
  const ports = resolveNodePorts(nodeId, spec, workflow, opEntry);
  const stageIds = getOrderedStageIds(workflow);
  const currentStage = spec.stage || DEFAULT_STAGE_ID;
  const nodeRunState = runState?.nodes?.[nodeId];

  const handleLiteralChange = (portName: string, nextVal: unknown) => {
    if (!onUpdateNodeSpec) return;
    onUpdateNodeSpec(nodeId, (prev) => {
      const nextInputs = { ...(prev.inputs ?? {}) };
      if (nextVal === undefined) {
        delete nextInputs[portName];
      } else {
        nextInputs[portName] = nextVal;
      }
      return { ...prev, inputs: nextInputs };
    });
  };

  const handleStageSelect = (nextStage: string) => {
    const check = validateStageChange(workflow, nodeId, nextStage);
    if (!check.valid) {
      setStageError(check.reason);
      return;
    }
    setStageError(null);
    onUpdateNodeSpec?.(nodeId, (prev) => ({
      ...prev,
      stage: nextStage,
    }));
  };

  return (
    <aside
      data-testid="node-inspector"
      className="flex h-full w-80 shrink-0 flex-col rounded-lg border border-slate-800 bg-slate-900/60 overflow-hidden"
    >
      {/* Inspector Header */}
      <div className="border-b border-slate-800 px-4 py-3 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Node Inspector
          </h2>
          {nodeRunState && (
            <span
              className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${nodeStatusBadgeClasses(
                nodeRunState.status,
              )}`}
            >
              {nodeRunState.status}
            </span>
          )}
        </div>
        <p className="font-mono text-xs font-semibold text-white">{nodeId}</p>
        <p className="font-mono text-[10px] text-slate-500 break-all">
          {spec.op}
        </p>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 text-xs">
        {/* Metadata */}
        <section className="space-y-3">
          <div>
            <label
              htmlFor="inspector-node-title"
              className="block text-[11px] font-medium text-slate-400 mb-1"
            >
              Title
            </label>
            <input
              id="inspector-node-title"
              data-testid="inspector-node-title"
              type="text"
              disabled={readOnly}
              value={spec.title ?? ""}
              placeholder={opEntry?.title || nodeId}
              onChange={(e) =>
                onUpdateNodeSpec?.(nodeId, (prev) => ({
                  ...prev,
                  title: e.target.value.trim() === "" ? null : e.target.value,
                }))
              }
              className="w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
            />
          </div>

          <div>
            <label
              htmlFor="inspector-node-stage"
              className="block text-[11px] font-medium text-slate-400 mb-1"
            >
              Stage
            </label>
            <select
              id="inspector-node-stage"
              data-testid="inspector-node-stage"
              disabled={readOnly}
              value={currentStage}
              onChange={(e) => handleStageSelect(e.target.value)}
              className="w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
            >
              {stageIds.map((sid) => (
                <option key={sid} value={sid}>
                  {workflow.stages?.[sid]?.title
                    ? `${workflow.stages[sid].title} (${sid})`
                    : sid}
                </option>
              ))}
            </select>
            {stageError && (
              <p
                role="alert"
                data-testid="inspector-stage-error"
                className="mt-1 text-[10px] text-rose-400"
              >
                {stageError}
              </p>
            )}
          </div>

          {opEntry?.description && (
            <p className="text-[11px] text-slate-400 leading-relaxed">
              {opEntry.description}
            </p>
          )}
        </section>

        {/* Inputs section */}
        <section className="space-y-3 border-t border-slate-800 pt-4">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Inputs ({ports.inputs.length})
          </h3>

          {ports.inputs.length === 0 ? (
            <p className="text-[11px] text-slate-500">
              This operation has no input ports.
            </p>
          ) : (
            <div className="space-y-3">
              {ports.inputs.map((port) => {
                const rawVal = spec.inputs?.[port.name];
                const ref = extractNodeRef(rawVal);
                const compatibleOutputs = readOnly
                  ? []
                  : getCompatibleUpstreamOutputs(workflow, nodeId, port, opsMap);

                return (
                  <div
                    key={port.name}
                    data-testid={`inspector-port-${port.name}`}
                    className="space-y-2 rounded-md border border-slate-800 bg-slate-950/60 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1 min-w-0">
                        <span className="truncate font-mono font-semibold text-slate-200">
                          {port.name}
                        </span>
                        {port.required && (
                          <span className="text-rose-400">*</span>
                        )}
                      </div>
                      <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                        {port.type}
                        {port.media ? ` (${port.media})` : ""}
                      </span>
                    </div>

                    {ref ? (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2 rounded border border-sky-800/80 bg-sky-950/50 px-2.5 py-1.5">
                          <span
                            data-testid={`inspector-ref-${port.name}`}
                            className="truncate font-mono text-[11px] text-sky-300"
                          >
                            ${ref.from_node}.{ref.output}
                          </span>
                          {!readOnly && (
                            <button
                              type="button"
                              data-testid={`inspector-unbind-${port.name}`}
                              onClick={() => onUnbindInput?.(nodeId, port.name)}
                              className="shrink-0 rounded border border-sky-700 bg-sky-900/60 px-2 py-0.5 text-[10px] font-semibold text-sky-200 hover:bg-sky-800"
                            >
                              Unbind
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <LiteralWidget
                          port={port}
                          value={rawVal}
                          readOnly={readOnly}
                          onChange={(nextVal) =>
                            handleLiteralChange(port.name, nextVal)
                          }
                        />

                        {rawVal === undefined &&
                          port.required &&
                          port.default === null && (
                            <p className="text-[10px] text-amber-400">
                              Unbound run input (prompted at run launch)
                            </p>
                          )}

                        {!readOnly && (
                          <div className="flex items-center gap-2">
                            {compatibleOutputs.length > 0 && (
                              <select
                                aria-label={`Bind ${port.name} to upstream output`}
                                data-testid={`inspector-bind-${port.name}`}
                                value=""
                                onChange={(e) => {
                                  const encoded = e.target.value;
                                  if (!encoded) return;
                                  const sepIdx = encoded.indexOf(".");
                                  if (sepIdx === -1) return;
                                  const srcNode = encoded.slice(0, sepIdx);
                                  const srcOut = encoded.slice(sepIdx + 1);
                                  onBindReference?.(
                                    nodeId,
                                    port.name,
                                    srcNode,
                                    srcOut,
                                  );
                                }}
                                className="min-w-0 flex-1 rounded border border-slate-800 bg-slate-900 px-2 py-1 text-[11px] text-sky-300 focus:border-sky-500 focus:outline-none"
                              >
                                <option value="">Bind reference...</option>
                                {compatibleOutputs.map(
                                  ({ nodeId: srcId, output }) => (
                                    <option
                                      key={`${srcId}.${output.name}`}
                                      value={`${srcId}.${output.name}`}
                                    >
                                      ${srcId}.{output.name} ({output.type})
                                    </option>
                                  ),
                                )}
                              </select>
                            )}

                            {rawVal !== undefined && (
                              <button
                                type="button"
                                data-testid={`inspector-clear-${port.name}`}
                                onClick={() =>
                                  handleLiteralChange(port.name, undefined)
                                }
                                className="shrink-0 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                              >
                                Clear
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Outputs & Artifact Preview section */}
        <section className="space-y-3 border-t border-slate-800 pt-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Outputs ({ports.outputs.length})
            </h3>
            {runState && (
              <span className="font-mono text-[10px] text-slate-500">
                run {runState.id.slice(0, 12)}
              </span>
            )}
          </div>

          {ports.outputs.length === 0 ? (
            <p className="text-[11px] text-slate-500">
              No outputs declared for this operation.
            </p>
          ) : (
            <div className="space-y-2">
              {ports.outputs.map((out) => {
                const canPreview =
                  Boolean(runState) && nodeRunState?.status === "SUCCESS";
                return (
                  <div
                    key={out.name}
                    data-testid={`inspector-output-${out.name}`}
                    className="flex items-center justify-between gap-2 rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-mono font-semibold text-emerald-300">
                        {out.name}
                      </p>
                      <p className="font-mono text-[10px] text-slate-500">
                        {out.type}
                        {out.media ? ` (${out.media})` : ""}
                      </p>
                    </div>
                    {canPreview && runState ? (
                      <button
                        type="button"
                        data-testid={`inspector-preview-output-${out.name}`}
                        onClick={() =>
                          onPreviewArtifact?.(
                            buildOutputPreviewTarget(runState.id, nodeId, out),
                          )
                        }
                        className="shrink-0 rounded border border-emerald-800 bg-emerald-950/80 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 hover:bg-emerald-900"
                      >
                        Preview
                      </button>
                    ) : (
                      <span className="shrink-0 text-[10px] text-slate-600">
                        {runState ? nodeRunState?.status ?? "PENDING" : "No run"}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}
