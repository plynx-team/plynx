import { useEffect, useState } from "react";
import {
  cancelRun,
  fetchRunState,
  resumeRun,
  subscribeRunEvents,
} from "../api/client";
import { applyRunEvent, createInitialRunState } from "../api/reducer";
import type {
  NodeRunState,
  NodeStatus,
  RunState,
} from "../api/types.gen";
import { Link, useRouter } from "../router/Router";
import { formatDuration, formatTimestamp, runStatusBadgeClasses } from "./RunList";

function nodeStatusBadgeClasses(status: NodeStatus): string {
  switch (status) {
    case "SUCCESS":
      return "bg-emerald-950 text-emerald-300 border-emerald-800";
    case "RUNNING":
    case "BUILDING_ENVIRONMENT":
      return "bg-sky-950 text-sky-300 border-sky-800 animate-pulse";
    case "WAITING_FOR_USER":
      return "bg-amber-950 text-amber-300 border-amber-800";
    case "FAILED":
      return "bg-rose-950 text-rose-300 border-rose-800";
    case "CANCELED":
    case "BLOCKED":
      return "bg-slate-900 text-slate-400 border-slate-700";
    case "PENDING":
      return "bg-slate-950 text-slate-400 border-slate-800";
  }
}

export function RunDetail({ runId }: { runId: string }) {
  const { navigate } = useRouter();
  const [runState, setRunState] = useState<RunState | null>(null);
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
        if (active) {
          setRunState(initial);
          setLoading(false);
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

  const nodes: ReadonlyArray<NodeRunState> = runState
    ? Object.values(runState.nodes)
    : [];

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
                <span className="text-slate-500">Nodes</span>
                <p className="mt-0.5 text-slate-300">{nodes.length}</p>
              </div>
            </div>

            {runState.error && (
              <div className="mt-4 rounded border border-rose-900 bg-rose-950/50 p-3 text-xs text-rose-300">
                <span className="font-semibold">Error:</span> {runState.error}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-wide text-slate-200">
              Nodes ({nodes.length})
            </h2>
            {nodes.length === 0 ? (
              <div className="rounded-md border border-slate-800 bg-slate-900/40 p-6 text-center text-xs text-slate-500">
                No nodes reported yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-800 rounded-lg border border-slate-800 bg-slate-900/40">
                {nodes.map((node) => (
                  <div
                    key={node.node_id}
                    className="flex items-center justify-between px-4 py-3 text-sm"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs font-semibold text-slate-200">
                        {node.node_id}
                      </span>
                      {node.cache_hit && (
                        <span className="rounded bg-teal-950 border border-teal-800 px-1.5 py-0.2 text-[10px] font-medium text-teal-300">
                          cache hit
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={`rounded border px-2 py-0.5 text-xs font-medium ${nodeStatusBadgeClasses(
                          node.status,
                        )}`}
                      >
                        {node.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
