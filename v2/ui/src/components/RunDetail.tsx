import { useEffect, useMemo, useState } from "react";
import {
  cancelRun,
  fetchOps,
  fetchRunState,
  fetchWorkflow,
  resumeRun,
  subscribeRunEvents,
} from "../api/client";
import { applyRunEvent, createInitialRunState } from "../api/reducer";
import type {
  OpEntry,
  OutputPortSpec,
  RunState,
  WorkflowDocument,
} from "../api/types.gen";
import { GraphView } from "../graph/GraphView";
import {
  buildOutputPreviewTarget,
  NodeInspector,
} from "../graph/NodeInspector";
import { useRouter } from "../router/Router";
import { CheckpointCard } from "../stepper/CheckpointCard";
import { StageApprovalCard } from "../stepper/StageApprovalCard";
import { StepperView } from "../stepper/StepperView";
import { ArtifactPreviewDialog } from "../previewers/ArtifactPreviewDialog";
import { computeWorkflowRunDiff } from "../graph/runDiff";
import { ControlButton, ControlPanel, ControlSeparator } from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";
import { LogsPanel } from "./LogsPanel";
import {
  formatDuration,
  formatTimestamp,
  runStatusBadgeClasses,
} from "./RunList";

export type RunViewMode = "stepper" | "graph";

const TERMINAL_RUN_STATUSES = new Set(["SUCCESS", "FAILED", "CANCELED"]);

function readSavedViewMode(runId: string): RunViewMode {
  try {
    const saved = window.sessionStorage.getItem(`plynx:runView:${runId}`);
    if (saved === "graph" || saved === "stepper") return saved;
  } catch {
    // Ignore storage access restrictions
  }
  return "stepper";
}

function writeSavedViewMode(runId: string, mode: RunViewMode): void {
  try {
    window.sessionStorage.setItem(`plynx:runView:${runId}`, mode);
  } catch {
    // Ignore storage access restrictions
  }
}

