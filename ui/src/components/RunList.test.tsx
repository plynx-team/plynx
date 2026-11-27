import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { RunList } from "./RunList";
import { RouterProvider } from "../router/Router";
import * as client from "../api/client";
import type { RunSummary } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockRuns: Array<RunSummary> = [
  {
    id: "run-abc-123",
    workflow_path: "examples/workflows/foo_or_woo.yaml",
    workflow_sha256: "hash1",
    status: "SUCCESS",
    cancel_requested: false,
    pinned: false,
    created_at: 1700000000,
    started_at: 1700000001,
    finished_at: 1700000010,
  },
  {
    id: "run-def-456",
    workflow_path: "workflows/test.yaml",
    workflow_sha256: "hash2",
    status: "FAILED",
    cancel_requested: false,
    pinned: false,
    created_at: 1700000100,
    started_at: 1700000101,
    finished_at: 1700000105,
    error: "Test failed",
  },
];

describe("RunList component", () => {
  beforeEach(() => {
    vi.spyOn(client, "fetchRuns").mockResolvedValue({ runs: mockRuns });
  });

  it("renders run history table with runs and statuses", async () => {
    render(
      <RouterProvider>
        <RunList />
      </RouterProvider>,
    );

    expect(screen.getByText("Loading runs...")).toBeDefined();

    await waitFor(() => {
      expect(screen.getAllByText(/run-abc-/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/run-def-/i).length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText("SUCCESS").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FAILED").length).toBeGreaterThan(0);
    expect(screen.getByText("examples/workflows/foo_or_woo.yaml")).toBeDefined();
  });

  it("renders runs table with multi-column grid layout for workflow, status, run id, duration, created, and actions (BUG-UI-1)", async () => {
    const { container } = render(
      <RouterProvider>
        <RunList />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText(/run-abc-/i).length).toBeGreaterThan(0);
    });

    const header = container.querySelector(".list-header");
    expect(header).toBeInTheDocument();
    expect(header).toHaveClass("run-list-grid");
    expect(header?.children.length).toBe(6);
    expect(header?.children[0].textContent).toBe("Workflow");
    expect(header?.children[1].textContent).toBe("Status");
    expect(header?.children[2].textContent).toBe("Run ID");
    expect(header?.children[3].textContent).toBe("Duration");
    expect(header?.children[4].textContent).toBe("Created");
    expect(header?.children[5].textContent).toBe("Actions");

    const row = screen.getByTestId("run-card-run-abc-123");
    expect(row).toBeInTheDocument();
    expect(row).toHaveClass("list-row");
    expect(row).toHaveClass("run-list-grid");
    expect(row.children.length).toBe(6);
    expect(row.children[0].textContent).toContain("examples/workflows/foo_or_woo.yaml");
    expect(row.children[1].textContent).toContain("SUCCESS");
    expect(row.children[2].textContent).toContain("run-abc-123");
    expect(screen.getByTestId("view-run-run-abc-123")).toBeInTheDocument();
  });

  it("handles empty runs state", async () => {
    vi.spyOn(client, "fetchRuns").mockResolvedValue({ runs: [] });
    render(
      <RouterProvider>
        <RunList />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("No runs found")).toBeDefined();
    });
  });

  it("displays error alert when fetch fails", async () => {
    vi.spyOn(client, "fetchRuns").mockRejectedValue(new Error("Network failure"));
    render(
      <RouterProvider>
        <RunList />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Network failure");
    });
  });
});
