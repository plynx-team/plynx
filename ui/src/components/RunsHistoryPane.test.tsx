import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RunSummary } from "../api/types.gen";
import { RunsHistoryPane } from "./RunsHistoryPane";

afterEach(() => {
  cleanup();
});

const SAMPLE_RUNS: Array<RunSummary> = Array.from({ length: 8 }, (_, idx) => ({
  id: `20261120-10000${idx}-run${idx}`,
  workflow_path: "workflows/demo.yaml",
  workflow_sha256: "sha",
  status: idx === 0 ? "RUNNING" : idx % 2 === 0 ? "SUCCESS" : "FAILED",
  cancel_requested: false,
  pinned: false,
  created_at: 1700000000 + idx * 60,
  started_at: 1700000000 + idx * 60,
  finished_at: idx === 0 ? null : 1700000010 + idx * 60,
}));

describe("RunsHistoryPane component (Task 6.19)", () => {
  it("renders Working Draft row and compact run preview in editor mode", () => {
    const onSelectRun = vi.fn();
    render(
      <RunsHistoryPane
        runs={SAMPLE_RUNS}
        selectedRunId={null}
        onSelectRun={onSelectRun}
        compactLimit={2}
      />,
    );

    expect(screen.getByTestId("mode-working-draft")).toHaveTextContent(
      "Working Draft",
    );
    expect(screen.getByTestId("runs-active-indicator")).toBeInTheDocument();
    // Only 2 runs shown in compact mode initially
    expect(
      screen.getByTestId(`run-history-item-${SAMPLE_RUNS[0].id}`),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(`run-history-item-${SAMPLE_RUNS[1].id}`),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId(`run-history-item-${SAMPLE_RUNS[2].id}`),
    ).not.toBeInTheDocument();

    // Clicking a run selects it
    fireEvent.click(
      screen.getByTestId(`run-history-item-${SAMPLE_RUNS[0].id}`),
    );
    expect(onSelectRun).toHaveBeenCalledWith(SAMPLE_RUNS[0].id);
  });

  it("expands with pagination when a run is selected and returns to Working Draft on click", () => {
    const onSelectRun = vi.fn();
    render(
      <RunsHistoryPane
        runs={SAMPLE_RUNS}
        selectedRunId={SAMPLE_RUNS[0].id}
        onSelectRun={onSelectRun}
        pageSize={4}
      />,
    );

    expect(screen.getByTestId("runs-paginator")).toBeInTheDocument();
    expect(screen.getByTestId("runs-page-indicator")).toHaveTextContent(
      "1 / 2",
    );

    fireEvent.click(screen.getByTestId("runs-page-next"));
    expect(screen.getByTestId("runs-page-indicator")).toHaveTextContent(
      "2 / 2",
    );
    expect(
      screen.getByTestId(`run-history-item-${SAMPLE_RUNS[4].id}`),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("mode-working-draft"));
    expect(onSelectRun).toHaveBeenCalledWith(null);
  });

  it("expands full height and shows full list of runs without compact limit when fullHeight is true", () => {
    const onSelectRun = vi.fn();
    render(
      <RunsHistoryPane
        runs={SAMPLE_RUNS}
        selectedRunId={null}
        onSelectRun={onSelectRun}
        fullHeight={true}
        pageSize={10}
      />,
    );

    const section = screen.getByTestId("runs-history-pane");
    expect(section).toHaveClass("is-expanded-full");
    expect(section).not.toHaveClass("is-compact");

    // All 8 runs should be directly rendered
    SAMPLE_RUNS.forEach((run) => {
      expect(screen.getByTestId(`run-history-item-${run.id}`)).toBeInTheDocument();
    });

    // "Show all N runs…" button should NOT be rendered
    expect(screen.queryByTestId("runs-show-all-btn")).not.toBeInTheDocument();
  });
});
