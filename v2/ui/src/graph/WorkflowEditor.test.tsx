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
});
