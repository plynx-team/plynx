import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { OpEntry, RunState, Workflow, WorkflowDocument } from "../api/types.gen";
import * as client from "../api/client";
import { RunInspector } from "../components/RunInspector";
import { RunList } from "../components/RunList";
import { RouterProvider } from "../router/Router";
import { StepperView } from "../stepper/StepperView";
import { GraphView } from "./GraphView";
import { NodeInspector } from "./NodeInspector";
import { StageInspectorPanel } from "./StageInspectorPanel";

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
  vi.restoreAllMocks();
});

const OPS: Array<OpEntry> = [
  {
    id: "standard_io/demo:Ingest",
    pack: "standard_io",
    module: "demo",
    name: "Ingest",
    kind: "class",
    title: "Ingest",
    category: "Demo",
    cacheable: true,
    description: "",
    inputs: [],
    outputs: [{ name: "text", type: "str", media: null }],
    allow_extra_inputs: false,
    source: "demo.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/demo:TranslateFr",
    pack: "standard_io",
    module: "demo",
    name: "TranslateFr",
    kind: "class",
    title: "Translate French",
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
    id: "standard_io/agent:StageSupervisor",
    pack: "standard_io",
    module: "agent",
    name: "StageSupervisor",
    kind: "class",
    title: "Stage Supervisor",
    category: "Agents",
    cacheable: false,
    description: "Inspects stage outcomes.",
    agent_role: "validator",
    allow_graph_edits: "confirm",
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
        default: "",
      },
    ],
    outputs: [{ name: "summary", type: "str", media: null }],
    allow_extra_inputs: false,
    source: "agent.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/agent:Planner",
    pack: "standard_io",
    module: "agent",
    name: "Planner",
    kind: "class",
    title: "Planner Agent",
    category: "Agents",
    cacheable: true,
    description: "Agent op.",
    agent_role: "agent",
    allow_graph_edits: "forbidden",
    inputs: [],
    outputs: [{ name: "plan", type: "str", media: null }],
    allow_extra_inputs: false,
    source: "agent.py",
    valid: true,
    error: null,
  },
];

const OPS_MAP: Record<string, OpEntry> = Object.fromEntries(
  OPS.map((op) => [op.id, op]),
);

const BASE_WORKFLOW: Workflow = {
  version: 1,
  name: "validator_ui_demo",
  stages: {
    s1: {
      title: "1. Ingest Stage",
      require_approval: false,
      validator: {
        op: "standard_io/agent:StageSupervisor",
        mode: "on_anomaly",
        allow_graph_edits: "confirm",
        inputs: { prompt: "Watch for French text" },
      },
    },
    s2: {
      title: "2. Output Stage",
      require_approval: false,
    },
  },
  nodes: {
    ingest: {
      op: "standard_io/demo:Ingest",
      stage: "s1",
      inputs: {},
    },
    planner: {
      op: "standard_io/agent:Planner",
      stage: "s2",
      inputs: {},
    },
  },
};

