import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpEntry, WorkflowDocument } from "../api/types.gen";
import { RouterProvider } from "../router/Router";
import type { GraphViewProps } from "./GraphView";
import { inputHandleId, outputHandleId } from "./types";

vi.mock("../api/client", () => ({
  fetchWorkflow: vi.fn(),
  fetchOps: vi.fn(),
  fetchRuns: vi.fn().mockResolvedValue({ runs: [] }),
  fetchRunState: vi.fn(),
  saveWorkflow: vi.fn(),
}));

vi.mock("./GraphView", () => ({
  GraphView: ({
    workflow,
    onConnect,
    onSelectEdge,
    onWireDropOnPane,
  }: GraphViewProps) => {
    const edges: Array<string> = [];
    for (const [targetId, spec] of Object.entries(workflow?.nodes ?? {})) {
      for (const [port, val] of Object.entries(spec.inputs ?? {})) {
        if (
          typeof val === "object" &&
          val !== null &&
          "from_node" in val &&
          "output" in val
        ) {
          const ref = val as { from_node: string; output: string };
          edges.push(`${ref.from_node}.${ref.output}->${targetId}.${port}`);
        }
      }
    }
    return (
      <div data-testid="mock-graph-view">
        <div data-testid="edge-list">{edges.join(",")}</div>
        <button
          type="button"
          data-testid="trigger-valid-wire"
          onClick={() =>
            onConnect?.({
              source: "pick",
              sourceHandle: outputHandleId("choice"),
              target: "echo",
              targetHandle: inputHandleId("text"),
            })
          }
        >
          Valid Wire
        </button>
        <button
          type="button"
          data-testid="trigger-backward-wire"
          onClick={() =>
            onConnect?.({
              source: "echo",
              sourceHandle: outputHandleId("text"),
              target: "pick",
              targetHandle: inputHandleId("prompt"),
            })
          }
        >
          Backward Wire
        </button>
        <button
          type="button"
          data-testid="trigger-type-mismatch"
          onClick={() =>
            onConnect?.({
              source: "pick",
              sourceHandle: outputHandleId("choice"),
              target: "reader",
              targetHandle: inputHandleId("path"),
            })
          }
        >
          Type Mismatch
        </button>
        <button
          type="button"
          data-testid="trigger-media-mismatch"
          onClick={() =>
            onConnect?.({
              source: "writer",
              sourceHandle: outputHandleId("file"),
              target: "pdf_consumer",
              targetHandle: inputHandleId("doc"),
            })
          }
        >
          Media Mismatch
        </button>
        <button
          type="button"
          data-testid="select-first-edge"
          onClick={() => onSelectEdge?.(edges[0])}
        >
          Select Edge
        </button>
        <button
          type="button"
          data-testid="trigger-wire-drop-on-pane"
          onClick={() =>
            onWireDropOnPane?.({
              originNodeId: "pick",
              originHandleId: outputHandleId("choice"),
              handleType: "source",
              screenPos: { x: 100, y: 100 },
              flowPos: { x: 300, y: 300 },
              stageId: "ask",
            })
          }
        >
          Trigger Wire Drop
        </button>
      </div>
    );
  },
}));

