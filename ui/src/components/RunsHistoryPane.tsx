import { useEffect, useState } from "react";
import type { RunStatus, RunSummary } from "../api/types.gen";
import { FeatherIcon, type FeatherIconName } from "./FeatherIcon";
import { formatDuration, formatTimestamp, runStatusBadgeClasses } from "./RunList";

export interface RunsHistoryPaneProps {
  runs: ReadonlyArray<RunSummary>;
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  compactLimit?: number;
  pageSize?: number;
  hasUnsavedChanges?: boolean;
  fullHeight?: boolean;
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
}

function getRunStatusIcon(status: RunStatus): {
  icon: FeatherIconName;
  color: string;
  spin?: boolean;
} {
  switch (status) {
    case "RUNNING":
      return { icon: "loader", color: "#00d8ff", spin: true };
    case "WAITING_FOR_USER":
      return { icon: "help-circle", color: "var(--color-warning)" };
    case "SUCCESS":
      return { icon: "check-circle", color: "var(--color-success)" };
    case "FAILED":
      return { icon: "alert-circle", color: "var(--color-error)" };
    case "CANCELED":
      return { icon: "slash", color: "var(--text-tertiary)" };
  }
}

function formatShortRunId(runId: string): string {
  if (runId.length <= 16) return runId;
  const parts = runId.split("-");
  if (parts.length >= 3) {
    return `${parts[1]}-${parts[2]}`;
  }
  return runId.slice(-12);
}

