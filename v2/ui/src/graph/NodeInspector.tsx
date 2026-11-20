import { useState } from "react";
import type {
  NodeSpec,
  OpEntry,
  OutputPortSpec,
  RunState,
  Workflow,
} from "../api/types.gen";
import {
  FeatherIcon,
  getPortIconColor,
  getPortIconName,
} from "../components/FeatherIcon";
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

export function buildOutputPreviewTarget(
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

  const stageIds = getOrderedStageIds(workflow);
  const spec = nodeId ? workflow.nodes?.[nodeId] : undefined;

  // Legacy v1 behavior: when no node is selected on the canvas, display Workflow Properties
  if (!nodeId || !spec) {
    const totalNodes = Object.keys(workflow.nodes ?? {}).length;
    return (
      <aside
        data-testid="node-inspector"
        className="PropertiesBar"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="PropertiesHeader">
          <span className="truncate">
            Properties of {workflow.name || "Workflow"}
          </span>
        </div>

        <div className="PropertiesBoxRoot">
          <div className="PropertiesBox">
            <div className="PropertiesBoxHeader">Workflow</div>
            <div className="PropertiesBoxContent">
              <div className="ParameterItem">
                <div className="ParameterNameCell">Name</div>
                <div className="ParameterValueCell font-semibold truncate">
                  {workflow.name}
                </div>
              </div>
              {workflow.description && (
                <div className="ParameterItem">
                  <div className="ParameterNameCell">Description</div>
                  <div className="ParameterValueCell">
                    {workflow.description}
                  </div>
                </div>
              )}
              <div className="ParameterItem">
                <div className="ParameterNameCell">Stages</div>
                <div className="ParameterValueCell font-mono">
                  {stageIds.length} ({stageIds.join(", ")})
                </div>
              </div>
              <div className="ParameterItem">
                <div className="ParameterNameCell">Nodes</div>
                <div className="ParameterValueCell font-mono">{totalNodes}</div>
              </div>
              {workflow.concurrency && (
                <div className="ParameterItem">
                  <div className="ParameterNameCell">Concurrency</div>
                  <div className="ParameterValueCell font-mono">
                    {workflow.concurrency}
                  </div>
                </div>
              )}
            </div>
          </div>

          {runState && (
            <div className="PropertiesBox">
              <div className="PropertiesBoxHeader">Active / Latest Run</div>
              <div className="PropertiesBoxContent">
                <div className="ParameterItem">
                  <div className="ParameterNameCell">Run ID</div>
                  <div className="ParameterValueCell font-mono text-xs truncate">
                    {runState.id}
                  </div>
                </div>
                <div className="ParameterItem">
                  <div className="ParameterNameCell">Status</div>
                  <div className="ParameterValueCell">
                    <span className={`status-badge ${runState.status}`}>
                      {runState.status}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <p
            className="px-1 pt-2 text-xs"
            style={{ color: "var(--text-tertiary)" }}
          >
            Select a node on the canvas to edit inputs, bind or unbind port
            references, and preview outputs.
          </p>
        </div>
      </aside>
    );
  }

  const opEntry = opsMap[spec.op];
  const ports = resolveNodePorts(nodeId, spec, workflow, opEntry);
  const currentStage = spec.stage || DEFAULT_STAGE_ID;
  const nodeRunState = runState?.nodes?.[nodeId];
  const displayTitle = spec.title || opEntry?.title || nodeId;

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
      className="PropertiesBar"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="PropertiesHeader">
        <span className="truncate" title={`Properties of ${displayTitle}`}>
          Properties of {displayTitle}
        </span>
        {nodeRunState && (
          <span className={`status-badge ${nodeRunState.status} !text-[10px]`}>
            {nodeRunState.status}
          </span>
        )}
      </div>

      <div className="PropertiesBoxRoot">
        {/* Node Metadata Box */}
        <div className="PropertiesBox">
          <div className="PropertiesBoxHeader">Node</div>
          <div className="PropertiesBoxContent">
            <div className="ParameterItem">
              <div className="ParameterNameCell">ID</div>
              <div className="ParameterValueCell font-mono text-xs truncate">
                {nodeId}
              </div>
            </div>
            <div className="ParameterItem">
              <div className="ParameterNameCell">Op</div>
              <div
                className="ParameterValueCell font-mono text-[11px] truncate"
                title={spec.op}
                style={{ color: "var(--text-secondary)" }}
              >
                {spec.op}
              </div>
            </div>
            <div className="ParameterItem">
              <label
                htmlFor="inspector-node-title"
                className="ParameterNameCell"
              >
                Title
              </label>
              <div className="ParameterValueCell">
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
                      title:
                        e.target.value.trim() === "" ? null : e.target.value,
                    }))
                  }
                  className="w-full px-1.5 py-1 text-xs"
                />
              </div>
            </div>
            <div className="ParameterItem">
              <label
                htmlFor="inspector-node-stage"
                className="ParameterNameCell"
              >
                Stage
              </label>
              <div className="ParameterValueCell">
                <select
                  id="inspector-node-stage"
                  data-testid="inspector-node-stage"
                  disabled={readOnly}
                  value={currentStage}
                  onChange={(e) => handleStageSelect(e.target.value)}
                  className="w-full px-1.5 py-1 text-xs"
                >
                  {stageIds.map((sid) => (
                    <option key={sid} value={sid}>
                      {workflow.stages?.[sid]?.title
                        ? `${workflow.stages[sid].title} (${sid})`
                        : sid}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {stageError && (
              <p
                role="alert"
                data-testid="inspector-stage-error"
                className="mt-1 text-[11px]"
                style={{ color: "var(--color-error)" }}
              >
                {stageError}
              </p>
            )}
            {opEntry?.description && (
              <p
                className="mt-1.5 text-[11px] leading-snug"
                style={{ color: "var(--text-secondary)" }}
              >
                {opEntry.description}
              </p>
            )}
          </div>
        </div>

        {/* Parameters / Inputs Box */}
        <div className="PropertiesBox">
          <div className="PropertiesBoxHeader">
            <span>Parameters ({ports.inputs.length})</span>
          </div>
          <div className="PropertiesBoxContent">
            {ports.inputs.length === 0 ? (
              <p
                className="text-xs py-1"
                style={{ color: "var(--text-tertiary)" }}
              >
                No input parameters.
              </p>
            ) : (
              <div className="divide-y divide-[#3c3c3c]">
                {ports.inputs.map((port) => {
                  const rawVal = spec.inputs?.[port.name];
                  const ref = extractNodeRef(rawVal);
                  const compatibleOutputs = readOnly
                    ? []
                    : getCompatibleUpstreamOutputs(
                        workflow,
                        nodeId,
                        port,
                        opsMap,
                      );

                  return (
                    <div
                      key={port.name}
                      data-testid={`inspector-port-${port.name}`}
                      className="py-1.5"
                    >
                      <div className="ParameterItem">
                        <div
                          className="ParameterNameCell"
                          title={`${port.name} (${port.type}${
                            port.media ? `: ${port.media}` : ""
                          })`}
                        >
                          <FeatherIcon
                            name={getPortIconName(port.type, port.media)}
                            size={12}
                            style={{ color: getPortIconColor(port.type) }}
                          />
                          <span className="truncate font-semibold">
                            {port.name}
                          </span>
                          {port.required && (
                            <span style={{ color: "var(--color-error)" }}>
                              *
                            </span>
                          )}
                        </div>

                        <div className="ParameterValueCell">
                          {ref ? (
                            <div className="flex items-center justify-between gap-1">
                              <span
                                data-testid={`inspector-ref-${port.name}`}
                                className="reference truncate font-mono text-xs italic font-semibold"
                                style={{ color: "var(--color-info)" }}
                              >
                                ${ref.from_node}.{ref.output}
                              </span>
                              {!readOnly && (
                                <button
                                  type="button"
                                  data-testid={`inspector-unbind-${port.name}`}
                                  title="Unbind reference"
                                  onClick={() =>
                                    onUnbindInput?.(nodeId, port.name)
                                  }
                                  className="control-button !h-6 !min-h-6 !px-1.5 !text-[10px]"
                                >
                                  <FeatherIcon name="x" size={11} />
                                  <span>Unbind</span>
                                </button>
                              )}
                            </div>
                          ) : (
                            <LiteralWidget
                              port={port}
                              value={rawVal}
                              readOnly={readOnly}
                              onChange={(nextVal) =>
                                handleLiteralChange(port.name, nextVal)
                              }
                            />
                          )}
                        </div>
                      </div>

                      {!ref && (
                        <div className="flex items-center justify-end gap-1.5 mt-1">
                          {rawVal === undefined &&
                            port.required &&
                            port.default === null && (
                              <span
                                className="text-[10px] mr-auto"
                                style={{ color: "var(--color-warning)" }}
                              >
                                Unbound run input
                              </span>
                            )}

                          {!readOnly && compatibleOutputs.length > 0 && (
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
                              className="px-1.5 py-0.5 text-[11px]"
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

                          {!readOnly && rawVal !== undefined && (
                            <button
                              type="button"
                              data-testid={`inspector-clear-${port.name}`}
                              onClick={() =>
                                handleLiteralChange(port.name, undefined)
                              }
                              className="control-button !h-5 !min-h-5 !px-1.5 !text-[10px]"
                            >
                              Clear
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Outputs Box */}
        <div className="PropertiesBox">
          <div className="PropertiesBoxHeader">
            <span>Outputs ({ports.outputs.length})</span>
            {runState && (
              <span
                className="font-mono text-[10px] font-normal"
                style={{ color: "var(--text-tertiary)" }}
              >
                {runState.id.slice(0, 12)}
              </span>
            )}
          </div>
          <div className="PropertiesBoxContent">
            {ports.outputs.length === 0 ? (
              <p
                className="text-xs py-1"
                style={{ color: "var(--text-tertiary)" }}
              >
                No outputs declared.
              </p>
            ) : (
              ports.outputs.map((out) => {
                const canPreview =
                  Boolean(runState) && nodeRunState?.status === "SUCCESS";
                return (
                  <div
                    key={out.name}
                    data-testid={`inspector-output-${out.name}`}
                    className="OutputItem"
                  >
                    <div
                      className="OutputNameCell"
                      title={`${out.name} (${out.type})`}
                    >
                      <FeatherIcon
                        name={getPortIconName(out.type, out.media)}
                        size={12}
                        style={{ color: getPortIconColor(out.type) }}
                      />
                      <span className="truncate font-semibold">{out.name}</span>
                    </div>

                    <div className="OutputValueCell">
                      {canPreview && runState ? (
                        <button
                          type="button"
                          data-testid={`inspector-preview-output-${out.name}`}
                          className="OutputItemPreview"
                          onClick={() =>
                            onPreviewArtifact?.(
                              buildOutputPreviewTarget(
                                runState.id,
                                nodeId,
                                out,
                              ),
                            )
                          }
                        >
                          <FeatherIcon name="eye" size={12} />
                          <span>Preview</span>
                        </button>
                      ) : (
                        <span
                          className="text-[11px]"
                          style={{ color: "var(--text-tertiary)" }}
                        >
                          {runState
                            ? nodeRunState?.status ?? "PENDING"
                            : out.type}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
