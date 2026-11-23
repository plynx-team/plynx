import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpEntry, WorkflowDocument } from "../api/types.gen";
import { RouterProvider } from "../router/Router";
import type { GraphViewProps } from "./GraphView";

vi.mock("../api/client", () => ({
  fetchWorkflow: vi.fn(),
  fetchOps: vi.fn(),
  fetchRuns: vi.fn().mockResolvedValue({ runs: [] }),
  fetchRunState: vi.fn(),
  saveWorkflow: vi.fn(),
}));

vi.mock("./GraphView", () => ({
  GraphView: ({ onSelectNode, onNodeDragStop, onViewportChange }: GraphViewProps) => (
    <div data-testid="mock-graph-view">
      <button
        type="button"
        data-testid="select-pick"
        onClick={() => onSelectNode?.("pick")}
      >
        Select Pick
      </button>
      <button
        type="button"
        data-testid="drag-pick"
        onClick={() => onNodeDragStop?.("pick", 320, 180)}
      >
        Drag Pick
      </button>
      <button
        type="button"
        data-testid="zoom-pan-graph"
        onClick={() => onViewportChange?.({ x: 150, y: 250, zoom: 1.75 })}
      >
        Zoom / Move Window
      </button>
    </div>
  ),
}));

import * as client from "../api/client";
import { WorkflowEditor } from "./WorkflowEditor";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  window.location.hash = "#/editor/examples/workflows/foo_or_woo.yaml?view=graph";
});

const OPS: Array<OpEntry> = [
  {
    id: "standard_io/demo:AskFooOrWoo",
    pack: "standard_io",
    module: "demo",
    name: "AskFooOrWoo",
    kind: "class",
    title: "Ask",
    category: "Demo",
    cacheable: false,
    description: "",
    inputs: [
      {
        name: "prompt",
        type: "str",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: "foo or woo?",
      },
    ],
    outputs: [{ name: "choice", type: "str", media: null }],
    allow_extra_inputs: false,
    source: "demo.py",
    valid: true,
    error: null,
  },
];

const INITIAL_DOC: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "foo_or_woo",
    stages: {
      ask: { title: "1. Ask", require_approval: false },
    },
    nodes: {
      pick: {
        op: "standard_io/demo:AskFooOrWoo",
        title: "Pick one",
        stage: "ask",
        inputs: { prompt: "foo or woo?" },
      },
    },
  },
  layout: {
    schema: 1,
    nodes: { pick: { x: 40, y: 60 } },
    viewport: { x: 0, y: 0, zoom: 1 },
  },
};

describe("WorkflowEditor save, layout sidecar, and dirty indicator (Task 6.12)", () => {
  it("tracks dirty state on edits/drags, saves via PUT /workflows with layout sidecar, and clears dirty state", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(INITIAL_DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(OPS);
    vi.mocked(client.saveWorkflow).mockImplementation(async (_path, doc) => doc);

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/foo_or_woo.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-graph-view")).toBeInTheDocument();
    });

    // Initially clean (not dirty)
    expect(screen.queryByTestId("dirty-indicator")).not.toBeInTheDocument();

    // Dragging a node marks dirty and updates coordinates
    fireEvent.click(screen.getByTestId("drag-pick"));
    expect(screen.getByTestId("dirty-indicator")).toHaveTextContent(
      "Unsaved changes",
    );

    // Editing a literal string with leading '$' escapes it as '$$' when saving
    fireEvent.click(screen.getByTestId("select-pick"));
    fireEvent.change(screen.getByTestId("inspector-input-prompt"), {
      target: { value: "$100 question?" },
    });

    // Save via button
    fireEvent.click(screen.getByTestId("btn-save-workflow"));

    await waitFor(() => {
      expect(client.saveWorkflow).toHaveBeenCalledTimes(1);
    });

    const [savedPath, savedBody] = vi.mocked(client.saveWorkflow).mock.calls[0];
    expect(savedPath).toBe("examples/workflows/foo_or_woo.yaml");
    expect(savedBody.workflow.nodes?.pick?.inputs?.prompt).toBe(
      "$$100 question?",
    );
    expect(savedBody.layout?.schema).toBe(1);
    expect(savedBody.layout?.nodes.pick).toEqual({ x: 320, y: 180 });

    await waitFor(() => {
      expect(screen.queryByTestId("dirty-indicator")).not.toBeInTheDocument();
      expect(screen.getByTestId("save-status")).toHaveTextContent("Saved");
    });
  });

  it("displays save error banner and retains dirty indicator when PUT /workflows fails", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(INITIAL_DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(OPS);
    vi.mocked(client.saveWorkflow).mockRejectedValue(
      new Error("Validation failed: unknown op"),
    );

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/foo_or_woo.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-graph-view")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("drag-pick"));
    expect(screen.getByTestId("dirty-indicator")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("btn-save-workflow"));

    await waitFor(() => {
      expect(screen.getByTestId("save-error-banner")).toHaveTextContent(
        "Validation failed: unknown op",
      );
    });
    expect(screen.getByTestId("dirty-indicator")).toBeInTheDocument();
  });

  it("does not consider zoom or moving window as unsaved changes", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(INITIAL_DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(OPS);

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/foo_or_woo.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-graph-view")).toBeInTheDocument();
    });

    // Clean initially
    expect(screen.queryByTestId("dirty-indicator")).not.toBeInTheDocument();
    expect(screen.getByTestId("btn-save-workflow")).not.toHaveClass("control-button-primary");

    // Zooming or moving the window/canvas does not mark workflow as dirty
    fireEvent.click(screen.getByTestId("zoom-pan-graph"));
    expect(screen.queryByTestId("dirty-indicator")).not.toBeInTheDocument();
    expect(screen.getByTestId("btn-save-workflow")).not.toHaveClass("control-button-primary");
  });

  it("aborts Save & Run when handleSave fails", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(INITIAL_DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(OPS);
    vi.mocked(client.saveWorkflow).mockRejectedValue(
      new Error("Disk full"),
    );

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/foo_or_woo.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-graph-view")).toBeInTheDocument();
    });

    // Make dirty
    fireEvent.click(screen.getByTestId("drag-pick"));
    expect(screen.getByTestId("dirty-indicator")).toBeInTheDocument();

    // Click Run Workflow -> opens unsaved changes confirm dialog
    fireEvent.click(screen.getByTestId("btn-run-workflow"));
    expect(screen.getByTestId("unsaved-run-confirm-dialog")).toBeInTheDocument();

    // Click Save & Run -> save fails
    fireEvent.click(screen.getByTestId("btn-save-and-run"));

    await waitFor(() => {
      expect(screen.getByTestId("save-error-banner")).toHaveTextContent("Disk full");
    });

    // Confirm dialog should NOT have closed and run modal should NOT have opened
    expect(screen.getByTestId("unsaved-run-confirm-dialog")).toBeInTheDocument();
    expect(screen.queryByTestId("run-inputs-form")).not.toBeInTheDocument();
  });
});
