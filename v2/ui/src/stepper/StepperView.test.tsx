import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { StepperView } from "./StepperView";
import type { RunState, WorkflowDocument } from "../api/types.gen";

afterEach(() => {
  cleanup();
});

const mockWorkflowDoc: WorkflowDocument = {
  workflow: {
    version: 1,
    name: "Diamond Workflow",
    stages: {
      s1: { title: "1. Ingest Stage", require_approval: false },
      s2: { title: "2. Processing Stage", require_approval: true },
    },
    nodes: {
      source: {
        op: "standard_io/demo:ReadText",
        title: "Source Reader",
        stage: "s1",
      },
      branch_a: {
        op: "standard_io/demo:Echo",
        title: "Branch A",
        stage: "s2",
      },
      branch_b: {
        op: "standard_io/demo:Echo",
        title: "Branch B",
        stage: "s2",
      },
    },
  },
};

const mockRunState: RunState = {
  id: "run-diamond-123",
  workflow_path: "workflows/diamond.yaml",
  workflow_sha256: "hash",
  status: "RUNNING",
  run_inputs: {},
  cancel_requested: false,
  pinned: false,
  created_at: 1700000000,
  nodes: {
    source: {
      node_id: "source",
      status: "SUCCESS",
      cache_hit: true,
      attempt: 1,
      started_at: 1700000001,
      finished_at: 1700000002,
    },
    branch_a: {
      node_id: "branch_a",
      status: "RUNNING",
      cache_hit: false,
      attempt: 1,
      started_at: 1700000003,
    },
    branch_b: {
      node_id: "branch_b",
      status: "PENDING",
      cache_hit: false,
      attempt: 1,
    },
  },
  checkpoints: [],
  stage_gates: {
    s2: {
      stage_id: "s2",
      status: "WAITING",
      created_at: 1700000000,
    },
  },
};

describe("StepperView component (Task 6.3)", () => {
  it("renders stage cards with stage titles and progress", () => {
    render(
      <StepperView
        runState={mockRunState}
        workflowDoc={mockWorkflowDoc}
      />,
    );

    // Stage titles
    expect(screen.getByText("1. Ingest Stage")).toBeDefined();
    expect(screen.getByText("2. Processing Stage")).toBeDefined();

    // Stage progress indicators
    expect(screen.getByText("1/1 completed")).toBeDefined();
    expect(screen.getByText("0/2 completed")).toBeDefined();

    // Overall progress
    expect(screen.getByText(/1 of 3 nodes completed/)).toBeDefined();
  });

  it("renders parallel nodes with status badges and cache_hit badges", () => {
    render(
      <StepperView
        runState={mockRunState}
        workflowDoc={mockWorkflowDoc}
      />,
    );

    // Nodes in stage 1
    expect(screen.getByText("source")).toBeDefined();
    expect(screen.getByText("• Source Reader")).toBeDefined();
    expect(screen.getByTestId("cache-hit-badge")).toBeDefined();
    expect(screen.getByText("cache hit")).toBeDefined();

    // Nodes in stage 2
    expect(screen.getByText("branch_a")).toBeDefined();
    expect(screen.getByText("• Branch A")).toBeDefined();
    expect(screen.getByText("branch_b")).toBeDefined();
    expect(screen.getByText("• Branch B")).toBeDefined();

    // Node statuses
    expect(screen.getAllByText("SUCCESS").length).toBeGreaterThan(0);
    expect(screen.getAllByText("RUNNING").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PENDING").length).toBeGreaterThan(0);
  });

  it("handles node selection callback", () => {
    const onSelect = vi.fn();
    render(
      <StepperView
        runState={mockRunState}
        workflowDoc={mockWorkflowDoc}
        onSelectNode={onSelect}
      />,
    );

    fireEvent.click(screen.getByText("branch_a"));
    expect(onSelect).toHaveBeenCalledWith("branch_a");
  });

  it("renders NEW badge for operations present in run but removed from workflow", () => {
    const diff = {
      hasChanges: true,
      nodes: {
        removed_op: {
          nodeId: "removed_op",
          status: "new_in_run" as const,
          opChanged: false,
          runOp: "standard_io/demo:Echo",
          changedInputs: {},
        },
      },
      removedNodeIds: ["removed_op"],
    };

    const runStateWithRemovedOp: RunState = {
      ...mockRunState,
      nodes: {
        ...mockRunState.nodes,
        removed_op: {
          node_id: "removed_op",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
        },
      },
    };

    render(
      <StepperView
        runState={runStateWithRemovedOp}
        workflowDoc={mockWorkflowDoc}
        runDiff={diff}
      />,
    );

    expect(screen.getByText("removed_op")).toBeDefined();
    expect(screen.getByText("NEW")).toBeDefined();
  });

  it("dims inactive stages and progress when a checkpoint or stage approval gate is waiting", () => {
    render(
      <StepperView
        runState={mockRunState}
        workflowDoc={mockWorkflowDoc}
      />,
    );

    // s2 is WAITING in mockRunState, s1 is not waiting
    const s1Title = screen.getByText("1. Ingest Stage");
    const s1Wrapper = s1Title.closest(".transition-opacity");
    expect(s1Wrapper?.className).toContain("opacity-40");

    const s2Title = screen.getByText("2. Processing Stage");
    const s2Wrapper = s2Title.closest(".transition-opacity");
    expect(s2Wrapper?.className).toContain("opacity-100");
    expect(s2Wrapper?.className).not.toContain("opacity-40");

    // Progress header should also be dimmed
    const progressHeader = screen.getByText("Overall Progress").closest(".transition-opacity");
    expect(progressHeader?.className).toContain("opacity-40");
  });
});
