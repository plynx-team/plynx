import { describe, expect, it } from "vitest";
import type { OpEntry, RunState, Workflow, WorkflowLayout } from "../api/types.gen";
import { buildGraphElements, computeDagrePositions, getOrderedStageIds } from "./layout";
import { stageGroupId } from "./types";

const SAMPLE_OPS: Record<string, OpEntry> = {
  "standard_io/demo:AskFooOrWoo": {
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
  "standard_io/demo:Echo": {
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
    source: "builtin_packs/standard_io/src/standard_io/demo.py",
    valid: true,
    error: null,
  },
};

const SAMPLE_WORKFLOW: Workflow = {
  version: 1,
  name: "foo_or_woo",
  stages: {
    ask: { title: "1. Ask", require_approval: false },
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
      stage: "print",
      inputs: { text: { from_node: "pick", output: "choice" } },
    },
  },
};

describe("graph layout utilities (Task 6.8)", () => {
  it("preserves explicit stage order and appends implicit node stages", () => {
    expect(getOrderedStageIds(SAMPLE_WORKFLOW)).toEqual(["ask", "print"]);
  });

  it("computes left-to-right Dagre positions separating stages horizontally", () => {
    const positions = computeDagrePositions(SAMPLE_WORKFLOW, SAMPLE_OPS);
    expect(positions.pick).toBeDefined();
    expect(positions.echo).toBeDefined();
    expect(positions.echo.x).toBeGreaterThan(positions.pick.x);
  });

  it("builds stage group parent nodes before child workflow nodes and creates edges", () => {
    const runState: RunState = {
      id: "run-1",
      workflow_path: "examples/workflows/foo_or_woo.yaml",
      workflow_sha256: "abc",
      status: "RUNNING",
      run_inputs: {},
      owner_pid: 123,
      cancel_requested: false,
      pinned: false,
      created_at: 100,
      nodes: {
        pick: { node_id: "pick", status: "SUCCESS", cache_hit: true, attempt: 1 },
        echo: { node_id: "echo", status: "RUNNING", cache_hit: false, attempt: 1 },
      },
      checkpoints: [],
      stage_gates: {},
    };

    const { nodes, edges } = buildGraphElements(SAMPLE_WORKFLOW, {
      opsMap: SAMPLE_OPS,
      runState,
      readOnly: true,
    });

    const stageIndices = nodes
      .map((n, idx) => (n.type === "stageGroup" ? idx : -1))
      .filter((i) => i >= 0);
    const workflowIndices = nodes
      .map((n, idx) => (n.type === "workflowNode" ? idx : -1))
      .filter((i) => i >= 0);

    expect(stageIndices).toEqual([0, 1]);
    expect(Math.max(...stageIndices)).toBeLessThan(Math.min(...workflowIndices));

    const pickNode = nodes.find((n) => n.id === "pick");
    const echoNode = nodes.find((n) => n.id === "echo");
    expect(pickNode?.parentId).toBe(stageGroupId("ask"));
    expect(echoNode?.parentId).toBe(stageGroupId("print"));

    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe("pick");
    expect(edges[0].sourceHandle).toBe("out:choice");
    expect(edges[0].target).toBe("echo");
    expect(edges[0].targetHandle).toBe("in:text");
    expect(edges[0].animated).toBe(true);
  });

  it("honors saved sidecar layout positions when provided", () => {
    const savedLayout: WorkflowLayout = {
      schema: 1,
      nodes: {
        pick: { x: 100, y: 200 },
        echo: { x: 600, y: 250 },
      },
      viewport: { x: 0, y: 0, zoom: 1 },
    };

    const { absolutePositions } = buildGraphElements(SAMPLE_WORKFLOW, {
      layout: savedLayout,
      opsMap: SAMPLE_OPS,
    });

    expect(absolutePositions.pick).toEqual({ x: 100, y: 200 });
    expect(absolutePositions.echo).toEqual({ x: 600, y: 250 });
  });

  it("includes run snapshot nodes not present in workflow as new_in_run snapshot nodes", () => {
    const runStateWithExtraNode: RunState = {
      id: "run-extra",
      workflow_path: "examples/workflows/foo_or_woo.yaml",
      workflow_sha256: "abc",
      status: "SUCCESS",
      run_inputs: {},
      owner_pid: null,
      cancel_requested: false,
      pinned: false,
      created_at: 100,
      nodes: {
        pick: { node_id: "pick", status: "SUCCESS", cache_hit: true, attempt: 1 },
        echo: { node_id: "echo", status: "SUCCESS", cache_hit: false, attempt: 1 },
        extra_op: { node_id: "extra_op", status: "SUCCESS", cache_hit: false, attempt: 1 },
      },
      checkpoints: [],
      stage_gates: {},
      workflow_snapshot: {
        version: 1,
        name: "foo_or_woo",
        stages: { ask: { title: "1. Ask" }, print: {} },
        nodes: {
          pick: { op: "standard_io/demo:AskFooOrWoo", stage: "ask" },
          echo: { op: "standard_io/demo:Echo", stage: "print" },
          extra_op: { op: "standard_io/demo:Echo", stage: "print" },
        },
      },
    };

    const { nodes } = buildGraphElements(SAMPLE_WORKFLOW, {
      opsMap: SAMPLE_OPS,
      runState: runStateWithExtraNode,
      readOnly: true,
    });

    const extraNode = nodes.find((n) => n.id === "extra_op");
    expect(extraNode).toBeDefined();
    expect(extraNode?.data.nodeId).toBe("extra_op");
    expect(extraNode?.data.readOnly).toBe(true);
  });

  it("includes nodes that only exist in runState.nodes when workflow_snapshot is missing", () => {
    const runStateOnlyNodes: RunState = {
      id: "run-no-snap",
      workflow_path: "foo.yaml",
      workflow_sha256: "abc",
      status: "SUCCESS",
      run_inputs: {},
      owner_pid: null,
      cancel_requested: false,
      pinned: false,
      created_at: 100,
      nodes: {
        pick: { node_id: "pick", status: "SUCCESS", cache_hit: true, attempt: 1 },
        fallback_node: { node_id: "fallback_node", status: "SUCCESS", cache_hit: false, attempt: 1 },
      },
      checkpoints: [],
      stage_gates: {},
    };

    const { nodes } = buildGraphElements(SAMPLE_WORKFLOW, {
      opsMap: SAMPLE_OPS,
      runState: runStateOnlyNodes,
    });
    const fallbackNode = nodes.find((n) => n.id === "fallback_node");
    expect(fallbackNode).toBeDefined();
    expect(fallbackNode?.data.nodeId).toBe("fallback_node");
  });

  it("positions snapshot-only nodes from runState.layout_snapshot when present", () => {
    const runStateWithLayout: RunState = {
      id: "run-snap-layout",
      workflow_path: "foo.yaml",
      workflow_sha256: "abc",
      status: "SUCCESS",
      run_inputs: {},
      owner_pid: null,
      cancel_requested: false,
      pinned: false,
      created_at: 100,
      nodes: {
        pick: { node_id: "pick", status: "SUCCESS", cache_hit: true, attempt: 1 },
        echo_2: { node_id: "echo_2", status: "SUCCESS", cache_hit: false, attempt: 1 },
      },
      checkpoints: [],
      stage_gates: {},
      workflow_snapshot: {
        version: 1,
        name: "wf",
        stages: { print: {} },
        nodes: {
          echo_2: { op: "standard_io/demo:Echo", stage: "print" },
        },
      },
      layout_snapshot: {
        schema: 1,
        nodes: {
          echo_2: { x: 408, y: 204 },
        },
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    };

    const { absolutePositions } = buildGraphElements(SAMPLE_WORKFLOW, {
      opsMap: SAMPLE_OPS,
      runState: runStateWithLayout,
    });
    expect(absolutePositions["echo_2"]).toEqual({ x: 408, y: 204 });
  });

  it("dynamically sizes stage groups to fit custom/variable measured node widths and heights", () => {
    // Simulate nodes having non-standard, dynamic measured widths (e.g., 380px wide) and heights (220px tall)
    const { nodes } = buildGraphElements(SAMPLE_WORKFLOW, {
      opsMap: SAMPLE_OPS,
      measuredDimensions: {
        pick: { width: 380, height: 220 },
      },
    });

    const askGroup = nodes.find((n) => n.id === stageGroupId("ask"));
    expect(askGroup).toBeDefined();
    // Width should cleanly enclose the 380px wide node + 2 * STAGE_PAD_X (32px) = 444px
    expect(askGroup?.style?.width).toBe(380 + 32 * 2);
    // Height should cleanly enclose the 220px tall node + STAGE_PAD_TOP (48px) + STAGE_PAD_BOTTOM (52px) = 320px
    expect(askGroup?.style?.height).toBe(220 + 48 + 52);
  });

  it("marks non-empty stages as draggable with dragHandle when not readOnly", () => {
    const wfWithEmptyStage: Workflow = {
      ...SAMPLE_WORKFLOW,
      stages: {
        ...SAMPLE_WORKFLOW.stages,
        empty_stage: { title: "Empty Stage" },
      },
    };

    const editableElements = buildGraphElements(wfWithEmptyStage, {
      opsMap: SAMPLE_OPS,
      readOnly: false,
    });

    const askGroup = editableElements.nodes.find((n) => n.id === stageGroupId("ask"));
    const emptyGroup = editableElements.nodes.find((n) => n.id === stageGroupId("empty_stage"));

    expect(askGroup?.draggable).toBe(true);
    expect(askGroup?.dragHandle).toBe(".stage-drag-handle");
    expect(emptyGroup?.draggable).toBe(false);

    const readOnlyElements = buildGraphElements(wfWithEmptyStage, {
      opsMap: SAMPLE_OPS,
      readOnly: true,
    });

    const readOnlyAskGroup = readOnlyElements.nodes.find((n) => n.id === stageGroupId("ask"));
    expect(readOnlyAskGroup?.draggable).toBe(false);
  });

  it("elides stage group container for a single stage called main", () => {
    const singleMainWf: Workflow = {
      version: 1,
      name: "single_main_pipeline",
      stages: {
        main: { title: "Workflow" },
      },
      nodes: {
        ask: {
          op: "standard_io/demo:AskFooOrWoo",
          stage: "main",
          inputs: { prompt: "pick?" },
        },
        echo: {
          op: "standard_io/demo:Echo",
          stage: "main",
          inputs: { text: "hello" },
        },
      },
    };

    const savedLayout: WorkflowLayout = {
      schema: 1,
      nodes: {
        ask: { x: 50, y: 100 },
        echo: { x: 400, y: 150 },
      },
      viewport: { x: 0, y: 0, zoom: 1 },
    };

    const elements = buildGraphElements(singleMainWf, {
      layout: savedLayout,
      opsMap: SAMPLE_OPS,
    });

    // Zero stage group nodes rendered
    const stageGroups = elements.nodes.filter((n) => n.type === "stageGroup");
    expect(stageGroups).toHaveLength(0);

    // Only workflowNodes rendered
    const workflowNodes = elements.nodes.filter((n) => n.type === "workflowNode");
    expect(workflowNodes).toHaveLength(2);

    // Nodes have no parentId and their positions match absolute canvas coordinates
    const askNode = workflowNodes.find((n) => n.id === "ask");
    const echoNode = workflowNodes.find((n) => n.id === "echo");

    expect(askNode?.parentId).toBeUndefined();
    expect(askNode?.position).toEqual({ x: 50, y: 100 });

    expect(echoNode?.parentId).toBeUndefined();
    expect(echoNode?.position).toEqual({ x: 400, y: 150 });

    // stageGroupPositions for main defaults to { x: 0, y: 0 }
    expect(elements.stageGroupPositions.main).toEqual({ x: 0, y: 0 });
  });

  it("renders stage group container if a single stage has a non-main name", () => {
    const singleCustomStageWf: Workflow = {
      version: 1,
      name: "custom_stage_pipeline",
      stages: {
        etl: { title: "ETL Process" },
      },
      nodes: {
        echo: {
          op: "standard_io/demo:Echo",
          stage: "etl",
          inputs: { text: "data" },
        },
      },
    };

    const elements = buildGraphElements(singleCustomStageWf, {
      opsMap: SAMPLE_OPS,
    });

    // Stage group is rendered because stage name is not "main"
    const stageGroups = elements.nodes.filter((n) => n.type === "stageGroup");
    expect(stageGroups).toHaveLength(1);
    expect(stageGroups[0].id).toBe(stageGroupId("etl"));

    const echoNode = elements.nodes.find((n) => n.id === "echo");
    expect(echoNode?.parentId).toBe(stageGroupId("etl"));
  });
});
