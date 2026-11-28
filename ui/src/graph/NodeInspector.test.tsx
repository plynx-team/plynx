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
    side_effects: "none",
    description: "Produces text.",
    inputs: [],
    outputs: [{ name: "text", type: "str", media: null }],
    allow_extra_inputs: false,
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
    side_effects: "none",
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
    allow_extra_inputs: false,
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
    warnings: [],
    },
    rich: {
      node_id: "rich",
      status: "SUCCESS",
      cache_hit: false,
      attempt: 1,
    warnings: [],
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

  it("renders modified diff with Editor as newer (- Run baseline, + Editor current)", () => {
    const modifiedDiff = {
      nodeId: "rich",
      status: "modified" as const,
      opChanged: true,
      editorOp: "pack/mod:RichOp",
      runOp: "pack/mod:RichOpV2",
      changedInputs: {
        mode: {
          portName: "mode",
          editorValue: "fast",
          runValue: "accurate",
        },
      },
    };

    render(
      <NodeInspector
        nodeId="rich"
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        runState={RUN_STATE}
        nodeDiff={modifiedDiff}
      />,
    );

    expect(screen.getByTestId("inspector-node-diff")).toBeDefined();
    expect(screen.getByText("Editor Changes vs. Run")).toBeDefined();
    expect(screen.getByText("- Run op: pack/mod:RichOpV2")).toBeDefined();
    expect(screen.getByText("+ Editor op: pack/mod:RichOp")).toBeDefined();
    expect(screen.getByText('- Run: "accurate"')).toBeDefined();
    expect(screen.getByText('+ Editor: "fast"')).toBeDefined();
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

  it("allows reordering stages directly from Workflow Properties", () => {
    const handleReorderStages = vi.fn().mockReturnValue({ success: true });

    render(
      <NodeInspector
        nodeId={undefined}
        selectedStageId={undefined}
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        onReorderStages={handleReorderStages}
      />,
    );

    const moveDownBtn = screen.getByTestId("btn-workflow-stage-move-down-s1");
    fireEvent.click(moveDownBtn);
    expect(handleReorderStages).toHaveBeenCalledWith(["s2", "s1"]);
  });

  it("renders help icon and tooltip for inputs with a description", () => {
    const opsWithHelp = {
      ...OPS_MAP,
      "pack/mod:RichOp": {
        ...OPS_MAP["pack/mod:RichOp"],
        inputs: [
          {
            ...OPS_MAP["pack/mod:RichOp"].inputs[0],
            description: "Detailed input text description for LLM prompt.",
          },
          ...OPS_MAP["pack/mod:RichOp"].inputs.slice(1),
        ],
      },
    };

    render(
      <NodeInspector
        nodeId="rich"
        workflow={WORKFLOW}
        opsMap={opsWithHelp}
      />,
    );

    const helpIcon = screen.getByTestId("inspector-port-help-text");
    expect(helpIcon).toBeDefined();
    expect(helpIcon).toHaveAttribute(
      "title",
      "Detailed input text description for LLM prompt.",
    );
  });

  it("supports adding and removing dynamic extra input ports when allow_extra_inputs is true (Task 3.3)", () => {
    const handleUpdateNodeSpec = vi.fn();
    const opsWithExtra = {
      ...OPS_MAP,
      "pack/mod:VariadicOp": {
        id: "pack/mod:VariadicOp",
        pack: "pack",
        module: "mod",
        name: "VariadicOp",
        kind: "class" as const,
        title: "Variadic Op",
        category: "Demo",
        cacheable: true,
        side_effects: "none" as const,
        description: "Op accepting extra inputs.",
        inputs: [],
        outputs: [],
        allow_extra_inputs: true,
        extra_inputs_type: {
          name: "tracks",
          type: "file" as const,
          media: "audio/wav",
          options: null,
          min: null,
          max: null,
          step: null,
          required: false,
          default: null,
        },
        source: "mod.py",
        valid: true,
        error: null,
      },
    };

    const wf: Workflow = {
      version: 1,
      name: "variadic_test",
      nodes: {
        var_node: {
          op: "pack/mod:VariadicOp",
          stage: "s1",
          inputs: {
            track_1: "audio1.wav",
          },
        },
      },
      stages: {
        s1: { title: "Stage 1", require_approval: false },
      },
    };

    render(
      <NodeInspector
        nodeId="var_node"
        workflow={wf}
        opsMap={opsWithExtra}
        onUpdateNodeSpec={handleUpdateNodeSpec}
      />,
    );

    // Dynamic port track_1 should be rendered with extra badge and remove button
    expect(screen.getByText("track_1")).toBeInTheDocument();
    expect(screen.getByText("extra")).toBeInTheDocument();
    const removeBtn = screen.getByTestId("inspector-remove-extra-track_1");
    expect(removeBtn).toBeInTheDocument();

    // Clicking remove should delete the port
    fireEvent.click(removeBtn);
    expect(handleUpdateNodeSpec).toHaveBeenCalled();

    // Add input button is visible
    const addInputBtn = screen.getByTestId("btn-add-extra-input");
    expect(addInputBtn).toBeInTheDocument();
    fireEvent.click(addInputBtn);

    // Form is displayed
    const inputField = screen.getByTestId("input-new-extra-port-name");
    const submitBtn = screen.getByTestId("btn-submit-add-extra-input");

    // Invalid snake_case
    fireEvent.change(inputField, { target: { value: "Track 2" } });
    fireEvent.click(submitBtn);
    expect(screen.getByText("Port name must be snake_case (e.g. track_1)")).toBeInTheDocument();

    // Valid snake_case
    fireEvent.change(inputField, { target: { value: "track_2" } });
    fireEvent.click(submitBtn);
    expect(handleUpdateNodeSpec).toHaveBeenCalled();
  });

  it("renders per-node warnings and open batch checkpoints in PropertiesBar", () => {
    const runWithWarningsAndCp: RunState = {
      ...RUN_STATE,
      status: "WAITING_FOR_USER",
      nodes: {
        ...RUN_STATE.nodes,
        rich: {
          ...RUN_STATE.nodes.rich,
          status: "WAITING_FOR_USER",
          warnings: ["Detected French language (lang=fr)"],
        },
      },
      checkpoints: [
        {
          node_id: "rich",
          checkpoint_id: "cp_0",
          question: "Target track?",
          options: null,
          allow_freeform: false,
          questions: [
            {
              id: "role",
              header: "Track",
              question: "Target track?",
              options: ["ML", "Backend"],
              multi_select: false,
              allow_freeform: false,
            },
          ],
          answer: null,
          created_at: 1700000000,
          answered_at: null,
        },
      ],
    };

    render(
      <NodeInspector
        nodeId="rich"
        workflow={WORKFLOW}
        opsMap={OPS_MAP}
        runState={runWithWarningsAndCp}
        readOnly={true}
      />,
    );

    expect(screen.getByTestId("inspector-warnings-badge")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-node-warnings")).toBeInTheDocument();
    expect(
      screen.getByText("Detected French language (lang=fr)"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("inspector-checkpoint-cp_0")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "ML" })).toBeInTheDocument();
  });

  it("displays write (external) badge in PropertiesBar when op declares side_effects === 'write'", () => {
    const opsWithWrite: Record<string, OpEntry> = {
      ...OPS_MAP,
      "pack/mod:SendWebhook": {
        id: "pack/mod:SendWebhook",
        pack: "pack",
        module: "mod",
        name: "SendWebhook",
        kind: "class",
        title: "Send Webhook",
        category: "Network",
        cacheable: false,
        side_effects: "write",
        description: "Posts external webhook.",
        inputs: [],
        outputs: [],
        allow_extra_inputs: false,
        source: "mod.py",
        valid: true,
        error: null,
      },
    };
    const wf: Workflow = {
      version: 1,
      name: "write_inspector_test",
      nodes: {
        hook: { op: "pack/mod:SendWebhook", stage: "main", inputs: {} },
      },
    };

    render(<NodeInspector nodeId="hook" workflow={wf} opsMap={opsWithWrite} />);
    expect(screen.getByTestId("inspector-side-effects")).toHaveTextContent(
      "write (external)",
    );
  });
});
