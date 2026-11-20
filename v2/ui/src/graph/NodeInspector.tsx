import { useEffect, useState } from "react";
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
import { detectPreviewKind } from "../previewers/ArtifactPreviewDialog";
import { CsvPreviewer } from "../previewers/CsvPreviewer";
import { ImagePreviewer } from "../previewers/ImagePreviewer";
import { JsonPreviewer } from "../previewers/JsonPreviewer";
import { MarkdownPreviewer } from "../previewers/MarkdownPreviewer";
import { TextPreviewer } from "../previewers/TextPreviewer";
import { DEFAULT_STAGE_ID, getOrderedStageIds, resolveNodePorts } from "./layout";
import { LiteralWidget } from "./LiteralWidget";
import type { NodeDiff } from "./runDiff";
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
  nodeDiff?: NodeDiff;
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

function InlineOutputPreview({ target }: { target: ArtifactPreviewTarget }) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const kind = detectPreviewKind(target.mediaType, target.filename);
  const isDirectUrl = kind === "pdf" || kind === "image";

  useEffect(() => {
    if (isDirectUrl) {
      setLoading(false);
      return;
    }
    if (typeof fetch !== "function") {
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    fetch(target.url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.text();
      })
      .then((text) => {
        if (active) {
          setContent(text);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [target.url, isDirectUrl]);

  if (loading) {
    return (
      <div
        className="mt-1 rounded p-1.5 text-[11px] font-mono"
        style={{
          backgroundColor: "var(--bg-canvas)",
          color: "var(--text-tertiary)",
        }}
      >
        Loading preview...
      </div>
    );
  }

  if (error) {
    return null;
  }

  return (
    <div
      data-testid={`inline-output-preview-${target.title}`}
      className="mt-1 max-h-40 overflow-auto rounded p-2 text-xs"
      style={{
        backgroundColor: "var(--bg-canvas)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      {kind === "image" && <ImagePreviewer url={target.url} alt={target.title} />}
      {kind === "csv" && content !== null && (
        <CsvPreviewer content={content} delimiter="," />
      )}
      {kind === "tsv" && content !== null && (
        <CsvPreviewer content={content} delimiter="\t" />
      )}
      {kind === "json" && content !== null && (
        <JsonPreviewer content={content} />
      )}
      {kind === "markdown" && content !== null && (
        <MarkdownPreviewer content={content} />
      )}
      {(kind === "text" || kind === "pdf") && content !== null && (
        <TextPreviewer content={content} />
      )}
    </div>
  );
}

export function NodeInspector({
  nodeId,
  workflow,
  opsMap,
  runState,
  nodeDiff,
  readOnly = false,
  onUpdateNodeSpec,
  onBindReference,
  onUnbindInput,
  onPreviewArtifact,
}: NodeInspectorProps) {
  const [stageError, setStageError] = useState<string | null>(null);

  const stageIds = getOrderedStageIds(workflow);
  const spec = nodeId ? workflow.nodes?.[nodeId] : undefined;

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
                <div className="mt-2 pt-2 border-t border-[#3c3c3c] text-xs">
                  <MarkdownPreviewer content={workflow.description} />
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
          </div>
        </div>

        {/* Diff Box when inspecting a Run that differs from Current Editor Node */}
        {nodeDiff && nodeDiff.status !== "unchanged" && (
          <div data-testid="inspector-node-diff" className="PropertiesBox">
            <div
              className="PropertiesBoxHeader flex items-center gap-1.5"
              style={{ color: "#ffcc80" }}
            >
              <FeatherIcon name="git-commit" size={12} />
              <span>Changes vs. Selected Run</span>
            </div>
            <div className="PropertiesBoxContent space-y-1.5 text-xs">
              {nodeDiff.status === "added" ? (
                <div style={{ color: "#ffcc80" }}>
                  This node was added in the editor after this run executed.
                </div>
              ) : (
                <>
                  {nodeDiff.opChanged && (
                    <div className="font-mono text-[11px]">
                      <div style={{ color: "#ff8a80" }}>
                        - Run op: {nodeDiff.runOp}
                      </div>
                      <div style={{ color: "#80cbc4" }}>
                        + Editor op: {nodeDiff.editorOp}
                      </div>
                    </div>
                  )}
                  {Object.values(nodeDiff.changedInputs).map((entry) => (
                    <div
                      key={entry.portName}
                      className="rounded p-1.5 font-mono text-[11px]"
                      style={{
                        backgroundColor: "var(--bg-canvas)",
                        border: "1px solid rgba(255, 167, 38, 0.35)",
                      }}
                    >
                      <div
                        className="font-semibold mb-0.5"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {entry.portName}
                      </div>
                      <div
                        className="truncate"
                        style={{ color: "#ff8a80" }}
                        title={JSON.stringify(entry.runValue ?? null)}
                      >
                        - Run: {JSON.stringify(entry.runValue ?? null)}
                      </div>
                      <div
                        className="truncate"
                        style={{ color: "#80cbc4" }}
                        title={JSON.stringify(entry.editorValue ?? null)}
                      >
                        + Editor: {JSON.stringify(entry.editorValue ?? null)}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}

        {/* Multiline / Markdown Description Box */}
        {opEntry?.description && (
          <div className="PropertiesBox">
            <div className="PropertiesBoxHeader">Description</div>
            <div
              data-testid="inspector-markdown-description"
              className="PropertiesBoxContent text-xs"
            >
              <MarkdownPreviewer content={opEntry.description} />
            </div>
          </div>
        )}

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

        {/* Outputs & Inline Previews Box */}
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
          <div className="PropertiesBoxContent divide-y divide-[#3c3c3c]">
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
                const target =
                  canPreview && runState
                    ? buildOutputPreviewTarget(runState.id, nodeId, out)
                    : null;

                return (
                  <div
                    key={out.name}
                    data-testid={`inspector-output-${out.name}`}
                    className="py-1"
                  >
                    <div className="OutputItem">
                      <div
                        className="OutputNameCell"
                        title={`${out.name} (${out.type})`}
                      >
                        <FeatherIcon
                          name={getPortIconName(out.type, out.media)}
                          size={12}
                          style={{ color: getPortIconColor(out.type) }}
                        />
                        <span className="truncate font-semibold">
                          {out.name}
                        </span>
                      </div>

                      <div className="OutputValueCell">
                        {target ? (
                          <button
                            type="button"
                            data-testid={`inspector-preview-output-${out.name}`}
                            className="OutputItemPreview"
                            onClick={() => onPreviewArtifact?.(target)}
                          >
                            <FeatherIcon name="maximize-2" size={11} />
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

                    {target && <InlineOutputPreview target={target} />}
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
