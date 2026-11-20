import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { OpEntry, WorkflowDocument } from "../api/types.gen";
import { RouterProvider } from "../router/Router";
import { WorkflowEditor } from "./WorkflowEditor";

vi.mock("../api/client", () => ({
  fetchWorkflow: vi.fn(),
  fetchOps: vi.fn(),
  fetchRuns: vi.fn().mockResolvedValue({ runs: [] }),
  fetchRunState: vi.fn(),
  saveWorkflow: vi.fn(),
}));

import * as client from "../api/client";

beforeAll(() => {
  if (typeof window.ResizeObserver === "undefined") {
    class MockResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    window.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  }
  if (typeof window.DOMMatrixReadOnly === "undefined") {
    class MockDOMMatrixReadOnly {
      m22 = 1;
      constructor() {}
    }
    window.DOMMatrixReadOnly =
      MockDOMMatrixReadOnly as unknown as typeof DOMMatrixReadOnly;
  }
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const MOCK_OPS: Array<OpEntry> = [
  {
    id: "standard_io/demo:Echo",
    pack: "standard_io",
    module: "demo",
    name: "Echo",
    kind: "class",
    title: "Echo text",
    category: "Demo",
    cacheable: true,
    description: "Echo an input string.",
    inputs: [
      {
        name: "text",
        type: "str",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: true,
        default: null,
      },
    ],
    outputs: [{ name: "text", type: "str", media: null }],
    source: "demo.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/text:Concat",
    pack: "standard_io",
    module: "text",
    name: "Concat",
    kind: "class",
    title: "Concat text",
    category: "Text / Basic",
    cacheable: true,
    description: "Join two strings.",
    inputs: [
      {
        name: "a",
        type: "str",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: true,
        default: null,
      },
      {
        name: "b",
        type: "str",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: " ",
      },
    ],
    outputs: [{ name: "text", type: "str", media: null }],
    source: "text.py",
    valid: true,
    error: null,
  },
];

const MOCK_DOC: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "sample_wf",
    stages: {
      main: { title: "Workflow", require_approval: false },
    },
    nodes: {
      echo: {
        op: "standard_io/demo:Echo",
        title: "Echo one",
        stage: "main",
        inputs: { text: "hello" },
      },
    },
  },
  layout: null,
};

