import { useEffect, useState } from "react";
import { fetchRuns } from "../api/client";
import type { RunStatus, RunSummary } from "../api/types.gen";
import { Link, useRouter } from "../router/Router";

export function formatTimestamp(ts: number | null | undefined): string {
  if (!ts) return "—";
  const date = new Date(ts * 1000);
  return date.toLocaleString();
}

export function formatDuration(
  started: number | null | undefined,
  finished: number | null | undefined,
): string {
  if (!started) return "—";
  const end = finished ?? Date.now() / 1000;
  const elapsed = Math.max(0, Math.floor(end - started));
  if (elapsed < 60) {
    return `${elapsed}s`;
  }
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return `${mins}m ${secs}s`;
}

export function runStatusBadgeClasses(status: RunStatus): string {
  switch (status) {
    case "SUCCESS":
      return "bg-emerald-950 text-emerald-400 border-emerald-800";
    case "RUNNING":
      return "bg-sky-950 text-sky-400 border-sky-800 animate-pulse";
    case "WAITING_FOR_USER":
      return "bg-amber-950 text-amber-400 border-amber-800";
    case "FAILED":
      return "bg-rose-950 text-rose-400 border-rose-800";
    case "CANCELED":
      return "bg-slate-900 text-slate-400 border-slate-700";
  }
}

export function RunList() {
  const { navigate } = useRouter();
  const [runs, setRuns] = useState<ReadonlyArray<RunSummary>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const loadRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchRuns();
      setRuns(res.runs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  const filteredRuns = runs.filter((run) => {
    if (statusFilter !== "ALL" && run.status !== statusFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = run.id.toLowerCase().includes(q);
      const matchWf = run.workflow_path.toLowerCase().includes(q);
      if (!matchId && !matchWf) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Runs</h1>
          <p className="text-xs text-slate-400">
            Execution history and active workflows
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadRuns}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => navigate("/workflows")}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500"
          >
            New Run
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Filter by run ID or workflow..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="min-w-[240px] flex-1 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:border-slate-600 focus:outline-none"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-sm text-slate-300 focus:border-slate-600 focus:outline-none"
        >
          <option value="ALL">All Statuses</option>
          <option value="RUNNING">RUNNING</option>
          <option value="WAITING_FOR_USER">WAITING_FOR_USER</option>
          <option value="SUCCESS">SUCCESS</option>
          <option value="FAILED">FAILED</option>
          <option value="CANCELED">CANCELED</option>
        </select>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-rose-900 bg-rose-950/60 p-3 text-sm text-rose-300"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
          Loading runs...
        </div>
      ) : filteredRuns.length === 0 ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/30 p-12 text-center">
          <p className="text-sm font-medium text-slate-300">No runs found</p>
          <p className="mt-1 text-xs text-slate-500">
            {runs.length === 0
              ? "You haven't run any workflows yet in this workspace."
              : "No runs match the selected filter."}
          </p>
          {runs.length === 0 && (
            <button
              type="button"
              onClick={() => navigate("/workflows")}
              className="mt-4 rounded-md bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
            >
              Browse Workflows
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/40">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th scope="col" className="px-4 py-3">
                  Run ID
                </th>
                <th scope="col" className="px-4 py-3">
                  Workflow
                </th>
                <th scope="col" className="px-4 py-3">
                  Status
                </th>
                <th scope="col" className="px-4 py-3">
                  Duration
                </th>
                <th scope="col" className="px-4 py-3">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredRuns.map((run) => (
                <tr
                  key={run.id}
                  className="transition-colors hover:bg-slate-800/40"
                >
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">
                    <Link
                      to={`/runs/${run.id}`}
                      className="font-semibold text-emerald-400 hover:text-emerald-300 hover:underline"
                    >
                      {run.id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-300 font-mono">
                    {run.workflow_path}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded border px-2 py-0.5 text-[11px] font-medium tracking-wide ${runStatusBadgeClasses(
                        run.status,
                      )}`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">
                    {formatTimestamp(run.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
