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
import {
  DEFAULT_STAGE_ID,
  DEFAULT_STAGE_TITLE,
  getOrderedStageIds,
  resolveNodePorts,
} from "./layout";
import { LiteralWidget } from "./LiteralWidget";
import { toSnakeCaseId } from "./mutations";
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
  selectedStageId?: string | undefined;
  onSelectStage?: (stageId: string | undefined) => void;
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
  onAddStage?: (
    stageId: string,
    title?: string,
    options?: { requireApproval?: boolean },
  ) => void;
  onUpdateStage?: (
    stageId: string,
    updates: { title?: string; require_approval?: boolean },
  ) => void;
  onDeleteStage?: (
    stageId: string,
    options?: { reassignToStageId?: string; deleteNodes?: boolean },
  ) => void;
  onReorderStages?: (
    newOrder: string[],
  ) => { success: boolean; reason?: string };
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
  const isDirectUrl = kind === "pdf" || kind === "image" || kind === "audio";

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
        backgroundColor: "var(--bg-panel-secondary)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      {kind === "image" && <ImagePreviewer url={target.url} alt={target.title} />}
      {kind === "audio" && (
        <audio controls src={target.url} className="w-full my-1" />
      )}
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
  selectedStageId,
  onSelectStage,
  workflow,
  opsMap,
  runState,
  nodeDiff,
  readOnly = false,
  onUpdateNodeSpec,
  onBindReference,
  onUnbindInput,
  onPreviewArtifact,
  onAddStage,
  onUpdateStage,
  onDeleteStage,
  onReorderStages,
}: NodeInspectorProps) {
  const [stageError, setStageError] = useState<string | null>(null);
  const [isAddingStage, setIsAddingStage] = useState<boolean>(false);
  const [newStageTitle, setNewStageTitle] = useState<string>("");
  const [newStageRequireApproval, setNewStageRequireApproval] = useState<boolean>(false);
  const [isCreatingStageForNode, setIsCreatingStageForNode] = useState<boolean>(false);
  const [newNodeStageTitle, setNewNodeStageTitle] = useState<string>("");

  const stageIds = getOrderedStageIds(workflow);
  const spec =
    (nodeId ? workflow.nodes?.[nodeId] : undefined) ??
    (nodeId && runState?.workflow_snapshot?.nodes
      ? runState.workflow_snapshot.nodes[nodeId]
      : undefined) ??
    (nodeId && runState?.nodes?.[nodeId]
      ? {
          op: nodeDiff?.runOp || "unknown",
          stage: DEFAULT_STAGE_ID,
          inputs: {},
        }
      : undefined);

  if (selectedStageId && (!nodeId || !spec)) {
    const stageSpec = workflow.stages?.[selectedStageId];
    const isDefaultStage = selectedStageId === DEFAULT_STAGE_ID;
    const memberNodes = Object.entries(workflow.nodes ?? {}).filter(
      ([, nSpec]) => (nSpec.stage || DEFAULT_STAGE_ID) === selectedStageId,
    );
    const stageIndex = stageIds.indexOf(selectedStageId);
    const canMoveEarlier = stageIndex > 0;
    const canMoveLater = stageIndex >= 0 && stageIndex < stageIds.length - 1;

    const handleMove = (direction: "earlier" | "later") => {
      if (!onReorderStages) return;
      const targetIdx = direction === "earlier" ? stageIndex - 1 : stageIndex + 1;
      const nextOrder = [...stageIds];
      const temp = nextOrder[stageIndex];
      nextOrder[stageIndex] = nextOrder[targetIdx];
      nextOrder[targetIdx] = temp;
      const res = onReorderStages(nextOrder);
      if (!res.success && res.reason) {
        setStageError(res.reason);
      } else {
        setStageError(null);
      }
    };

    return (
      <aside
        data-testid="stage-inspector"
        className="PropertiesBar"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="PropertiesHeader">
          <div className="flex items-center gap-1.5 truncate">
            <FeatherIcon
              name="layers"
              size={14}
              style={{ color: "var(--color-primary)" }}
            />
            <span className="truncate">
              Stage: {stageSpec?.title || selectedStageId}
            </span>
          </div>
          {onSelectStage && (
            <button
              type="button"
              aria-label="Close stage properties"
              onClick={() => onSelectStage(undefined)}
              className="control-button !h-5 !min-h-5 !px-1.5 !text-[10px]"
            >
              <FeatherIcon name="x" size={12} />
            </button>
          )}
        </div>

        <div className="PropertiesBoxRoot">
          <div className="PropertiesBox">
            <div className="PropertiesBoxHeader">Stage Details</div>
            <div className="PropertiesBoxContent space-y-2">
              <div className="ParameterItem">
                <div className="ParameterNameCell">Stage ID</div>
                <div className="ParameterValueCell font-mono text-xs flex items-center gap-1">
                  <span>{selectedStageId}</span>
                  {isDefaultStage && (
                    <span className="status-badge CREATED !text-[9px]">Default</span>
                  )}
                </div>
              </div>

              <div className="ParameterItem">
                <label
                  htmlFor="inspector-stage-title"
                  className="ParameterNameCell"
                >
                  Title
                </label>
                <div className="ParameterValueCell">
                  <input
                    id="inspector-stage-title"
                    data-testid="inspector-stage-title"
                    type="text"
                    disabled={readOnly}
                    value={
                      stageSpec?.title ??
                      (isDefaultStage ? DEFAULT_STAGE_TITLE : selectedStageId)
                    }
                    onChange={(e) =>
                      onUpdateStage?.(selectedStageId, { title: e.target.value })
                    }
                    className="w-full px-1.5 py-1 text-xs"
                  />
                </div>
              </div>

              <div className="pt-1 border-t border-[#3c3c3c]">
                <label className="flex items-start gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    data-testid="inspector-stage-gate-checkbox"
                    disabled={readOnly}
                    checked={Boolean(stageSpec?.require_approval)}
                    onChange={(e) =>
                      onUpdateStage?.(selectedStageId, {
                        require_approval: e.target.checked,
                      })
                    }
                    className="mt-0.5 rounded"
                  />
                  <div className="text-xs">
                    <span
                      className="font-semibold block"
                      style={{ color: "var(--text-primary)" }}
                    >
                      Approval Gate
                    </span>
                    <span
                      className="text-[11px] block"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Pauses the run before downstream stages start until approved.
                    </span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div className="PropertiesBox">
            <div className="PropertiesBoxHeader">Stage Order</div>
            <div className="PropertiesBoxContent space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span style={{ color: "var(--text-secondary)" }}>
                  Position: #{stageIndex + 1} of {stageIds.length}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    data-testid="btn-stage-move-earlier"
                    disabled={readOnly || !canMoveEarlier}
                    onClick={() => handleMove("earlier")}
                    title="Move stage earlier in execution order"
                    className="control-button !h-6 !min-h-6 !px-2 !text-xs"
                  >
                    <FeatherIcon name="chevron-up" size={12} />
                    <span>Earlier</span>
                  </button>
                  <button
                    type="button"
                    data-testid="btn-stage-move-later"
                    disabled={readOnly || !canMoveLater}
                    onClick={() => handleMove("later")}
                    title="Move stage later in execution order"
                    className="control-button !h-6 !min-h-6 !px-2 !text-xs"
                  >
                    <FeatherIcon name="chevron-down" size={12} />
                    <span>Later</span>
                  </button>
                </div>
              </div>
              {stageError && (
                <p
                  role="alert"
                  data-testid="inspector-stage-reorder-error"
                  className="mt-1 text-[11px]"
                  style={{ color: "var(--color-error)" }}
                >
                  {stageError}
                </p>
              )}
            </div>
          </div>

          <div className="PropertiesBox">
            <div className="PropertiesBoxHeader">
              <span>Operations ({memberNodes.length})</span>
            </div>
            <div className="PropertiesBoxContent text-xs">
              {memberNodes.length === 0 ? (
                <p
                  className="py-1 italic"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  No operations in this stage.
                </p>
              ) : (
                <div className="space-y-1">
                  {memberNodes.map(([nid, nSpec]) => (
                    <div
                      key={nid}
                      className="flex items-center justify-between px-2 py-1 rounded bg-[#242424] border border-[#363636]"
                    >
                      <span className="font-semibold truncate">
                        {nSpec.title || nid}
                      </span>
                      <span
                        className="font-mono text-[10px]"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {nid}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {!readOnly && onDeleteStage && (
            <div className="pt-2">
              <button
                type="button"
                data-testid="btn-delete-stage-inspector"
                disabled={stageIds.length <= 1}
                title={
                  stageIds.length <= 1
                    ? "Cannot delete the only stage in the workflow"
                    : "Delete stage"
                }
                onClick={() => onDeleteStage(selectedStageId)}
                className="control-button danger w-full justify-center !h-7 !text-xs"
              >
                <FeatherIcon name="trash-2" size={12} />
                <span>
                  {memberNodes.length === 0
                    ? "Delete Empty Stage"
                    : `Delete Stage (${memberNodes.length} ${
                        memberNodes.length === 1 ? "op" : "ops"
                      })`}
                </span>
              </button>
            </div>
          )}
        </div>
      </aside>
    );
  }

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

          {/* Interactive Stages Management in Workflow Properties */}
          <div className="PropertiesBox">
            <div className="PropertiesBoxHeader flex items-center justify-between">
              <span>Stages ({stageIds.length})</span>
              {!readOnly && onAddStage && (
                <button
                  type="button"
                  data-testid="btn-add-stage-workflow"
                  onClick={() => setIsAddingStage(true)}
                  className="control-button !h-5 !min-h-5 !px-1.5 !text-[10px]"
                >
                  <FeatherIcon name="plus" size={11} />
                  <span>Add Stage</span>
                </button>
              )}
            </div>
            <div className="PropertiesBoxContent space-y-1.5">
              {isAddingStage && (
                <div
                  data-testid="inline-add-stage-form"
                  className="p-2 rounded bg-[#242424] border border-[#404040] space-y-2 mb-2"
                >
                  <div className="text-xs font-semibold">New Stage</div>
                  <div>
                    <label className="text-[11px] block text-[var(--text-secondary)] mb-0.5">
                      Title
                    </label>
                    <input
                      type="text"
                      data-testid="input-new-stage-title"
                      placeholder="e.g. Data Preparation"
                      value={newStageTitle}
                      onChange={(e) => setNewStageTitle(e.target.value)}
                      className="w-full px-1.5 py-1 text-xs"
                      autoFocus
                    />
                  </div>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      data-testid="checkbox-new-stage-gate"
                      checked={newStageRequireApproval}
                      onChange={(e) =>
                        setNewStageRequireApproval(e.target.checked)
                      }
                      className="rounded"
                    />
                    <span>Approval Gate</span>
                  </label>
                  <div className="flex items-center justify-end gap-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        setIsAddingStage(false);
                        setNewStageTitle("");
                        setNewStageRequireApproval(false);
                      }}
                      className="control-button !h-6 !min-h-6 !px-2 !text-[11px]"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      data-testid="btn-submit-add-stage"
                      disabled={!newStageTitle.trim()}
                      onClick={() => {
                        const title = newStageTitle.trim();
                        const slug = toSnakeCaseId(title);
                        onAddStage?.(slug, title, {
                          requireApproval: newStageRequireApproval,
                        });
                        setIsAddingStage(false);
                        setNewStageTitle("");
                        setNewStageRequireApproval(false);
                      }}
                      className="control-button primary !h-6 !min-h-6 !px-2 !text-[11px]"
                    >
                      Add Stage
                    </button>
                  </div>
                </div>
              )}

              <div className="space-y-1">
                {stageIds.map((sid, idx) => {
                  const sDef = workflow.stages?.[sid];
                  const sTitle =
                    sDef?.title ||
                    (sid === DEFAULT_STAGE_ID ? DEFAULT_STAGE_TITLE : sid);
                  const isDef = sid === DEFAULT_STAGE_ID;
                  const nodeCount = Object.values(workflow.nodes ?? {}).filter(
                    (n) => (n.stage || DEFAULT_STAGE_ID) === sid,
                  ).length;

                  return (
                    <div
                      key={sid}
                      data-testid={`workflow-stage-row-${sid}`}
                      className="flex items-center justify-between p-1.5 rounded bg-[#242424] border border-[#363636] hover:border-[#4c4c4c] text-xs transition-colors"
                    >
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={() => onSelectStage?.(sid)}
                        className="flex items-center gap-1.5 min-w-0 cursor-pointer flex-1"
                        title="Click to inspect and edit stage"
                      >
                        <span className="font-mono text-[10px] text-[var(--text-tertiary)] w-4">
                          #{idx + 1}
                        </span>
                        <FeatherIcon
                          name="layers"
                          size={11}
                          style={{ color: "var(--text-secondary)" }}
                        />
                        <span className="truncate font-semibold">{sTitle}</span>
                        {isDef && (
                          <span className="status-badge CREATED !text-[9px]">
                            Default
                          </span>
                        )}
                        {sDef?.require_approval && (
                          <span className="status-badge WAITING !text-[9px]">
                            Gate
                          </span>
                        )}
                        <span className="font-mono text-[10px] text-[var(--text-tertiary)] ml-auto pr-1">
                          {nodeCount} {nodeCount === 1 ? "op" : "ops"}
                        </span>
                      </div>

                      {!readOnly && (
                        <div className="flex items-center gap-0.5 shrink-0">
                          {onReorderStages && (
                            <>
                              <button
                                type="button"
                                data-testid={`btn-workflow-stage-move-up-${sid}`}
                                disabled={idx === 0}
                                title="Move stage earlier"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const next = [...stageIds];
                                  const temp = next[idx];
                                  next[idx] = next[idx - 1];
                                  next[idx - 1] = temp;
                                  const res = onReorderStages(next);
                                  if (!res.success && res.reason) {
                                    setStageError(res.reason);
                                  } else {
                                    setStageError(null);
                                  }
                                }}
                                className="p-1 rounded hover:bg-[#3c3c3c] text-[var(--text-secondary)] disabled:opacity-20 disabled:hover:bg-transparent"
                              >
                                <FeatherIcon name="chevron-up" size={11} />
                              </button>
                              <button
                                type="button"
                                data-testid={`btn-workflow-stage-move-down-${sid}`}
                                disabled={idx === stageIds.length - 1}
                                title="Move stage later"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const next = [...stageIds];
                                  const temp = next[idx];
                                  next[idx] = next[idx + 1];
                                  next[idx + 1] = temp;
                                  const res = onReorderStages(next);
                                  if (!res.success && res.reason) {
                                    setStageError(res.reason);
                                  } else {
                                    setStageError(null);
                                  }
                                }}
                                className="p-1 rounded hover:bg-[#3c3c3c] text-[var(--text-secondary)] disabled:opacity-20 disabled:hover:bg-transparent"
                              >
                                <FeatherIcon name="chevron-down" size={11} />
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            title="Edit stage"
                            onClick={() => onSelectStage?.(sid)}
                            className="p-1 rounded hover:bg-[#3c3c3c] text-[var(--text-secondary)]"
                          >
                            <FeatherIcon name="edit-2" size={11} />
                          </button>
                          {stageIds.length > 1 && onDeleteStage && (
                            <button
                              type="button"
                              title="Delete stage"
                              onClick={() => onDeleteStage(sid)}
                              className="p-1 rounded hover:bg-[#3c3c3c] text-[var(--text-secondary)] hover:text-[var(--color-error)]"
                            >
                              <FeatherIcon name="trash-2" size={11} />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {stageError && (
                <p
                  role="alert"
                  data-testid="workflow-stage-reorder-error"
                  className="mt-1.5 text-[11px]"
                  style={{ color: "var(--color-error)" }}
                >
                  {stageError}
                </p>
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

  const isSnapshotOnly = Boolean(nodeId && !workflow.nodes?.[nodeId]);
  const effectiveReadOnly = readOnly || isSnapshotOnly;

  const opEntry = opsMap[spec.op];
  const ports = resolveNodePorts(nodeId, spec, workflow, opEntry);
  const currentStage = spec.stage || DEFAULT_STAGE_ID;
  const nodeRunState = runState?.nodes?.[nodeId];
  const displayTitle = spec.title || opEntry?.title || nodeId;

  const handleLiteralChange = (portName: string, nextVal: unknown) => {
    if (!onUpdateNodeSpec || effectiveReadOnly) return;
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
    if (effectiveReadOnly) return;
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
                  disabled={effectiveReadOnly}
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
                  disabled={effectiveReadOnly}
                  value={currentStage}
                  onChange={(e) => {
                    if (e.target.value === "__NEW_STAGE__") {
                      setIsCreatingStageForNode(true);
                      setNewNodeStageTitle("");
                    } else {
                      handleStageSelect(e.target.value);
                    }
                  }}
                  className="w-full px-1.5 py-1 text-xs"
                >
                  {stageIds.map((sid) => (
                    <option key={sid} value={sid}>
                      {sid === DEFAULT_STAGE_ID
                        ? "Workflow (main - Default)"
                        : workflow.stages?.[sid]?.title
                        ? `${workflow.stages[sid].title} (${sid})`
                        : sid}
                    </option>
                  ))}
                  {!effectiveReadOnly && onAddStage && (
                    <option value="__NEW_STAGE__">+ Create new stage...</option>
                  )}
                </select>
              </div>
            </div>
            {isCreatingStageForNode && (
              <div
                data-testid="inline-create-stage-for-node"
                className="mt-2 p-2 rounded bg-[#242424] border border-[#404040] space-y-1.5"
              >
                <div className="text-[11px] font-semibold text-[var(--text-secondary)]">
                  Create New Stage
                </div>
                <input
                  type="text"
                  data-testid="input-node-new-stage-title"
                  placeholder="e.g. Evaluation"
                  value={newNodeStageTitle}
                  onChange={(e) => setNewNodeStageTitle(e.target.value)}
                  className="w-full px-1.5 py-1 text-xs"
                  autoFocus
                />
                <div className="flex items-center justify-end gap-1.5 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreatingStageForNode(false);
                      setNewNodeStageTitle("");
                    }}
                    className="control-button !h-5 !min-h-5 !px-2 !text-[10px]"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    data-testid="btn-node-submit-new-stage"
                    disabled={!newNodeStageTitle.trim()}
                    onClick={() => {
                      const title = newNodeStageTitle.trim();
                      const slug = toSnakeCaseId(title);
                      onAddStage?.(slug, title);
                      handleStageSelect(slug);
                      setIsCreatingStageForNode(false);
                      setNewNodeStageTitle("");
                    }}
                    className="control-button primary !h-5 !min-h-5 !px-2 !text-[10px]"
                  >
                    Create & Move
                  </button>
                </div>
              </div>
            )}
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
              style={{
                color:
                  nodeDiff.status === "not_in_run"
                    ? "#ff8a80"
                    : nodeDiff.status === "new_in_run"
                      ? "#00d8ff"
                      : "#ffcc80",
              }}
            >
              <FeatherIcon
                name={
                  nodeDiff.status === "not_in_run"
                    ? "slash"
                    : nodeDiff.status === "new_in_run"
                      ? "plus"
                      : "git-commit"
                }
                size={12}
              />
              <span>
                {nodeDiff.status === "not_in_run"
                  ? "Not in Selected Run"
                  : nodeDiff.status === "new_in_run"
                    ? "New in Selected Run"
                    : "Run Changes vs. Editor"}
              </span>
            </div>
            <div className="PropertiesBoxContent space-y-1.5 text-xs">
              {nodeDiff.status === "not_in_run" ? (
                <div style={{ color: "#ff8a80" }}>
                  This operation is in the current workflow, but was not executed in this run.
                </div>
              ) : nodeDiff.status === "new_in_run" ? (
                <div style={{ color: "#00d8ff" }}>
                  This operation was executed in this run, but is not present in the current workflow.
                </div>
              ) : (
                <>
                  {nodeDiff.opChanged && (
                    <div className="font-mono text-[11px]">
                      <div style={{ color: "#ff8a80" }}>
                        - Editor op: {nodeDiff.editorOp}
                      </div>
                      <div style={{ color: "#80cbc4" }}>
                        + Run op: {nodeDiff.runOp}
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
                        title={JSON.stringify(entry.editorValue ?? null)}
                      >
                        - Editor: {JSON.stringify(entry.editorValue ?? null)}
                      </div>
                      <div
                        className="truncate"
                        style={{ color: "#80cbc4" }}
                        title={JSON.stringify(entry.runValue ?? null)}
                      >
                        + Run: {JSON.stringify(entry.runValue ?? null)}
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
                  const compatibleOutputs = effectiveReadOnly
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
                              {!effectiveReadOnly && (
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
                              readOnly={effectiveReadOnly}
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

                          {!effectiveReadOnly && compatibleOutputs.length > 0 && (
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
