import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { OpEntry, RunState, WorkflowDocument } from "../api/types.gen";
import { RunDetail } from "../components/RunDetail";
import { RouterProvider } from "../router/Router";
import { GraphView } from "./GraphView";

vi.mock("../api/client", () => ({
  fetchOps: vi.fn(),
  fetchRunState: vi.fn(),
  fetchWorkflow: vi.fn(),
  subscribeRunEvents: vi.fn(),
  cancelRun: vi.fn(),
  resumeRun: vi.fn(),
  fetchNodeLogs: vi.fn(),
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
    id: "standard_io/demo:AskFooOrWoo",
    pack: "standard_io",
    module: "demo",
    name: "AskFooOrWoo",
    kind: "class",
    title: "Ask foo or woo",
    category: "Demo",
    cacheable: false,
    description: "Ask the user to pick foo or woo.",
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
    source: "builtin_packs/standard_io/src/standard_io/demo.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/demo:Echo",
    pack: "standard_io",
    module: "demo",
    name: "Echo",
    kind: "class",
    title: "Echo text",
    category: "Demo",
    cacheable: true,
    description: "Echo text",
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
    source: "builtin_packs/standard_io/src/standard_io/demo.py",
    valid: true,
    error: null,
  },
];

const MOCK_WORKFLOW_DOC: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "foo_or_woo",
    stages: {
      ask: { title: "1. Ask", require_approval: false },
      print: { title: "2. Print", require_approval: true },
    },
    nodes: {
      pick: {
        op: "standard_io/demo:AskFooOrWoo",
        title: "Pick one",
        stage: "ask",
        inputs: { prompt: "foo or woo?" },
      },
      echo: {
        op: "standard_io/demo:Echo",
        title: "Echo result",
        stage: "print",
        inputs: { text: { from_node: "pick", output: "choice" } },
      },
    },
  },
  layout: null,
};

const MOCK_RUN_STATE: RunState = {
  id: "20261118_001500_abcdef",
  workflow_path: "examples/workflows/foo_or_woo.yaml",
  workflow_sha256: "abc123",
  status: "RUNNING",
  run_inputs: {},
  owner_pid: 999,
  cancel_requested: false,
  pinned: false,
  created_at: 1731800000,
  started_at: 1731800001,
  finished_at: null,
  error: null,
  nodes: {
    pick: {
      node_id: "pick",
      status: "SUCCESS",
      cache_hit: true,
      attempt: 1,
    },
    echo: {
      node_id: "echo",
      status: "RUNNING",
      cache_hit: false,
      attempt: 1,
    },
  },
  checkpoints: [],
  stage_gates: {},
};

describe("GraphView component (Task 6.8)", () => {
  it("renders stage group nodes, workflow nodes, live statuses, and cache hit badges", () => {
    const onSelect = vi.fn();
    render(
      <GraphView
        workflowDoc={MOCK_WORKFLOW_DOC}
        runState={MOCK_RUN_STATE}
        ops={MOCK_OPS}
        onSelectNode={onSelect}
        readOnly={true}
      />,
    );

    expect(screen.getByTestId("graph-view")).toBeInTheDocument();
    expect(screen.getByTestId("stage-group-ask")).toBeInTheDocument();
    expect(screen.getByTestId("stage-group-print")).toBeInTheDocument();
    expect(screen.getByText("1. Ask")).toBeInTheDocument();
    expect(screen.getByText("2. Print")).toBeInTheDocument();

    expect(screen.getByTestId("graph-node-pick")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-status-pick")).toHaveTextContent("SUCCESS");
    expect(screen.getByTestId("graph-node-cache-pick")).toHaveTextContent("cache hit");

    expect(screen.getByTestId("graph-node-echo")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-status-echo")).toHaveTextContent("RUNNING");
    expect(screen.getByTestId("graph-node-echo")).toHaveClass(
      "flow-node",
      "node-running-status-running",
    );
    expect(screen.getByText("foo_or_woo")).toBeInTheDocument();
  });

  it("toggles between Stepper and Graph views in RunDetail and displays live status updates", async () => {
    let emitEvent: ((ev: Parameters<Parameters<typeof client.subscribeRunEvents>[1]>[0]) => void) | undefined;

    vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);
    vi.mocked(client.fetchRunState).mockResolvedValue(MOCK_RUN_STATE);
    vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_WORKFLOW_DOC);
    vi.mocked(client.subscribeRunEvents).mockImplementation((_runId, cb) => {
      emitEvent = cb;
      return () => {};
    });

    render(
      <RouterProvider>
        <RunDetail runId={MOCK_RUN_STATE.id} />
      </RouterProvider>,
    );

    // Stepper is default
    await waitFor(() => {
      expect(screen.getByText("Workflow Stages (Stepper)")).toBeInTheDocument();
    });
    expect(screen.getByTestId("view-toggle-stepper")).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Toggle to Graph view
    fireEvent.click(screen.getByTestId("view-toggle-graph"));

    await waitFor(() => {
      expect(screen.getByText("Workflow DAG (Graph)")).toBeInTheDocument();
      expect(screen.getByTestId("graph-view")).toBeInTheDocument();
    });

    expect(screen.getByTestId("graph-node-status-echo")).toHaveTextContent("RUNNING");

    // Emit live SSE node_status update -> echo transitions to SUCCESS
    emitEvent?.({
      seq: 2,
      ts: 1731800005,
      type: "node_status",
      data: {
        run_id: MOCK_RUN_STATE.id,
        node_id: "echo",
        status: "SUCCESS",
        cache_hit: false,
        attempt: 1,
      },
    });

    await waitFor(() => {
      expect(screen.getByTestId("graph-node-status-echo")).toHaveTextContent("SUCCESS");
    });

    // Toggle back to Stepper
    fireEvent.click(screen.getByTestId("view-toggle-stepper"));
    await waitFor(() => {
      expect(screen.getByText("Workflow Stages (Stepper)")).toBeInTheDocument();
    });
  });
});
