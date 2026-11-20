import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OpEntry, RunState, Workflow } from "../api/types.gen";
import { NodeInspector } from "./NodeInspector";

vi.mock("../api/client", () => ({
  uploadFile: vi.fn().mockResolvedValue({ path: ".plynx/uploads/sample.txt" }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const OPS_MAP: Record<string, OpEntry> = {
  "pack/mod:Producer": {
    id: "pack/mod:Producer",
    pack: "pack",
    module: "mod",
    name: "Producer",
    kind: "class",
    title: "Producer",
    category: "Demo",
    cacheable: true,
    description: "Produces text.",
    inputs: [],
    outputs: [{ name: "text", type: "str", media: null }],
    source: "mod.py",
    valid: true,
    error: null,
  },
  "pack/mod:RichOp": {
    id: "pack/mod:RichOp",
    pack: "pack",
    module: "mod",
    name: "RichOp",
    kind: "class",
    title: "Rich Op",
    category: "Demo",
    cacheable: true,
    description: "Op exercising all registry input types.",
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
      {
        name: "mode",
        type: "str",
        media: null,
        options: ["fast", "accurate"],
        min: null,
        max: null,
        step: null,
        required: false,
        default: "fast",
      },
      {
        name: "count",
        type: "int",
        media: null,
        options: null,
        min: 1,
        max: 10,
        step: 1,
        required: false,
        default: 3,
      },
      {
        name: "enabled",
        type: "bool",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: false,
      },
      {
        name: "config",
        type: "json",
        media: null,
        options: null,
        min: null,
        max: null,
        step: null,
        required: false,
        default: null,
      },
    ],
    outputs: [
      { name: "summary", type: "str", media: null },
      { name: "report", type: "file", media: "text/markdown" },
    ],
    source: "mod.py",
    valid: true,
    error: null,
  },
};

const WORKFLOW: Workflow = {
  version: 1,
  name: "inspector_test",
  stages: {
    s1: { title: "Stage 1", require_approval: false },
    s2: { title: "Stage 2", require_approval: false },
  },
  nodes: {
    producer: {
      op: "pack/mod:Producer",
      stage: "s1",
      inputs: {},
    },
    rich: {
      op: "pack/mod:RichOp",
      title: "Rich Node",
      stage: "s2",
      inputs: {
        text: { from_node: "producer", output: "text" },
        mode: "fast",
        count: 5,
        enabled: true,
      },
    },
  },
};

const RUN_STATE: RunState = {
  id: "20261118_003000_123456",
  workflow_path: "examples/workflows/demo.yaml",
  workflow_sha256: "deadbeef",
  status: "SUCCESS",
  run_inputs: {},
  owner_pid: null,
  cancel_requested: false,
  pinned: false,
  created_at: 1731800000,
  nodes: {
    producer: {
      node_id: "producer",
      status: "SUCCESS",
      cache_hit: false,
      attempt: 1,
    },
    rich: {
      node_id: "rich",
      status: "SUCCESS",
      cache_hit: false,
      attempt: 1,
    },
  },
  checkpoints: [],
  stage_gates: {},
};

describe("NodeInspector component (Task 6.11)", () => {
  it("edits registry-typed literals (enum, bounded int, bool, json)", () => {
    const onUpdateNodeSpec = vi.fn();

    render(
      <NodeInspector
        nodeId="rich"
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        onUpdateNodeSpec={onUpdateNodeSpec}
      />,
    );

    // Enum select
    fireEvent.change(screen.getByTestId("inspector-input-mode"), {
      target: { value: "accurate" },
    });
    expect(onUpdateNodeSpec).toHaveBeenCalledTimes(1);
    const updater1 = onUpdateNodeSpec.mock.calls[0][1];
    expect(updater1(WORKFLOW.nodes!.rich).inputs?.mode).toBe("accurate");

    // Bounded numeric slider + input
    expect(screen.getByTestId("inspector-input-count-slider")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("inspector-input-count"), {
      target: { value: "8" },
    });
    const updater2 = onUpdateNodeSpec.mock.calls[1][1];
    expect(updater2(WORKFLOW.nodes!.rich).inputs?.count).toBe(8);

    // Boolean checkbox
    fireEvent.click(screen.getByTestId("inspector-input-enabled"));
    const updater3 = onUpdateNodeSpec.mock.calls[2][1];
    expect(updater3(WORKFLOW.nodes!.rich).inputs?.enabled).toBe(false);

    // JSON object input
    fireEvent.change(screen.getByTestId("inspector-input-config"), {
      target: { value: '{"k": 42}' },
    });
    const updater4 = onUpdateNodeSpec.mock.calls[3][1];
    expect(updater4(WORKFLOW.nodes!.rich).inputs?.config).toEqual({ k: 42 });
  });

  it("unbinds an existing reference and binds an upstream output reference", () => {
    const onUnbind = vi.fn();
    const onBind = vi.fn();

    const { rerender } = render(
      <NodeInspector
        nodeId="rich"
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        onUnbindInput={onUnbind}
        onBindReference={onBind}
      />,
    );

    // Currently bound to $producer.text
    expect(screen.getByTestId("inspector-ref-text")).toHaveTextContent(
      "$producer.text",
    );
    fireEvent.click(screen.getByTestId("inspector-unbind-text"));
    expect(onUnbind).toHaveBeenCalledWith("rich", "text");

    // After unbinding, bind dropdown lets user wire back to producer.text
    const unboundWorkflow: Workflow = {
      ...WORKFLOW,
      nodes: {
        ...WORKFLOW.nodes,
        rich: {
          ...WORKFLOW.nodes!.rich,
          inputs: { mode: "fast" },
        },
      },
    };
    rerender(
      <NodeInspector
        nodeId="rich"
        workflow={unboundWorkflow}
        opsMap={OPS_MAP}
        onUnbindInput={onUnbind}
        onBindReference={onBind}
      />,
    );

    fireEvent.change(screen.getByTestId("inspector-bind-text"), {
      target: { value: "producer.text" },
    });
    expect(onBind).toHaveBeenCalledWith("rich", "text", "producer", "text");
  });

  it("triggers artifact preview for completed node outputs", () => {
    const onPreview = vi.fn();

    render(
      <NodeInspector
        nodeId="rich"
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        runState={RUN_STATE}
        onPreviewArtifact={onPreview}
      />,
    );

    fireEvent.click(screen.getByTestId("inspector-preview-output-report"));
    expect(onPreview).toHaveBeenCalledWith({
      title: "rich.report",
      url: "/api/v1/runs/20261118_003000_123456/nodes/rich/outputs/report",
      mediaType: "text/markdown",
      filename: "rich-report",
    });

    fireEvent.click(screen.getByTestId("inspector-preview-output-summary"));
    expect(onPreview).toHaveBeenCalledWith({
      title: "rich.summary",
      url: "/api/v1/runs/20261118_003000_123456/nodes/rich/outputs/summary",
      mediaType: "application/json",
      filename: "rich-summary.json",
    });
  });

  it("inspects a node that was removed from workflow but exists in run snapshot", () => {
    const wfWithoutRich: Workflow = {
      ...WORKFLOW,
      nodes: {
        producer: WORKFLOW.nodes!.producer,
      },
    };

    const runDiff = {
      nodeId: "rich",
      status: "new_in_run" as const,
      opChanged: false,
      runOp: "pack/mod:RichOp",
      changedInputs: {},
    };

    render(
      <NodeInspector
        nodeId="rich"
        workflow={wfWithoutRich}
        opsMap={OPS_MAP}
        runState={RUN_STATE}
        nodeDiff={runDiff}
      />,
    );

    expect(screen.getByText("Properties of Rich Op")).toBeDefined();
    expect(screen.getByTestId("inspector-node-diff")).toBeDefined();
    expect(
      screen.getByText(
        "This operation was executed in this run, but is not present in the current workflow.",
      ),
    ).toBeDefined();

    const titleInput = screen.getByTestId("inspector-node-title");
    expect(titleInput).toBeDisabled();
  });

  it("inspects a selected stage, allows editing title and toggling approval gate", () => {
    const handleUpdateStage = vi.fn();
    const handleDeleteStage = vi.fn();
    const handleReorderStages = vi.fn().mockReturnValue({ success: true });

    render(
      <NodeInspector
        nodeId={undefined}
        selectedStageId="s1"
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        onUpdateStage={handleUpdateStage}
        onDeleteStage={handleDeleteStage}
        onReorderStages={handleReorderStages}
      />,
    );

    expect(screen.getByTestId("stage-inspector")).toBeDefined();
    expect(screen.getByText("Stage: Stage 1")).toBeDefined();

    // Title editing
    const titleInput = screen.getByTestId("inspector-stage-title");
    fireEvent.change(titleInput, { target: { value: "User Input" } });
    expect(handleUpdateStage).toHaveBeenCalledWith("s1", {
      title: "User Input",
    });

    // Approval gate checkbox
    const gateCheckbox = screen.getByTestId("inspector-stage-gate-checkbox");
    fireEvent.click(gateCheckbox);
    expect(handleUpdateStage).toHaveBeenCalledWith("s1", {
      require_approval: true,
    });

    // Reorder stage
    const moveLaterBtn = screen.getByTestId("btn-stage-move-later");
    fireEvent.click(moveLaterBtn);
    expect(handleReorderStages).toHaveBeenCalled();
  });

  it("allows adding a new stage from Workflow Properties", () => {
    const handleAddStage = vi.fn();

    render(
      <NodeInspector
        nodeId={undefined}
        selectedStageId={undefined}
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        onAddStage={handleAddStage}
      />,
    );

    expect(screen.getByText("Properties of inspector_test")).toBeDefined();

    // Click Add Stage
    const addStageBtn = screen.getByTestId("btn-add-stage-workflow");
    fireEvent.click(addStageBtn);

    const input = screen.getByTestId("input-new-stage-title");
    fireEvent.change(input, { target: { value: "Processing Stage" } });

    const submitBtn = screen.getByTestId("btn-submit-add-stage");
    fireEvent.click(submitBtn);

    expect(handleAddStage).toHaveBeenCalledWith(
      "processing_stage",
      "Processing Stage",
      { requireApproval: false },
    );
  });
});
