import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { WorkflowPicker } from "./WorkflowPicker";
import { RouterProvider } from "../router/Router";
import * as client from "../api/client";
import type { WorkflowListItem } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockWorkflows: Array<WorkflowListItem> = [
  {
    path: "examples/workflows/foo_or_woo.yaml",
    name: "Foo or Woo Demo",
    stage_count: 2,
  },
  {
    path: "workflows/data_pipeline.yaml",
    name: "Data Pipeline",
    stage_count: 3,
  },
];

describe("WorkflowPicker component", () => {
  beforeEach(() => {
    vi.spyOn(client, "fetchWorkflows").mockResolvedValue(mockWorkflows);
  });

  it("renders workflows list with names and stage counts", async () => {
    render(
      <RouterProvider>
        <WorkflowPicker />
      </RouterProvider>,
    );

    expect(screen.getByText("Loading workflows...")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("Foo or Woo Demo")).toBeDefined();
      expect(screen.getByText("Data Pipeline")).toBeDefined();
    });

    expect(screen.getByText("2 stages")).toBeDefined();
    expect(screen.getByText("3 stages")).toBeDefined();
  });

  it("handles empty workflows state", async () => {
    vi.spyOn(client, "fetchWorkflows").mockResolvedValue([]);
    render(
      <RouterProvider>
        <WorkflowPicker />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("No workflows found")).toBeDefined();
    });
  });

  it("displays error alert when fetch fails", async () => {
    vi.spyOn(client, "fetchWorkflows").mockRejectedValue(new Error("Disk error"));
    render(
      <RouterProvider>
        <WorkflowPicker />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Disk error");
    });
  });
});
