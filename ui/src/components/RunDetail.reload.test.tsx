import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { applyRunEvent } from "../api/reducer";
import type {
  OpEntry,
  RunEvent,
  RunState,
  WorkflowDocument,
} from "../api/types.gen";
import { RouterProvider } from "../router/Router";
import { RunDetail } from "./RunDetail";

vi.mock("../api/client", () => ({
  fetchOps: vi.fn(),
  fetchRunState: vi.fn(),
  fetchWorkflow: vi.fn(),
  subscribeRunEvents: vi.fn(),
  cancelRun: vi.fn(),
  resumeRun: vi.fn(),
  answerCheckpoint: vi.fn(),
  approveStage: vi.fn(),
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
  window.sessionStorage.clear();
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
    description: "",
    inputs: [],
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
];

const MOCK_DOC: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "foo_or_woo",
    stages: {
      ask: { title: "1. Ask", require_approval: false },
      print: { title: "2. Print", require_approval: false },
    },
    nodes: {
      pick: { op: "standard_io/demo:AskFooOrWoo", stage: "ask", inputs: {} },
      echo: {
        op: "standard_io/demo:Echo",
        stage: "print",
        inputs: { text: { from_node: "pick", output: "choice" } },
      },
    },
  },
  layout: null,
};

describe("RunDetail reload behavior (Task 6.13)", () => {
  it("hydrates from SQLite first during an active run, preserves Graph mode across reload, and applies live SSE", async () => {
    const runId = "20261118_003500_active";
    let sseHandler: ((ev: RunEvent) => void) | undefined;

    const runningState: RunState = {
      id: runId,
      workflow_path: "examples/workflows/foo_or_woo.yaml",
      workflow_sha256: "abc",
      status: "RUNNING",
      run_inputs: {},
      owner_pid: 4242,
      cancel_requested: false,
      pinned: false,
      created_at: 1731800000,
      started_at: 1731800001,
      nodes: {
        pick: { node_id: "pick", status: "RUNNING", cache_hit: false, attempt: 1, warnings: [] },
        echo: { node_id: "echo", status: "PENDING", cache_hit: false, attempt: 0, warnings: [] },
      },
      checkpoints: [],
      stage_gates: {},
    };

    vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);
    vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
    vi.mocked(client.fetchRunState).mockResolvedValue(runningState);
    vi.mocked(client.subscribeRunEvents).mockImplementation((_id, cb) => {
      sseHandler = cb;
      return () => {};
    });

    const { unmount } = render(
      <RouterProvider>
        <RunDetail runId={runId} />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-status-badge")).toHaveTextContent("RUNNING");
    });

    // Switch to Graph view
    fireEvent.click(screen.getByTestId("view-toggle-graph"));
    await waitFor(() => {
      expect(screen.getByTestId("graph-view")).toBeInTheDocument();
    });

    // Simulate full browser reload (unmount + fresh mount)
    unmount();

    render(
      <RouterProvider>
        <RunDetail runId={runId} />
      </RouterProvider>,
    );

    // Restores Graph view and live RUNNING status from SQLite
    await waitFor(() => {
      expect(screen.getByTestId("graph-view")).toBeInTheDocument();
      expect(screen.getByTestId("graph-node-status-pick")).toHaveTextContent("RUNNING");
    });

    // Subsequent SSE updates still flow in after reload
    act(() => {
      sseHandler?.({
        seq: 5,
        ts: 1731800005,
        type: "node_status",
        data: {
          run_id: runId,
          node_id: "pick",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
        warnings: [],
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("graph-node-status-pick")).toHaveTextContent("SUCCESS");
    });
  });

  it("restores open checkpoint from SQLite on refresh and ignores duplicate replay of already-resolved checkpoints", async () => {
    const runId = "20261118_003500_checkp";
    let sseHandler: ((ev: RunEvent) => void) | undefined;

    const waitingState: RunState = {
      id: runId,
      workflow_path: "examples/workflows/foo_or_woo.yaml",
      workflow_sha256: "abc",
      status: "WAITING_FOR_USER",
      run_inputs: {},
      owner_pid: 4242,
      cancel_requested: false,
      pinned: false,
      created_at: 1731800000,
      nodes: {
        pick: {
          node_id: "pick",
          status: "WAITING_FOR_USER",
          cache_hit: false,
          attempt: 1,
        warnings: [],
        },
        echo: { node_id: "echo", status: "PENDING", cache_hit: false, attempt: 0, warnings: [] },
      },
      checkpoints: [
        {
          node_id: "pick",
          checkpoint_id: "cp_0",
          question: "foo or woo?",
          options: ["foo", "woo"],
          allow_freeform: false,
          questions: [],
          answer: null,
          created_at: 1731800002,
          answered_at: null,
        },
      ],
      stage_gates: {},
    };

    vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);
    vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
    vi.mocked(client.fetchRunState).mockResolvedValue(waitingState);
    vi.mocked(client.subscribeRunEvents).mockImplementation((_id, cb) => {
      sseHandler = cb;
      return () => {};
    });

    render(
      <RouterProvider>
        <RunDetail runId={runId} />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-status-badge")).toHaveTextContent(
        "WAITING_FOR_USER",
      );
      expect(screen.getByTestId("checkpoint-card-cp_0")).toBeInTheDocument();
      expect(screen.getByText("foo or woo?")).toBeInTheDocument();
    });

    // Resolve checkpoint via SSE
    act(() => {
      sseHandler?.({
        seq: 4,
        ts: 1731800010,
        type: "checkpoint_resolved",
        data: { run_id: runId, node_id: "pick", checkpoint_id: "cp_0" },
      });
    });

    await waitFor(() => {
      expect(screen.queryByTestId("checkpoint-card-cp_0")).not.toBeInTheDocument();
    });

    // Verify reducer ignores historical node_checkpoint replay for an already-resolved checkpoint
    const resolvedState: RunState = {
      ...waitingState,
      checkpoints: [
        {
          ...waitingState.checkpoints[0],
          answer: "foo",
          answered_at: 1731800010,
        },
      ],
    };
    const afterReplay = applyRunEvent(resolvedState, {
      seq: 3,
      ts: 1731800002,
      type: "node_checkpoint",
      data: {
        run_id: runId,
        node_id: "pick",
        checkpoint_id: "cp_0",
        question: "foo or woo?",
        options: ["foo", "woo"],
        allow_freeform: false,
        questions: [],
      },
    });
    expect(afterReplay.checkpoints[0].answered_at).toBe(1731800010);
  });

  it("restores FAILED (engine_died) after server restart, hides dead checkpoints, and reconnects on Resume Run", async () => {
    const runId = "20261118_003500_reaped";
    const reapedState: RunState = {
      id: runId,
      workflow_path: "examples/workflows/foo_or_woo.yaml",
      workflow_sha256: "abc",
      status: "FAILED",
      run_inputs: {},
      owner_pid: null,
      cancel_requested: false,
      pinned: false,
      created_at: 1731800000,
      finished_at: 1731800020,
      error: "engine_died",
      nodes: {
        pick: {
          node_id: "pick",
          status: "WAITING_FOR_USER",
          cache_hit: false,
          attempt: 1,
        warnings: [],
        },
        echo: { node_id: "echo", status: "PENDING", cache_hit: false, attempt: 0, warnings: [] },
      },
      checkpoints: [
        {
          node_id: "pick",
          checkpoint_id: "cp_0",
          question: "foo or woo?",
          options: ["foo", "woo"],
          allow_freeform: false,
          questions: [],
          answer: null,
          created_at: 1731800002,
          answered_at: null,
        },
      ],
      stage_gates: {},
    };

    const resumedState: RunState = {
      ...reapedState,
      status: "RUNNING",
      owner_pid: 9001,
      finished_at: null,
      error: null,
    };

    vi.mocked(client.fetchOps).mockResolvedValue(MOCK_OPS);
    vi.mocked(client.fetchWorkflow).mockResolvedValue(MOCK_DOC);
    vi.mocked(client.fetchRunState)
      .mockResolvedValueOnce(reapedState)
      .mockResolvedValueOnce(resumedState);
    vi.mocked(client.resumeRun).mockResolvedValue({ run_id: runId });
    vi.mocked(client.subscribeRunEvents).mockReturnValue(() => {});

    render(
      <RouterProvider>
        <RunDetail runId={runId} />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("run-status-badge")).toHaveTextContent("FAILED");
      expect(screen.getByTestId("run-error-banner")).toHaveTextContent(
        "engine_died",
      );
    });

    // Terminal FAILED run must NOT open SSE or render dead interactive checkpoint cards
    expect(client.subscribeRunEvents).not.toHaveBeenCalled();
    expect(screen.queryByTestId("checkpoint-card-cp_0")).not.toBeInTheDocument();

    // Clicking Resume Run claims ownership, re-fetches SQLite state, and connects SSE
    fireEvent.click(screen.getByRole("button", { name: "Resume Run" }));

    await waitFor(() => {
      expect(client.resumeRun).toHaveBeenCalledWith(runId);
      expect(screen.getByTestId("run-status-badge")).toHaveTextContent("RUNNING");
      expect(client.subscribeRunEvents).toHaveBeenCalledTimes(1);
    });
  });
});