export function RunsHistoryPane({
  runs,
  selectedRunId,
  onSelectRun,
  collapsed = false,
  onToggleCollapse,
  compactLimit = 2,
  pageSize = 10,
  hasUnsavedChanges = false,
  fullHeight = false,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
}: RunsHistoryPaneProps) {
  const [page, setPage] = useState<number>(0);
  const [showAllInEditMode, setShowAllInEditMode] = useState<boolean>(false);

  const isInspectingRun = selectedRunId !== null;
  const isExpandedList = isInspectingRun || showAllInEditMode || fullHeight;

  useEffect(() => {
    if (!selectedRunId) {
      setPage(0);
      return;
    }
    const idx = runs.findIndex((r) => r.id === selectedRunId);
    if (idx >= 0) {
      setPage(Math.floor(idx / pageSize));
    }
  }, [selectedRunId, runs, pageSize]);

  const totalPages = Math.max(1, Math.ceil(runs.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);

  const visibleRuns = isExpandedList
    ? runs.slice(safePage * pageSize, (safePage + 1) * pageSize)
    : runs.slice(0, compactLimit);

  const activeRunningCount = runs.filter((r) => r.status === "RUNNING").length;

  return (
    <section
      data-testid="runs-history-pane"
      className={`dock-accordion-section ${
        collapsed
          ? "is-collapsed"
          : isInspectingRun || fullHeight || showAllInEditMode
          ? "is-expanded-full"
          : "is-compact"
      }`}
    >
      <button
        type="button"
        data-testid="runs-accordion-toggle"
        onClick={onToggleCollapse}
        className="dock-accordion-header"
      >
        <span className="flex items-center gap-1.5 truncate">
          <FeatherIcon
            name={collapsed ? "chevron-right" : "chevron-down"}
            size={13}
          />
          <FeatherIcon
            name="activity"
            size={13}
            style={{
              color:
                activeRunningCount > 0 ? "#00d8ff" : "var(--color-primary)",
            }}
          />
          <span className="truncate">Runs &amp; Mode</span>
        </span>
        <span className="flex items-center gap-1.5">
          {activeRunningCount > 0 && (
            <span
              data-testid="runs-active-indicator"
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold"
              style={{
                backgroundColor: "rgba(0, 216, 255, 0.16)",
                color: "#00d8ff",
              }}
            >
              <FeatherIcon name="loader" size={10} className="animate-spin" />
              {activeRunningCount}
            </span>
          )}
          <span
            className="font-mono text-[11px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            {runs.length}
          </span>
        </span>
      </button>

      {!collapsed && (
        <div className="dock-accordion-body">
          {/* Pinned Working Draft (Clean Blueprint Editor Mode) */}
          <button
            type="button"
            data-testid="mode-working-draft"
            onClick={() => onSelectRun(null)}
            className={`run-history-item working-draft ${
              selectedRunId === null ? "selected" : ""
            }`}
          >
            <div className="flex items-center justify-between gap-1.5 w-full">
              <span className="flex items-center gap-1.5 font-semibold text-xs truncate">
                <FeatherIcon
                  name="edit-3"
                  size={13}
                  style={{
                    color:
                      selectedRunId === null
                        ? "var(--color-primary)"
                        : "var(--text-secondary)",
                  }}
                />
                <span className="truncate">Working Draft</span>
              </span>
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{
                  backgroundColor:
                    selectedRunId === null
                      ? "var(--color-primary)"
                      : "var(--bg-panel)",
                  color:
                    selectedRunId === null ? "#fff" : "var(--text-secondary)",
                }}
              >
                {selectedRunId === null ? "Editing" : "Edit"}
              </span>
            </div>
            <div
              className="flex items-center justify-between text-[11px] w-full"
              style={{ color: "var(--text-tertiary)" }}
            >
              <span>
                {selectedRunId === null
                  ? "Clean blueprint mode"
                  : "Click to return to editor"}
              </span>
              {hasUnsavedChanges && (
                <span style={{ color: "var(--color-warning)" }}>● Unsaved</span>
              )}
            </div>
          </button>

          {/* Runs List */}
          <div
            data-testid="runs-history-list"
            className="runs-history-list space-y-1"
          >
            {runs.length === 0 ? (
              <div
                className="px-2 py-2.5 text-center text-[11px]"
                style={{ color: "var(--text-tertiary)" }}
              >
                No runs yet. Click <strong>Run Workflow</strong> to execute.
              </div>
            ) : (
              visibleRuns.map((run) => {
                const isSelected = selectedRunId === run.id;
                const statusMeta = getRunStatusIcon(run.status);
                return (
                  <button
                    key={run.id}
                    type="button"
                    data-testid={`run-history-item-${run.id}`}
                    onClick={() =>
                      onSelectRun(isSelected ? null : run.id)
                    }
                    className={`run-history-item ${
                      isSelected ? "selected" : ""
                    } ${run.status === "RUNNING" ? "is-running" : ""}`}
                    title={`Run ${run.id} (${run.status})`}
                  >
                    <div className="flex items-center justify-between gap-1.5 w-full">
                      <span className="flex items-center gap-1.5 font-mono text-xs truncate">
                        <FeatherIcon
                          name={statusMeta.icon}
                          size={12}
                          className={statusMeta.spin ? "animate-spin" : ""}
                          style={{ color: statusMeta.color }}
                        />
                        <span className="truncate">
                          #{formatShortRunId(run.id)}
                        </span>
                      </span>
                      <span className={runStatusBadgeClasses(run.status)}>
                        {run.status}
                      </span>
                    </div>
                    <div
                      className="flex items-center justify-between text-[11px] w-full"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      <span>{formatTimestamp(run.created_at)}</span>
                      <span className="font-mono">
                        {formatDuration(run.started_at, run.finished_at)}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* Footer: either "Show all N runs" in compact mode, or Paginator in expanded mode */}
          {!isExpandedList && runs.length > compactLimit && (
            <button
              type="button"
              data-testid="runs-show-all-btn"
              onClick={() => setShowAllInEditMode(true)}
              className="w-full py-1 text-center text-[11px] rounded hover:bg-white/5"
              style={{ color: "var(--color-primary)" }}
            >
              Show all {runs.length} runs…
            </button>
          )}

          {isExpandedList && runs.length > pageSize && (
            <div
              data-testid="runs-paginator"
              className="flex items-center justify-between pt-1 px-1 text-[11px]"
              style={{
                borderTop: "1px solid var(--border-subtle)",
                color: "var(--text-secondary)",
              }}
            >
              <button
                type="button"
                data-testid="runs-page-prev"
                disabled={safePage === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="px-1.5 py-0.5 rounded disabled:opacity-40 hover:bg-white/5"
              >
                &lsaquo; Prev
              </button>
              <span data-testid="runs-page-indicator" className="font-mono">
                {safePage + 1} / {totalPages}
              </span>
              <button
                type="button"
                data-testid="runs-page-next"
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                className="px-1.5 py-0.5 rounded disabled:opacity-40 hover:bg-white/5"
              >
                Next &rsaquo;
              </button>
            </div>
          )}

          {showAllInEditMode && !isInspectingRun && !fullHeight && runs.length > compactLimit && (
            <button
              type="button"
              onClick={() => setShowAllInEditMode(false)}
              className="w-full py-0.5 text-center text-[10px] hover:underline"
              style={{ color: "var(--text-tertiary)" }}
            >
              Show fewer
            </button>
          )}

          {hasMore && onLoadMore && (
            <button
              type="button"
              data-testid="runs-load-more-btn"
              disabled={loadingMore}
              onClick={onLoadMore}
              className="w-full py-1 text-center text-[11px] rounded hover:bg-white/5 disabled:opacity-40"
              style={{ color: "var(--color-primary)" }}
            >
              {loadingMore ? "Loading older runs…" : "Load older runs…"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
