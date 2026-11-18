import { useEffect, useState } from "react";
import {
  cancelRun,
  fetchRunState,
  fetchWorkflow,
  resumeRun,
  subscribeRunEvents,
} from "../api/client";
import { applyRunEvent, createInitialRunState } from "../api/reducer";
import type {
  RunState,
  WorkflowDocument,
} from "../api/types.gen";
import { Link, useRouter } from "../router/Router";
import { StepperView } from "../stepper/StepperView";
import { formatDuration, formatTimestamp, runStatusBadgeClasses } from "./RunList";

export function RunDetail({ runId }: { runId: string }) {
  const { navigate } = useRouter();
  const [runState, setRunState] = useState<RunState | null>(null);
  const [workflowDoc, setWorkflowDoc] = useState<WorkflowDocument | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setRunState(createInitialRunState(runId));

    fetchRunState(runId)
      .then((initial) => {
        if (!active) return;
        setRunState(initial);
        setLoading(false);

        // Fetch workflow document for stage definitions
        if (initial.workflow_path) {
          fetchWorkflow(initial.workflow_path)
            .then((doc) => {
              if (active) setWorkflowDoc(doc);
            })
            .catch(() => {
              // Silently ignore workflow doc fetch error if not critical
            });
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });

    const unsubscribe = subscribeRunEvents(runId, (event) => {
      if (!active) return;
      setRunState((prev) =>
        applyRunEvent(prev ?? createInitialRunState(runId), event),
      );
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [runId]);

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
              <div className="mt-4 rounded border border-rose-900 bg-rose-950/50 p-3 text-xs text-rose-300">
                <span className="font-semibold">Error:</span> {runState.error}
              </div>
            )}
          </div>

          {/* Stepper View */}
          <div className="space-y-4">
            <h2 className="text-sm font-bold tracking-wide text-white">
              Workflow Stages (Stepper)
            </h2>
            <StepperView
              runState={runState}
              workflowDoc={workflowDoc}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