import * as client from "../api/client";
import { WorkflowEditor } from "./WorkflowEditor";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  window.location.hash = "#/editor/examples/workflows/wire_demo.yaml?view=graph";
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
  {
    id: "standard_io/demo:Echo",
    pack: "standard_io",
    module: "demo",
    name: "Echo",
    kind: "class",
    title: "Echo",
    category: "Demo",
    cacheable: true,
    description: "",
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
    allow_extra_inputs: false,
    source: "demo.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/demo:ReadText",
    pack: "standard_io",
    module: "demo",
    name: "ReadText",
    kind: "class",
    title: "ReadText",
    category: "Files",
    cacheable: true,
    description: "",
    inputs: [
      {
        name: "path",
        type: "file",
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
    allow_extra_inputs: false,
    source: "demo.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/demo:WriteText",
    pack: "standard_io",
    module: "demo",
    name: "WriteText",
    kind: "class",
    title: "WriteText",
    category: "Files",
    cacheable: true,
    description: "",
    inputs: [],
    outputs: [{ name: "file", type: "file", media: "text/plain" }],
    allow_extra_inputs: false,
    source: "demo.py",
    valid: true,
    error: null,
  },
  {
    id: "custom/pdf:ParsePdf",
    pack: "custom",
    module: "pdf",
    name: "ParsePdf",
    kind: "class",
    title: "ParsePdf",
    category: "Files",
    cacheable: true,
    description: "",
    inputs: [
      {
        name: "doc",
        type: "file",
        media: "application/pdf",
        options: null,
        min: null,
        max: null,
        step: null,
        required: true,
        default: null,
      },
    ],
    outputs: [{ name: "text", type: "str", media: null }],
    allow_extra_inputs: false,
    source: "pdf.py",
    valid: true,
    error: null,
  },
];

const DOC: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "wire_demo",
    stages: {
      ask: { title: "1. Ask", require_approval: false },
      print: { title: "2. Print", require_approval: false },
    },
    nodes: {
      pick: { op: "standard_io/demo:AskFooOrWoo", stage: "ask", inputs: {} },
      echo: { op: "standard_io/demo:Echo", stage: "print", inputs: {} },
      reader: { op: "standard_io/demo:ReadText", stage: "print", inputs: {} },
      writer: { op: "standard_io/demo:WriteText", stage: "ask", inputs: {} },
      pdf_consumer: { op: "custom/pdf:ParsePdf", stage: "print", inputs: {} },
    },
  },
  layout: null,
};

describe("WorkflowEditor wiring & rejection reasons (Task 6.10)", () => {
  it("creates valid wires, rejects backward/type/media mismatches visibly, and disconnects edges", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(OPS);

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="examples/workflows/wire_demo.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-graph-view")).toBeInTheDocument();
    });

    // Backward stage edge rejected with visible banner
    fireEvent.click(screen.getByTestId("trigger-backward-wire"));
    expect(screen.getByTestId("wire-error-banner")).toHaveTextContent(
      "Backward stage edge",
    );
    expect(screen.getByTestId("edge-list")).toHaveTextContent("");

    // Type mismatch rejected with visible banner
    fireEvent.click(screen.getByTestId("trigger-type-mismatch"));
    expect(screen.getByTestId("wire-error-banner")).toHaveTextContent(
      "Port type mismatch",
    );
    expect(screen.getByTestId("edge-list")).toHaveTextContent("");

    // Media mismatch rejected with visible banner
    fireEvent.click(screen.getByTestId("trigger-media-mismatch"));
    expect(screen.getByTestId("wire-error-banner")).toHaveTextContent(
      "Media mismatch",
    );
    expect(screen.getByTestId("edge-list")).toHaveTextContent("");

    // Valid wire clears error and creates edge
    fireEvent.click(screen.getByTestId("trigger-valid-wire"));
    expect(screen.queryByTestId("wire-error-banner")).not.toBeInTheDocument();
    expect(screen.getByTestId("edge-list")).toHaveTextContent(
      "pick.choice->echo.text",
    );

    // Select and disconnect edge
    fireEvent.click(screen.getByTestId("select-first-edge"));
    fireEvent.click(screen.getByTestId("btn-delete-edge"));
    expect(screen.getByTestId("edge-list")).toHaveTextContent("");
  });

  it("opens QuickConnectPopover on wire drop in pane and auto-wires selected operation", async () => {
    vi.mocked(client.fetchWorkflow).mockResolvedValue(DOC);
    vi.mocked(client.fetchOps).mockResolvedValue(OPS);

    render(
      <RouterProvider>
        <WorkflowEditor workflowPath="foo_or_woo.yaml" />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("mock-graph-view")).toBeInTheDocument();
    });

    // Drop wire from pick.choice (output: str) on empty pane
    fireEvent.click(screen.getByTestId("trigger-wire-drop-on-pane"));

    expect(screen.getByTestId("quick-connect-popover")).toBeInTheDocument();

    // Echo should be visible since it has an input 'text: str'
    const echoItem = screen.getByTestId(
      "quick-connect-item-standard_io/demo:Echo-text",
    );
    expect(echoItem).toBeInTheDocument();

    // Select Echo -> text
    fireEvent.click(echoItem);

    // Popover closes
    expect(screen.queryByTestId("quick-connect-popover")).not.toBeInTheDocument();

    // Edge list should now include wire from pick.choice to the new node's text input!
    await waitFor(() => {
      expect(screen.getByTestId("edge-list").textContent).toContain("pick.choice->");
      expect(screen.getByTestId("edge-list").textContent).toContain(".text");
    });
  });
});
