import { useEffect, useState } from "react";
import { fetchRuns, fetchRunState, subscribeRunEvents } from "./api/client";
import { applyRunEvent, createInitialRunState } from "./api/reducer";
import type {
  NodeRunState,
  NodeStatus,
  RunState,
  RunSummary,
} from "./api/types.gen";

function statusBadgeClasses(status: NodeStatus): string {
  switch (status) {
    case "SUCCESS":
      return "bg-emerald-900/60 text-emerald-300 border-emerald-700";
    case "RUNNING":
    case "BUILDING_ENVIRONMENT":
      return "bg-sky-900/60 text-sky-300 border-sky-700";
    case "WAITING_FOR_USER":
      return "bg-amber-900/60 text-amber-300 border-amber-700";
    case "FAILED":
      return "bg-rose-900/60 text-rose-300 border-rose-700";
    case "CANCELED":
    case "BLOCKED":
      return "bg-slate-800 text-slate-400 border-slate-700";
    case "PENDING":
      return "bg-slate-900 text-slate-300 border-slate-800";
  }
}

export function App() {
  const [runs, setRuns] = useState<ReadonlyArray<RunSummary>>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [runState, setRunState] = useState<RunState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchRuns()
      .then((res) => {
        if (!active) return;
        setRuns(res.runs);
        if (res.runs.length > 0) {
          setSelectedRunId((prev) => prev || res.runs[0].id);
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedRunId.trim()) {
      return;
    }
    let active = true;
    setError(null);
    setRunState(createInitialRunState(selectedRunId));

    fetchRunState(selectedRunId)
      .then((initial) => {
        if (active) {
          setRunState(initial);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });

    const unsubscribe = subscribeRunEvents(selectedRunId, (event) => {
      if (!active) return;
      setRunState((prev) =>
        applyRunEvent(prev ?? createInitialRunState(selectedRunId), event),
      );
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [selectedRunId]);

  const nodes: ReadonlyArray<NodeRunState> = runState
    ? Object.values(runState.nodes)
    : [];

  return (
    <main className="mx-auto max-w-3xl p-6 space-y-6">
      <header className="flex items-center justify-between border-b border-slate-800 pb-4">
        <h1 className="text-xl font-semibold tracking-tight">PLynx v2</h1>
        <span className="text-xs text-slate-400">Live Run Monitor</span>
      </header>

      <section className="flex flex-wrap items-center gap-3">
        <label htmlFor="run-picker" className="text-sm text-slate-300">
          Run ID:
        </label>
        {runs.length > 0 && (
          <select
            id="run-picker"
            className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm"
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id} ({r.status})
              </option>
            ))}
          </select>
        )}
        <input
          type="text"
          aria-label="Custom Run ID"
          placeholder="Enter run ID..."
          className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm font-mono"
          value={selectedRunId}
          onChange={(e) => setSelectedRunId(e.target.value)}
        />
      </section>

      {error && (
        <div
          role="alert"
          className="rounded border border-rose-800 bg-rose-950/50 p-3 text-sm text-rose-300"
        >
          {error}
        </div>
      )}

      {runState && (
        <section className="space-y-4">
          <div className="flex items-center justify-between rounded border border-slate-800 bg-slate-900/60 p-4">
            <div>
              <p className="text-xs text-slate-400">Run</p>
              <p className="font-mono text-sm">{runState.id}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Status</p>
              <p className="font-semibold text-sm">{runState.status}</p>
            </div>
          </div>

          <div className="space-y-2">
            <h2 className="text-sm font-medium text-slate-300">Nodes</h2>
            {nodes.length === 0 ? (
              <p className="text-sm text-slate-500">No node events yet.</p>
            ) : (
              <ul className="divide-y divide-slate-800 rounded border border-slate-800 bg-slate-900/40">
                {nodes.map((node) => (
                  <li
                    key={node.node_id}
                    className="flex items-center justify-between px-4 py-3 text-sm"
                  >
                    <span className="font-mono">{node.node_id}</span>
                    <span
                      className={`rounded border px-2.5 py-0.5 text-xs font-medium ${statusBadgeClasses(node.status)}`}
                    >
                      {node.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