describe("Phase 4 Stage Validator, Patch Diff, & Drift UI (FEAT-AGT-3)", () => {
  it("attaches, configures, and removes a stage validator in StageInspectorPanel", () => {
    const onUpdateStage = vi.fn();
    render(
      <StageInspectorPanel
        selectedStageId="s2"
        workflow={BASE_WORKFLOW}
        opsMap={OPS_MAP}
        onUpdateStage={onUpdateStage}
      />,
    );

    // Attach validator to stage s2
    fireEvent.click(screen.getByTestId("btn-attach-stage-validator"));
    expect(onUpdateStage).toHaveBeenCalledWith("s2", {
      validator: {
        op: "standard_io/agent:StageSupervisor",
        mode: "on_anomaly",
        allow_graph_edits: "confirm",
        inputs: {},
      },
    });

    cleanup();
    const onUpdateS1 = vi.fn();
    render(
      <StageInspectorPanel
        selectedStageId="s1"
        workflow={BASE_WORKFLOW}
        opsMap={OPS_MAP}
        onUpdateStage={onUpdateS1}
      />,
    );

    // Change trigger mode and graph edit policy on s1
    fireEvent.change(screen.getByTestId("validator-mode-select"), {
      target: { value: "always" },
    });
    expect(onUpdateS1).toHaveBeenCalledWith(
      "s1",
      expect.objectContaining({
        validator: expect.objectContaining({ mode: "always" }),
      }),
    );

    fireEvent.change(screen.getByTestId("validator-edit-policy-select"), {
      target: { value: "auto" },
    });
    expect(onUpdateS1).toHaveBeenCalledWith(
      "s1",
      expect.objectContaining({
        validator: expect.objectContaining({ allow_graph_edits: "auto" }),
      }),
    );

    // Remove validator
    fireEvent.click(screen.getByTestId("btn-remove-stage-validator"));
    expect(onUpdateS1).toHaveBeenCalledWith("s1", { validator: null });
  });

  it("renders StageGroupNode validator pill without leaking __stage_validator__ as a regular node", () => {
    const onSelectValidator = vi.fn();
    const runWithValidator: RunState = {
      id: "run-val-1",
      workflow_path: "workflows/demo.yaml",
      workflow_sha256: "sha",
      status: "WAITING_FOR_USER",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: 1700000000,
      nodes: {
        ingest: {
          node_id: "ingest",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
          warnings: ["lang=fr"],
        },
        __stage_validator__s1: {
          node_id: "__stage_validator__s1",
          status: "WAITING_FOR_USER",
          cache_hit: false,
          attempt: 1,
          warnings: [],
        },
        planner: {
          node_id: "planner",
          status: "PENDING",
          cache_hit: false,
          attempt: 0,
          warnings: [],
        },
      },
      checkpoints: [
        {
          checkpoint_id: "cp_patch_0",
          node_id: "__stage_validator__s1",
          question: "Proposed Graph Patch",
          options: ["Approve Patch", "Reject"],
          allow_freeform: false,
          questions: [],
          graph_patch: {
            reason: "Splice French translator",
            add_nodes: {
              translate_fr: {
                op: "standard_io/demo:TranslateFr",
                stage: "s1",
                inputs: { text: "$ingest.text" },
              },
            },
            rewire_inputs: { planner: { text: "$translate_fr.text" } },
          },
          created_at: 1700000005,
        },
      ],
      stage_gates: {},
      workflow_snapshot: BASE_WORKFLOW,
    };

    render(
      <GraphView
        workflow={BASE_WORKFLOW}
        runState={runWithValidator}
        ops={OPS}
        onSelectValidator={onSelectValidator}
        readOnly={true}
      />,
    );

    expect(screen.getByTestId("stage-validator-pill-s1")).toBeInTheDocument();
    expect(screen.getByTestId("stage-validator-status-s1")).toHaveTextContent(
      "PATCH_PROPOSED",
    );
    expect(
      screen.queryByTestId("graph-node-__stage_validator__s1"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("stage-validator-pill-s1"));
    expect(onSelectValidator).toHaveBeenCalledWith(
      "s1",
      "__stage_validator__s1",
    );
  });

  it("renders validator patch diff preview in StepperView and submits Approve Patch", async () => {
    const answerSpy = vi
      .spyOn(client, "answerCheckpoint")
      .mockResolvedValue(undefined);
    const onCheckpointAnswered = vi.fn();

    const doc: WorkflowDocument = { workflow: BASE_WORKFLOW };
    const pausedRun: RunState = {
      id: "run-patch-confirm",
      workflow_path: "workflows/demo.yaml",
      workflow_sha256: "sha",
      status: "WAITING_FOR_USER",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: 1700000000,
      nodes: {
        ingest: {
          node_id: "ingest",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
          warnings: ["Detected French"],
        },
        __stage_validator__s1: {
          node_id: "__stage_validator__s1",
          status: "WAITING_FOR_USER",
          cache_hit: false,
          attempt: 1,
          warnings: [],
        },
        planner: {
          node_id: "planner",
          status: "PENDING",
          cache_hit: false,
          attempt: 0,
          warnings: [],
        },
      },
      checkpoints: [
        {
          checkpoint_id: "cp_patch_1",
          node_id: "__stage_validator__s1",
          question: "Stage 's1' validator proposed a graph patch",
          options: ["Approve Patch", "Reject"],
          allow_freeform: false,
          questions: [],
          graph_patch: {
            reason: "Detected French; splicing translator.",
            add_nodes: {
              translate_fr: {
                op: "standard_io/demo:TranslateFr",
                stage: "s1",
                inputs: { text: "$ingest.text" },
              },
            },
            rewire_inputs: { planner: { text: "$translate_fr.text" } },
          },
          created_at: 1700000010,
        },
      ],
      stage_gates: {},
      workflow_snapshot: BASE_WORKFLOW,
    };

    render(
      <StepperView
        runState={pausedRun}
        workflowDoc={doc}
        opsMap={OPS_MAP}
        onCheckpointAnswered={onCheckpointAnswered}
      />,
    );

    expect(screen.getByTestId("stage-validator-row-s1")).toBeInTheDocument();
    const card = screen.getByTestId("checkpoint-card-cp_patch_1");
    expect(card).toHaveTextContent("Detected French; splicing translator.");
    const preview = screen.getByTestId("patch-diff-preview-cp_patch_1");
    expect(preview).toHaveTextContent("+ translate_fr");
    expect(preview).toHaveTextContent("~ planner.text");
    expect(preview).toHaveTextContent("$translate_fr.text");

    fireEvent.click(screen.getByTestId("btn-approve-patch-cp_patch_1"));

    await waitFor(() => {
      expect(answerSpy).toHaveBeenCalledWith(
        "run-patch-confirm",
        "__stage_validator__s1",
        "cp_patch_1",
        "Approve Patch",
      );
      expect(onCheckpointAnswered).toHaveBeenCalledTimes(1);
    });
  });

  it("renders ADDED BY AGENT badge, provenance box, AgentOp graph edits select, and RunInspector layout toggle", () => {
    const splicedSnapshot: Workflow = {
      ...BASE_WORKFLOW,
      nodes: {
        ...BASE_WORKFLOW.nodes,
        translate_fr: {
          op: "standard_io/demo:TranslateFr",
          title: "Translate French",
          stage: "s1",
          meta: {
            injected_by: "__stage_validator__s1",
            reason: "French text detected in ingest output",
          },
          inputs: { text: "$ingest.text" },
        },
      },
    };

    const completedRun: RunState = {
      id: "run-spliced-1",
      workflow_path: "workflows/demo.yaml",
      workflow_sha256: "sha",
      status: "SUCCESS",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: 1700000000,
      nodes: {
        ingest: {
          node_id: "ingest",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
          warnings: [],
        },
        translate_fr: {
          node_id: "translate_fr",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
          warnings: [],
        },
        __stage_validator__s1: {
          node_id: "__stage_validator__s1",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
          warnings: [],
        },
        planner: {
          node_id: "planner",
          status: "SUCCESS",
          cache_hit: false,
          attempt: 1,
          warnings: [],
        },
      },
      checkpoints: [],
      stage_gates: {},
      workflow_snapshot: splicedSnapshot,
    };

    render(
      <RunInspector
        runState={completedRun}
        viewMode="graph"
        ops={OPS}
        opsMap={OPS_MAP}
        editorWorkflow={BASE_WORKFLOW}
        selectedNodeId="translate_fr"
        onSelectNode={vi.fn()}
        onPreviewArtifact={vi.fn()}
      />,
    );

    // ADDED BY AGENT badge on canvas node + provenance box in NodeInspector
    expect(
      screen.getByTestId("badge-added-by-agent-translate_fr"),
    ).toHaveTextContent("ADDED BY AGENT");
    expect(screen.getByTestId("inspector-injected-meta")).toHaveTextContent(
      "__stage_validator__s1",
    );
    expect(screen.getByTestId("inspector-injected-meta")).toHaveTextContent(
      "French text detected in ingest output",
    );

    // Client-side layout toggle bar
    expect(screen.getByTestId("run-layout-mode-toggle")).toBeInTheDocument();
    const origBtn = screen.getByTestId("layout-mode-original");
    const relayoutBtn = screen.getByTestId("layout-mode-relayout");
    expect(relayoutBtn).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(origBtn);
    expect(origBtn).toHaveAttribute("aria-pressed", "true");

    // Also verify regular AgentOp node allow_graph_edits selector in editor mode
    cleanup();
    const onUpdateNodeSpec = vi.fn();
    render(
      <NodeInspector
        nodeId="planner"
        workflow={BASE_WORKFLOW}
        opsMap={OPS_MAP}
        onUpdateNodeSpec={onUpdateNodeSpec}
      />,
    );
    const policySelect = screen.getByTestId("inspector-node-allow-graph-edits");
    fireEvent.change(policySelect, { target: { value: "confirm" } });
    const updater = onUpdateNodeSpec.mock.calls[0][1];
    expect(updater(BASE_WORKFLOW.nodes!.planner).allow_graph_edits).toBe(
      "confirm",
    );
  });

  it("renders Baseline Drift alert banner in RunList when recurring splices are detected", async () => {
    vi.spyOn(client, "fetchRuns").mockResolvedValue({
      runs: [
        {
          id: "run-1",
          workflow_path: "workflows/demo.yaml",
          workflow_sha256: "h1",
          status: "SUCCESS",
          cancel_requested: false,
          pinned: false,
          created_at: 1700000000,
        },
      ],
      drift_alerts: [
        {
          workflow_path: "workflows/demo.yaml",
          injected_op: "standard_io/demo:TranslateFr",
          upstream_op: "standard_io/demo:Ingest",
          downstream_op: "standard_io/agent:Planner",
          occurrences: 3,
          window_runs: 5,
          message:
            "Baseline Drift Detected in 'workflows/demo.yaml': 'standard_io/demo:TranslateFr' was spliced in 3 of the last 5 runs.",
        },
      ],
    });

    render(
      <RouterProvider>
        <RunList />
      </RouterProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("baseline-drift-banner")).toHaveTextContent(
        "standard_io/demo:TranslateFr",
      );
    });
  });
});