describe("WorkflowEditor palette & node operations (Task 6.9)", () => {
  it("adds, duplicates, and deletes nodes in the graph editor", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/sample.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("graph-node-echo")).toBeInTheDocument();
    });

    // Add Concat node from palette
    fireEvent.click(screen.getByTestId("palette-op-standard_io/text:Concat"));
    await waitFor(() => {
      expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
    });

    // Newly added node is selected, so Duplicate is enabled
    const duplicateBtn = screen.getByTestId("btn-duplicate-node");
    expect(duplicateBtn).not.toBeDisabled();
    fireEvent.click(duplicateBtn);

    await waitFor(() => {
      expect(screen.getByTestId("graph-node-concat_copy")).toBeInTheDocument();
    });

    // Delete the duplicated node
    const deleteBtn = screen.getByTestId("btn-delete-node");
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(
        screen.queryByTestId("graph-node-concat_copy"),
      ).not.toBeInTheDocument();
    });

    // Original and first added concat node remain
    expect(screen.getByTestId("graph-node-echo")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
  });

  it("starts in Clean Blueprint mode and switches to Run Inspection mode with diff badges when a run is selected (Task 6.20)", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);
    vi.mocked(client.fetchRuns).mockResolvedValue({
      runs: [
        {
          id: "20261120-120000-run1",
          workflow_path: "examples/workflows/sample.yaml",
          workflow_sha256: "sha1",
          status: "SUCCESS",
          cancel_requested: false,
          pinned: false,
          created_at: 1700000000,
          started_at: 1700000000,
          finished_at: 1700000005,
        },
      ],
    });
    vi.mocked(client.fetchRunState).mockResolvedValue({
      id: "20261120-120000-run1",
      workflow_path: "examples/workflows/sample.yaml",
      workflow_sha256: "sha1",
      status: "SUCCESS",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: 1700000000,
      started_at: 1700000000,
      finished_at: 1700000005,
      nodes: {
        echo: {
          node_id: "echo",
          status: "SUCCESS",
          cache_hit: true,
          attempt: 1,
        },
      },
      checkpoints: [],
      stage_gates: {},
      workflow_snapshot: {
        version: 1,
        name: "sample_wf",
        nodes: {
          echo: {
            op: "standard_io/demo:Echo",
            title: "Echo one",
            stage: "main",
            inputs: { text: "older-run-value" },
          },
        },
      },
    });

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/sample.yaml" />
      </RouterProvider>,
    );

    const echoNode = await screen.findByTestId("graph-node-echo");
    // In Editor mode (Clean Blueprint), the node status is IDLE even though a run exists
    expect(echoNode).toHaveAttribute("data-node-status", "IDLE");
    expect(screen.queryByTestId("run-mode-hud")).not.toBeInTheDocument();

    // Wait for the run item to appear in the Left Dock RunsHistoryPane
    const runItem = await screen.findByTestId(
      "run-history-item-20261120-120000-run1",
    );
    fireEvent.click(runItem);

    // Selecting a run activates Run Inspection Mode:
    // 1. HUD banner appears with Return to Editor button
    // 2. Operations palette collapses automatically
    // 3. Node displays the run's SUCCESS status AND a DIFF badge because "hello" !== "older-run-value"
    await waitFor(() => {
      expect(screen.getByTestId("run-mode-hud")).toBeInTheDocument();
      expect(screen.getByTestId("graph-node-echo")).toHaveAttribute(
        "data-node-status",
        "SUCCESS",
      );
      expect(screen.getByTestId("graph-node-diff-echo")).toHaveTextContent(
        "DIFF",
      );
    });
    expect(screen.getByTestId("workspace-center")).toHaveClass(
      "is-inspecting-run",
    );
    expect(screen.getByTestId("op-palette")).toHaveClass("is-collapsed");

    // Clicking Return to Editor restores Clean Blueprint mode and expands Operations palette
    fireEvent.click(screen.getByTestId("btn-return-to-editor"));
    await waitFor(() => {
      expect(screen.queryByTestId("run-mode-hud")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("graph-node-echo")).toHaveAttribute(
      "data-node-status",
      "IDLE",
    );
    expect(screen.getByTestId("op-palette")).toHaveClass("is-expanded");
  });

  describe("WorkflowEditor history (Undo/Redo)", () => {
    it("handles undo and redo via toolbar buttons and keyboard shortcuts", async () => {
      vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
      vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);

      render(
        <RouterProvider>
          <WorkflowEditor workflowPath="examples/workflows/sample.yaml" />
        </RouterProvider>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("graph-node-echo")).toBeInTheDocument();
      });

      const undoBtn = screen.getByTestId("btn-undo");
      const redoBtn = screen.getByTestId("btn-redo");
      const saveBtn = screen.getByTestId("btn-save-workflow");

      // Initially, clean state: cannot undo, cannot redo, not dirty
      expect(undoBtn).toBeDisabled();
      expect(redoBtn).toBeDisabled();
      expect(saveBtn).not.toHaveClass("primary");

      // Add a Concat node
      fireEvent.click(screen.getByTestId("palette-op-standard_io/text:Concat"));
      await waitFor(() => {
        expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
      });

      // After adding node: can undo, cannot redo, dirty
      expect(undoBtn).not.toBeDisabled();
      expect(redoBtn).toBeDisabled();
      expect(saveBtn).toHaveClass("primary");

      // Click Undo button
      fireEvent.click(undoBtn);
      await waitFor(() => {
        expect(screen.queryByTestId("graph-node-concat")).not.toBeInTheDocument();
      });
      // Back to initial snapshot: cannot undo, can redo, not dirty!
      expect(undoBtn).toBeDisabled();
      expect(redoBtn).not.toBeDisabled();
      expect(saveBtn).not.toHaveClass("primary");

      // Click Redo button
      fireEvent.click(redoBtn);
      await waitFor(() => {
        expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
      });
      expect(undoBtn).not.toBeDisabled();
      expect(redoBtn).toBeDisabled();
      expect(saveBtn).toHaveClass("primary");

      // Test keyboard shortcut Ctrl+Z (or Cmd+Z) for Undo
      fireEvent.keyDown(window, { key: "z", ctrlKey: true });
      await waitFor(() => {
        expect(screen.queryByTestId("graph-node-concat")).not.toBeInTheDocument();
      });
      expect(undoBtn).toBeDisabled();
      expect(redoBtn).not.toBeDisabled();

      // Test keyboard shortcut Ctrl+Shift+Z for Redo
      fireEvent.keyDown(window, { key: "z", ctrlKey: true, shiftKey: true });
      await waitFor(() => {
        expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
      });
      expect(undoBtn).not.toBeDisabled();
      expect(redoBtn).toBeDisabled();

      // Test keyboard shortcut Ctrl+Y for Redo after undoing
      fireEvent.keyDown(window, { key: "z", metaKey: true });
      await waitFor(() => {
        expect(screen.queryByTestId("graph-node-concat")).not.toBeInTheDocument();
      });
      fireEvent.keyDown(window, { key: "y", metaKey: true });
      await waitFor(() => {
        expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
      });
      expect(undoBtn).not.toBeDisabled();
      expect(redoBtn).toBeDisabled();
    });

    it("does not trigger canvas undo when typing in an input element", async () => {
      vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
      vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);

      render(
        <RouterProvider>
          <WorkflowEditor workflowPath="examples/workflows/sample.yaml" />
        </RouterProvider>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("graph-node-echo")).toBeInTheDocument();
      });

      // Add a node so past history is non-empty
      fireEvent.click(screen.getByTestId("palette-op-standard_io/text:Concat"));
      await waitFor(() => {
        expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();
      });

      // Create an input element simulating user typing in an inspector field
      const input = document.createElement("input");
      document.body.appendChild(input);
      input.focus();

      // Fire Ctrl+Z targeted at the input element
      fireEvent.keyDown(input, { key: "z", ctrlKey: true });

      // Node should NOT be undone because focus was inside an input
      expect(screen.getByTestId("graph-node-concat")).toBeInTheDocument();

      document.body.removeChild(input);
    });
  });
});
