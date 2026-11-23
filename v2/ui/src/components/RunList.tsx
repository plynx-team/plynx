import { useEffect, useState } from "react";
import { fetchRuns } from "../api/client";
import type { RunStatus, RunSummary } from "../api/types.gen";
import { Link, useRouter } from "../router/Router";
import {
  ControlButton,
  ControlPanel,
  ControlSeparator,
  SearchBar,
} from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";

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
  return `status-badge ${status}`;
}

export function RunList() {
  const { navigate } = useRouter();
  const [runs, setRuns] = useState<ReadonlyArray<RunSummary>>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const loadRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchRuns({ limit: 50 });
      setRuns(res.runs);
      setNextCursor(res.next_cursor ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const loadMoreRuns = async () => {
    if (!nextCursor || loadingMore) return;
    try {
      setLoadingMore(true);
      setError(null);
      const res = await fetchRuns({ limit: 50, cursor: nextCursor });
      setRuns((prev) => {
        const seen = new Set(prev.map((r) => r.id));
        return [...prev, ...res.runs.filter((r) => !seen.has(r.id))];
      });
      setNextCursor(res.next_cursor ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    void loadRuns();
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
    <div className="ListPage">
      <ControlPanel>
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Filter by run ID or workflow..."
          className="w-80"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-8 px-2.5 text-xs"
        >
          <option value="ALL">All Statuses</option>
          <option value="RUNNING">RUNNING</option>
          <option value="WAITING_FOR_USER">WAITING_FOR_USER</option>
          <option value="SUCCESS">SUCCESS</option>
          <option value="FAILED">FAILED</option>
          <option value="CANCELED">CANCELED</option>
        </select>

        <ControlSeparator />

        <ControlButton
          icon="refresh-cw"
          text="Refresh"
          onClick={() => void loadRuns()}
        />
        <ControlButton
          icon="plus"
          text="New Run"
          variant="primary"
          onClick={() => navigate("/workflows")}
        />
      </ControlPanel>

      {error && (
        <div
          role="alert"
          className="m-2 rounded border px-3 py-2 text-xs"
          style={{
            borderColor: "var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      )}

      <div className="list">
        <div
          className="list-header"
          style={{
            gridTemplateColumns:
              "minmax(180px, 1.5fr) 150px minmax(200px, 1.5fr) 110px 180px",
          }}
        >
          <div className="list-field">Workflow</div>
          <div className="list-field">Status</div>
          <div className="list-field">Run ID</div>
          <div className="list-field">Duration</div>
          <div className="list-field">Created</div>
        </div>

        {loading ? (
          <div
            className="p-8 text-center text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            Loading runs...
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="p-10 text-center">
            <p
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              No runs found
            </p>
            <p
              className="mt-1 text-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              {runs.length === 0
                ? "You haven't run any workflows yet in this workspace."
                : "No runs match the selected filter."}
            </p>
            {runs.length === 0 && (
              <div className="mt-4">
                <ControlButton
                  icon="grid"
                  text="Browse Workflows"
                  variant="primary"
                  onClick={() => navigate("/workflows")}
                />
              </div>
            )}
          </div>
        ) : (
          filteredRuns.map((run) => (
            <Link
              key={run.id}
              to={`/runs/${run.id}`}
              className="list-item"
              style={{
                gridTemplateColumns:
                  "minmax(180px, 1.5fr) 150px minmax(200px, 1.5fr) 110px 180px",
              }}
            >
              <div className="list-field flex items-center gap-2 font-semibold">
                <FeatherIcon
                  name="play-circle"
                  size={15}
                  style={{ color: "var(--color-primary)" }}
                />
                <span>{run.workflow_path}</span>
              </div>

              <div className="list-field">
                <span className={runStatusBadgeClasses(run.status)}>
                  {run.status}
                </span>
              </div>

              <div className="list-field font-mono text-xs">
                <span
                  style={{ color: "var(--color-primary)" }}
                  className="hover:underline font-semibold"
                >
                  {run.id}
                </span>
              </div>

              <div
                className="list-field text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                {formatDuration(run.started_at, run.finished_at)}
              </div>

              <div
                className="list-field text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                {formatTimestamp(run.created_at)}
              </div>
            </Link>
          ))
        )}
        {nextCursor && (
          <div className="p-3 text-center">
            <ControlButton
              icon="chevron-down"
              text={loadingMore ? "Loading..." : "Load More Runs"}
              data-testid="btn-load-more-runs"
              disabled={loadingMore}
              onClick={() => void loadMoreRuns()}
            />
          </div>
        )}
      </div>
    </div>
  );
}
