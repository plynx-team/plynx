import { cleanup, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { OpEntry, RunState, Workflow } from "../api/types.gen";
import { RunInspector } from "./RunInspector";

beforeAll(() => {
  if (typeof window.ResizeObserver === "undefined") {
    class MockResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    window.ResizeObserver =
      MockResizeObserver as unknown as typeof ResizeObserver;
  }
  if (typeof window.DOMMatrixReadOnly === "undefined") {
    class MockDOMMatrixReadOnly {
      m22 = 1;
    }
    window.DOMMatrixReadOnly =
      MockDOMMatrixReadOnly as unknown as typeof DOMMatrixReadOnly;
  }
});

afterEach(() => {
  cleanup();
});

const OPS: Array<OpEntry> = [
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

const OPS_MAP: Record<string, OpEntry> = {
  "standard_io/demo:Echo": OPS[0],
};

describe("RunInspector (R4.2 snapshot fidelity)", () => {
  it("renders the run's true workflow_snapshot rather than the modified live editor workflow", () => {
    const olderSnapshot: Workflow = {
      version: 1,
      name: "Older Snapshot",
      stages: { main: { title: "Main", require_approval: false } },
      nodes: {
        legacy_node: {
          op: "standard_io/demo:Echo",
          title: "Legacy Snapshot Node",
          stage: "main",
          inputs: { text: "from snapshot" },
        },
      },
    };

    const currentEditorWorkflow: Workflow = {
      version: 1,
      name: "Current Editor",
      stages: { main: { title: "Main", require_approval: false } },
      nodes: {
        brand_new_editor_node: {
          op: "standard_io/demo:Echo",
          title: "Brand New Editor Node",
          stage: "main",
          inputs: { text: "editor only" },
        },
      },
    };

    const runState: RunState = {
      id: "run-old-1",
      workflow_path: "workflows/demo.yaml",
      workflow_sha256: "sha1",
      status: "RUNNING",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: 1700000000,
      nodes: {
        legacy_node: {
          node_id: "legacy_node",
          status: "RUNNING",
          cache_hit: false,
          attempt: 1,
        },
      },
      checkpoints: [],
      stage_gates: {},
      workflow_snapshot: olderSnapshot,
    };

    render(
      <RunInspector
        runState={runState}
        viewMode="stepper"
        ops={OPS}
        opsMap={OPS_MAP}
        editorWorkflow={currentEditorWorkflow}
        onSelectNode={vi.fn()}
        onPreviewArtifact={vi.fn()}
      />,
    );

    // Snapshot node is rendered and progress is computed from snapshot nodes only (0 of 1, not inflated by editor-only nodes)
    expect(screen.getByText("legacy_node")).toBeInTheDocument();
    expect(screen.getByText(/Legacy Snapshot Node/)).toBeInTheDocument();
    expect(screen.getByText("0 of 1 nodes completed (0%)")).toBeInTheDocument();
    expect(screen.queryByText("brand_new_editor_node")).not.toBeInTheDocument();
    expect(screen.queryByText(/Brand New Editor Node/)).not.toBeInTheDocument();
  });
});
