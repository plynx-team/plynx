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
import type { ArtifactPreviewTarget } from "../graph/NodeInspector";
import { computeWorkflowRunDiff } from "../graph/runDiff";
import { isStageValidatorNodeId } from "../graph/types";
import { ArtifactPreviewDialog } from "../previewers/ArtifactPreviewDialog";
import { useRouter } from "../router/Router";
import { ControlButton, ControlPanel, ControlSeparator } from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";
import { RunInspector, type RunViewMode } from "./RunInspector";
import {
  formatDuration,
  formatTimestamp,
  runStatusBadgeClasses,
} from "./RunList";

export type { RunViewMode };

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
  const [previewTarget, setPreviewTarget] =
    useState<ArtifactPreviewTarget | null>(null);
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

        if (initial.workflow_path) {
          fetchWorkflow(initial.workflow_path)
            .then((doc) => {
              if (active) {
                setActiveWorkflowDoc(doc);
              }
            })
            .catch(() => {});
        }

        if (!TERMINAL_RUN_STATUSES.has(initial.status)) {
          unsubscribe = subscribeRunEvents(
            runId,
            (event) => {
              if (!active) return;
              let shouldResyncSnapshot = false;
              setRunState((prev) => {
                if (
                  event.type === "node_status" &&
                  prev?.workflow_snapshot?.nodes &&
                  !isStageValidatorNodeId(event.data.node_id) &&
                  !prev.workflow_snapshot.nodes[event.data.node_id]
                ) {
                  shouldResyncSnapshot = true;
                }
                return applyRunEvent(prev ?? createInitialRunState(runId), event);
              });
              if (shouldResyncSnapshot && !resyncPending) {
                resyncPending = true;
                fetchRunState(runId)
                  .then((latest) => {
                    if (active) setRunState(latest);
                  })
                  .catch(() => {})
                  .finally(() => {
                    resyncPending = false;
                  });
              }
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

  const runDiff = useMemo(
    () =>
      activeWorkflowDoc?.workflow && runState
        ? computeWorkflowRunDiff(activeWorkflowDoc.workflow, runState)
        : null,
    [activeWorkflowDoc, runState],
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
        <RunInspector
          runState={runState}
          viewMode={viewMode}
          ops={ops}
          opsMap={opsMap}
          editorWorkflow={activeWorkflowDoc?.workflow ?? null}
          fallbackLayout={activeWorkflowDoc?.layout ?? null}
          runDiff={runDiff}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
          onPreviewArtifact={setPreviewTarget}
          onApproved={() => setReloadSeq((s) => s + 1)}
          onCheckpointAnswered={() => setReloadSeq((s) => s + 1)}
          showLogsHeader={true}
        />
      ) : null}

      {previewTarget && (
        <ArtifactPreviewDialog
          title={previewTarget.title}
          url={previewTarget.url}
          filename={previewTarget.filename}
          mediaType={previewTarget.mediaType}
          onClose={() => setPreviewTarget(null)}
        />
      )}
    </div>
  );
}
