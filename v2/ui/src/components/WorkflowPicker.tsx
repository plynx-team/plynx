import { useEffect, useState } from "react";
import { fetchWorkflows } from "../api/client";
import type { WorkflowListItem } from "../api/types.gen";
import { Link, useRouter } from "../router/Router";

export function WorkflowPicker() {
  const { navigate } = useRouter();
  const [workflows, setWorkflows] = useState<ReadonlyArray<WorkflowListItem>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");

  const loadWorkflows = async () => {
    try {
      setLoading(true);
      setError(null);
      const items = await fetchWorkflows();
      setWorkflows(items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkflows();
  }, []);

  const filtered = workflows.filter((wf) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      wf.name.toLowerCase().includes(q) || wf.path.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Workflows
          </h1>
          <p className="text-xs text-slate-400">
            Workflows discovered in this workspace
          </p>
        </div>
        <div>
          <button
            type="button"
            onClick={loadWorkflows}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search workflows by name or file path..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:border-slate-600 focus:outline-none"
        />
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
          Loading workflows...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/30 p-12 text-center">
          <p className="text-sm font-medium text-slate-300">
            No workflows found
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {workflows.length === 0
              ? "No workflows found in `workflows/` or `examples/workflows/`."
              : "No workflows matched your search."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((wf) => (
            <div
              key={wf.path}
              data-testid={`workflow-card-${wf.path}`}
              className="flex flex-col justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-5 transition-colors hover:border-slate-700"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-base font-semibold text-white">
                    {wf.name}
                  </h2>
                  <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-400">
                    {wf.stage_count} {wf.stage_count === 1 ? "stage" : "stages"}
                  </span>
                </div>
                <p className="font-mono text-xs text-slate-400 break-all">
                  {wf.path}
                </p>
              </div>

              <div className="mt-5 flex items-center justify-between gap-2 border-t border-slate-800/80 pt-4">
                <Link
                  to={`/workflows/${wf.path}`}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Configure &amp; Run &rarr;
                </Link>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    data-testid={`edit-workflow-${wf.path}`}
                    onClick={() => navigate(`/editor/${wf.path}`)}
                    className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800"
                  >
                    Edit Graph
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/workflows/${wf.path}`)}
                    className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500"
                  >
                    Run
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
