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
  RunState,
  WorkflowDocument,
} from "../api/types.gen";
import { GraphView } from "../graph/GraphView";
import { NodeInspector } from "../graph/NodeInspector";
import { Link, useRouter } from "../router/Router";
import { CheckpointCard } from "../stepper/CheckpointCard";
import { StageApprovalCard } from "../stepper/StageApprovalCard";
import { StepperView } from "../stepper/StepperView";
import { ArtifactPreviewDialog } from "../previewers/ArtifactPreviewDialog";
import { LogsPanel } from "./LogsPanel";
import { formatDuration, formatTimestamp, runStatusBadgeClasses } from "./RunList";

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
  const [ops, setOps] = useState<Array<OpEntry>>([]);
  const [viewMode, setViewModeState] = useState<RunViewMode>(() =>
    readSavedViewMode(runId),
  );
  const [reloadSeq, setReloadSeq] = useState<number>(0);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(undefined);
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
        .catch(() => {
          // Non-critical: GraphView can fall back to inferred ports
        });
    }

    // PROTOCOL.md section 9: load full ground truth from SQLite first, then connect SSE if non-terminal
    fetchRunState(runId)
      .then((initial) => {
        if (!active) return;
        setRunState(initial);
        setLoading(false);

        // Fetch workflow document for stage definitions and graph topology
        if (initial.workflow_path) {
          fetchWorkflow(initial.workflow_path)
            .then((doc) => {
              if (active) setWorkflowDoc(doc);
            })
            .catch(() => {
              // Silently ignore workflow doc fetch error if not critical
            });
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
              // On SSE error (e.g. server restart), resync ground truth from SQLite
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
                .catch(() => {
                  // Server may still be restarting; EventSource will retry
                })
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

  const isTerminal =
    runState?.status === "SUCCESS" ||
    runState?.status === "FAILED" ||
    runState?.status === "CANCELED";
  const canCancel = runState && !isTerminal && !runState.cancel_requested;
  const canResume =
    runState && (runState.status === "FAILED" || runState.status === "CANCELED");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <Link to="/runs" className="hover:text-slate-200">
          &larr; All Runs
        </Link>
        <span>/</span>
        <span className="font-mono text-slate-300">{runId}</span>
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-md border border-rose-900 bg-rose-950/60 p-3 text-sm text-rose-300"
        >
          {actionError}
        </div>
      )}

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-rose-900 bg-rose-950/60 p-4 text-sm text-rose-300"
        >
          {error}
        </div>
      ) : loading && !runState ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
          Loading run details...
        </div>
      ) : runState ? (
        <div className="space-y-6">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <h1 className="font-mono text-lg font-bold text-white">
                    {runState.id}
                  </h1>
                  <span
                    data-testid="run-status-badge"
                    className={`rounded border px-2.5 py-0.5 text-xs font-semibold ${runStatusBadgeClasses(
                      runState.status,
                    )}`}
                  >
                    {runState.status}
                  </span>
                </div>
                <p className="font-mono text-xs text-slate-400">
                  Workflow: {runState.workflow_path}
                </p>
              </div>

              <div className="flex items-center gap-2">
                {canCancel && (
                  <button
                    type="button"
                    disabled={actionInProgress}
                    onClick={handleCancel}
                    className="rounded-md border border-rose-800 bg-rose-950/50 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-900/60 disabled:opacity-50"
                  >
                    {actionInProgress ? "Cancelling..." : "Cancel Run"}
                  </button>
                )}
                {canResume && (
                  <button
                    type="button"
                    disabled={actionInProgress}
                    onClick={handleResume}
                    className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {actionInProgress ? "Resuming..." : "Resume Run"}
                  </button>
                )}
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-800/80 pt-4 sm:grid-cols-4 text-xs">
              <div>
                <span className="text-slate-500">Created</span>
                <p className="mt-0.5 text-slate-300">
                  {formatTimestamp(runState.created_at)}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Duration</span>
                <p className="mt-0.5 text-slate-300">
                  {formatDuration(runState.started_at, runState.finished_at)}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Owner PID</span>
                <p className="mt-0.5 font-mono text-slate-300">
                  {runState.owner_pid ?? "—"}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Total Nodes</span>
                <p className="mt-0.5 text-slate-300">
                  {Object.keys(runState.nodes).length}
                </p>
              </div>
            </div>

            {runState.error && (
              <div
                data-testid="run-error-banner"
                className="mt-4 rounded border border-rose-900 bg-rose-950/50 p-3 text-xs text-rose-300"
              >
                <span className="font-semibold">Error:</span> {runState.error}
              </div>
            )}
          </div>

          {/* Dual View: Stepper | Graph */}
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-bold tracking-wide text-white">
                {viewMode === "stepper"
                  ? "Workflow Stages (Stepper)"
                  : "Workflow DAG (Graph)"}
              </h2>

              <div
                role="tablist"
                aria-label="Run view mode"
                className="inline-flex rounded-md border border-slate-800 bg-slate-900 p-0.5 text-xs"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewMode === "stepper"}
                  data-testid="view-toggle-stepper"
                  onClick={() => setViewMode("stepper")}
                  className={`rounded px-3 py-1 font-semibold transition-colors ${
                    viewMode === "stepper"
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Stepper
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewMode === "graph"}
                  data-testid="view-toggle-graph"
                  onClick={() => setViewMode("graph")}
                  className={`rounded px-3 py-1 font-semibold transition-colors ${
                    viewMode === "graph"
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Graph
                </button>
              </div>
            </div>

            {viewMode === "stepper" ? (
              <StepperView
                runState={runState}
                workflowDoc={workflowDoc}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
              />
            ) : (
              <div className="space-y-4">
                {!isTerminal &&
                  runState.checkpoints
                    .filter((cp) => !cp.answered_at)
                    .map((cp) => (
                      <CheckpointCard
                        key={`${cp.node_id}-${cp.checkpoint_id}`}
                        runId={runState.id}
                        checkpoint={cp}
                      />
                    ))}
                {!isTerminal &&
                  Object.entries(runState.stage_gates)
                    .filter(([, gate]) => gate.status === "WAITING")
                    .map(([stageId, gate]) => (
                      <StageApprovalCard
                        key={stageId}
                        runId={runState.id}
                        stageId={stageId}
                        stageTitle={
                          workflowDoc?.workflow.stages?.[stageId]?.title || stageId
                        }
                        gateState={gate}
                      />
                    ))}
                <div className="flex gap-4">
                  <div className="flex-1 min-w-0">
                    <GraphView
                      workflowDoc={workflowDoc}
                      runState={runState}
                      ops={ops}
                      selectedNodeId={selectedNodeId}
                      onSelectNode={setSelectedNodeId}
                      readOnly={true}
                    />
                  </div>
                  {selectedNodeId && workflowDoc?.workflow && (
                    <div className="h-[540px]">
                      <NodeInspector
                        nodeId={selectedNodeId}
                        workflow={workflowDoc.workflow}
                        opsMap={opsMap}
                        runState={runState}
                        readOnly={true}
                        onPreviewArtifact={setPreviewTarget}
                      />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Logs Panel & Output Actions for Selected Node */}
          {selectedNodeId && (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/60 px-4 py-2 text-xs">
                <span className="font-mono text-slate-300">
                  Selected Node: <strong className="text-white">{selectedNodeId}</strong> (
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
                    className="rounded bg-slate-800 px-2.5 py-1 text-xs font-semibold text-emerald-400 hover:bg-slate-700"
                  >
                    Preview Output
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

          {/* Artifact Preview Dialog */}
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
      ) : null}
    </div>
  );
}
