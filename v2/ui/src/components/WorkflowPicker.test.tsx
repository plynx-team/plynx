import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
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

  it("opens New Workflow modal and creates a workflow navigating to editor", async () => {
    const saveSpy = vi.spyOn(client, "saveWorkflow").mockResolvedValue({
      workflow: {
        version: 1,
        name: "My New Workflow",
        stages: { main: { title: "Main", require_approval: false } },
        nodes: {},
      },
      layout: null,
    });

    render(
      <RouterProvider>
        <WorkflowPicker />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Foo or Woo Demo")).toBeDefined();
    });

    const newBtn = screen.getByTestId("btn-new-workflow");
    fireEvent.click(newBtn);

    expect(screen.getByTestId("modal-new-workflow")).toBeDefined();

    const nameInput = screen.getByTestId("input-new-workflow-name");
    const pathInput = screen.getByTestId("input-new-workflow-path");
    const submitBtn = screen.getByTestId("btn-submit-new-workflow");

    // Initially submit is disabled
    expect(submitBtn).toBeDisabled();

    // Type name: automatically generates slug path
    fireEvent.change(nameInput, { target: { value: "My New Workflow" } });
    expect(pathInput).toHaveValue("workflows/my_new_workflow.yaml");
    expect(submitBtn).not.toBeDisabled();

    // Test duplicate path validation
    fireEvent.change(pathInput, {
      target: { value: "workflows/data_pipeline.yaml" },
    });
    expect(
      screen.getByText(/already exists/i),
    ).toBeDefined();
    expect(submitBtn).toBeDisabled();

    // Change back to new path
    fireEvent.change(pathInput, {
      target: { value: "workflows/my_new_workflow.yaml" },
    });
    expect(submitBtn).not.toBeDisabled();

    // Submit form
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(saveSpy).toHaveBeenCalledWith(
        "workflows/my_new_workflow.yaml",
        expect.objectContaining({
          workflow: expect.objectContaining({
            name: "My New Workflow",
            version: 1,
          }),
        }),
      );
    });
  });
});