export function RunDetail({ runId }: { runId: string }) {
  const { navigate } = useRouter();
  const [runState, setRunState] = useState<RunState | null>(null);
  const [workflowDoc, setWorkflowDoc] = useState<WorkflowDocument | null>(null);
  const [activeWorkflowDoc, setActiveWorkflowDoc] =
    useState<WorkflowDocument | null>(null);
  const [ops, setOps] = useState<Array<OpEntry>>([]);
  const [viewMode, setViewModeState] = useState<RunViewMode>(() =>
    readSavedViewMode(runId),
  );
  const [reloadSeq, setReloadSeq] = useState<number>(0);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(
    undefined,
  );
  const [previewTarget, setPreviewTarget] = useState<{
    title: string;
    url: string;
    filename?: string;
    mediaType?: string;
    content?: string;
  } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<boolean>(false);

  const setViewMode = (mode: RunViewMode) => {
    setViewModeState(mode);
    writeSavedViewMode(runId, mode);
  };

  useEffect(() => {
    setViewModeState(readSavedViewMode(runId));
  }, [runId]);

  const opsMap = useMemo<Record<string, OpEntry>>(() => {
    const map: Record<string, OpEntry> = {};
    for (const op of ops) {
      map[op.id] = op;
    }
    return map;
  }, [ops]);

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;
    let resyncPending = false;
    setLoading(true);
    setError(null);

    if (typeof fetchOps === "function") {
      fetchOps()
        .then((entries) => {
          if (active) setOps(entries);
        })
        .catch(() => {});
    }

    fetchRunState(runId)
      .then((initial) => {
        if (!active) return;
        setRunState(initial);
        setLoading(false);

        if (initial.workflow_snapshot) {
          setWorkflowDoc({ workflow: initial.workflow_snapshot, layout: null });
        }
        if (initial.workflow_path) {
          fetchWorkflow(initial.workflow_path)
            .then((doc) => {
              if (active) {
                setActiveWorkflowDoc(doc);
                setWorkflowDoc((prev) => ({
                  workflow: prev?.workflow ?? doc.workflow,
                  layout: doc.layout ?? prev?.layout ?? null,
                }));
              }
            })
            .catch(() => {});
        }

        if (!TERMINAL_RUN_STATUSES.has(initial.status)) {
          unsubscribe = subscribeRunEvents(
            runId,
            (event) => {
              if (!active) return;
              setRunState((prev) =>
                applyRunEvent(prev ?? createInitialRunState(runId), event),
              );
            },
            () => {
              if (!active || resyncPending) return;
              resyncPending = true;
              fetchRunState(runId)
                .then((latest) => {
                  if (!active) return;
                  setRunState(latest);
                  if (TERMINAL_RUN_STATUSES.has(latest.status)) {
                    unsubscribe?.();
                    unsubscribe = undefined;
                  }
                })
                .catch(() => {})
                .finally(() => {
                  resyncPending = false;
                });
            },
          );
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
      unsubscribe?.();
    };
  }, [runId, reloadSeq]);

  const handleCancel = async () => {
    if (!runState) return;
    try {
      setActionInProgress(true);
      setActionError(null);
      await cancelRun(runState.id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionInProgress(false);
    }
  };

  const handleResume = async () => {
    if (!runState) return;
    try {
      setActionInProgress(true);
      setActionError(null);
      const res = await resumeRun(runState.id);
      if (res.run_id !== runState.id) {
        navigate(`/runs/${res.run_id}`);
      } else {
        setReloadSeq((seq) => seq + 1);
      }
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionInProgress(false);
    }
  };

  const handlePreviewNodeOutput = (nodeId: string, output: OutputPortSpec) => {
    if (!runState) return;
    setPreviewTarget(buildOutputPreviewTarget(runState.id, nodeId, output));
  };

  const isTerminal =
    runState?.status === "SUCCESS" ||
    runState?.status === "FAILED" ||
    runState?.status === "CANCELED";
  const canCancel = runState && !isTerminal && !runState.cancel_requested;
  const canResume =
    runState &&
    (runState.status === "FAILED" ||
      runState.status === "CANCELED" ||
      (runState.status === "WAITING_FOR_USER" && !runState.owner_pid));

  const referenceWorkflow =
    activeWorkflowDoc?.workflow ?? workflowDoc?.workflow;

  const runDiff = useMemo(
    () =>
      referenceWorkflow && runState
        ? computeWorkflowRunDiff(referenceWorkflow, runState)
        : null,
    [referenceWorkflow, runState],
  );

  return (
    <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
      {/* Sub-header Control Panel Toolbar */}
      <ControlPanel>
        <div
          role="tablist"
          aria-label="Run view mode"
          className="control-toggle"
        >
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "stepper"}
            data-testid="view-toggle-stepper"
            onClick={() => setViewMode("stepper")}
            className={`control-button first ${
              viewMode === "stepper" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="sliders" size={14} />
            <span className="control-button-text">Stepper</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "graph"}
            data-testid="view-toggle-graph"
            onClick={() => setViewMode("graph")}
            className={`control-button last ${
              viewMode === "graph" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="grid" size={14} />
            <span className="control-button-text">Graph</span>
          </button>
        </div>

        <ControlSeparator />

        <ControlButton
          icon="list"
          text="All Runs"
          onClick={() => navigate("/runs")}
        />

        {runState?.workflow_path && (
          <ControlButton
            icon="edit-3"
            text="Edit Workflow"
            onClick={() => navigate(`/editor/${runState.workflow_path}`)}
          />
        )}

        {canCancel && (
          <ControlButton
            icon="x"
            text={actionInProgress ? "Cancelling..." : "Cancel Run"}
            variant="danger"
            disabled={actionInProgress}
            onClick={() => void handleCancel()}
          />
        )}

        {canResume && (
          <ControlButton
            icon="rotate-ccw"
            text={actionInProgress ? "Resuming..." : "Resume Run"}
            variant="primary"
            disabled={actionInProgress}
            onClick={() => void handleResume()}
          />
        )}

        {runState && (
          <div className="ml-auto flex items-center gap-3 pr-2 text-xs">
            {runDiff?.hasChanges && (
              <span
                data-testid="run-hud-diff-indicator"
                className="node-diff-badge"
              >
                <FeatherIcon name="git-commit" size={10} />
                <span>Workflow modified since this run</span>
              </span>
            )}
            <span className="font-mono font-semibold">{runState.id}</span>
            <span
              data-testid="run-status-badge"
              className={runStatusBadgeClasses(runState.status)}
            >
              {runState.status}
            </span>
            <span
              className="font-mono hidden md:inline"
              style={{ color: "var(--text-secondary)" }}
            >
              {formatDuration(runState.started_at, runState.finished_at)}
            </span>
            <span
              className="font-mono hidden lg:inline"
              style={{ color: "var(--text-tertiary)" }}
            >
              {formatTimestamp(runState.created_at)}
            </span>
          </div>
        )}
      </ControlPanel>

      {actionError && (
        <div
          role="alert"
          className="px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {actionError}
        </div>
      )}

      {runState?.error && (
        <div
          data-testid="run-error-banner"
          className="px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          <span className="font-semibold">Error:</span> {runState.error}
        </div>
      )}

      {error ? (
        <div
          role="alert"
          className="m-3 rounded p-3 text-xs"
          style={{
            border: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      ) : loading && !runState ? (
        <div
          className="p-8 text-center text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          Loading run details...
        </div>
      ) : runState ? (
        <div className="flex flex-1 min-h-0 flex-row overflow-hidden">
          {/* Center Workspace + Bottom Docked Logs Drawer */}
          <div
            className="flex flex-1 min-w-0 flex-col overflow-hidden"
            style={{ backgroundColor: "var(--bg-canvas)" }}
          >
            {/* Visually present view mode title for accessibility and tests */}
            <h2 className="sr-only">
              {viewMode === "stepper"
                ? "Workflow Stages (Stepper)"
                : "Workflow DAG (Graph)"}
            </h2>

            <div className="flex-1 min-h-0 flex flex-col overflow-y-auto">
              {viewMode === "stepper" ? (
                <StepperView
                  runState={runState}
                  workflowDoc={
                    referenceWorkflow
                      ? {
                          workflow: referenceWorkflow,
                          layout:
                            activeWorkflowDoc?.layout ??
                            workflowDoc?.layout ??
                            null,
                        }
                      : workflowDoc
                  }
                  runDiff={runDiff}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={setSelectedNodeId}
                  opsMap={opsMap}
                  onApproved={() => setReloadSeq((s) => s + 1)}
                />
              ) : (
                <div className="flex flex-1 min-h-0 flex-col">
                  {(!isTerminal &&
                    (runState.checkpoints.some((cp) => !cp.answered_at) ||
                      Object.values(runState.stage_gates).some(
                        (g) => g.status === "WAITING",
                      ))) && (
                    <div className="p-2.5 space-y-2 shrink-0">
                      {runState.checkpoints
                        .filter((cp) => !cp.answered_at)
                        .map((cp) => (
                          <CheckpointCard
                            key={`${cp.node_id}-${cp.checkpoint_id}`}
                            runId={runState.id}
                            checkpoint={cp}
                          />
                        ))}
                      {Object.entries(runState.stage_gates)
                        .filter(([, gate]) => gate.status === "WAITING")
                        .map(([stageId, gate]) => (
                          <StageApprovalCard
                            key={stageId}
                            runId={runState.id}
                            stageId={stageId}
                            stageTitle={
                              workflowDoc?.workflow.stages?.[stageId]?.title ||
                              stageId
                            }
                            gateState={gate}
                            workflow={workflowDoc?.workflow}
                            runInputs={runState.run_inputs}
                            opsMap={opsMap}
                            onApproved={() => setReloadSeq((s) => s + 1)}
                          />
                        ))}
                    </div>
                  )}

                  <div className="flex-1 min-h-0">
                    <GraphView
                      workflow={referenceWorkflow}
                      layout={activeWorkflowDoc?.layout ?? workflowDoc?.layout}
                      runState={runState}
                      runDiff={runDiff}
                      ops={ops}
                      selectedNodeId={selectedNodeId}
                      onSelectNode={setSelectedNodeId}
                      onPreviewOutput={handlePreviewNodeOutput}
                      readOnly={true}
                      heightClassName="h-full"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Bottom Docked Logs Drawer when a node is selected */}
            {selectedNodeId && (
              <div>
                <div
                  className="flex items-center justify-between px-3 py-1 text-xs"
                  style={{
                    backgroundColor: "var(--bg-panel)",
                    borderTop: "1px solid var(--border-subtle)",
                  }}
                >
                  <span className="font-mono">
                    Selected Node: <strong>{selectedNodeId}</strong> (
                    {runState.nodes[selectedNodeId]?.status ?? "PENDING"})
                  </span>
                  {runState.nodes[selectedNodeId]?.status === "SUCCESS" && (
                    <button
                      type="button"
                      onClick={() => {
                        setPreviewTarget({
                          title: `${selectedNodeId} output`,
                          url: `/api/v1/runs/${runState.id}/nodes/${selectedNodeId}/outputs/text`,
                          filename: `${selectedNodeId}-output.txt`,
                        });
                      }}
                      className="OutputItemPreview"
                    >
                      <FeatherIcon name="eye" size={12} />
                      <span>Preview Output</span>
                    </button>
                  )}
                </div>
                <LogsPanel
                  runId={runState.id}
                  nodeId={selectedNodeId}
                  onClose={() => setSelectedNodeId(undefined)}
                />
              </div>
            )}
          </div>

          {/* Right Docked PropertiesBar */}
          {referenceWorkflow && (
            <NodeInspector
              nodeId={selectedNodeId}
              workflow={referenceWorkflow}
              opsMap={opsMap}
              runState={runState}
              nodeDiff={
                selectedNodeId ? runDiff?.nodes?.[selectedNodeId] : undefined
              }
              readOnly={true}
              onPreviewArtifact={setPreviewTarget}
            />
          )}
        </div>
      ) : null}

      {previewTarget && (
        <ArtifactPreviewDialog
          title={previewTarget.title}
          url={previewTarget.url}
          filename={previewTarget.filename}
          mediaType={previewTarget.mediaType}
          initialContent={previewTarget.content}
          onClose={() => setPreviewTarget(null)}
        />
      )}
    </div>
  );
}
