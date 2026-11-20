import { describe, expect, it } from "vitest";
import type { OpEntry, Workflow, WorkflowLayout } from "../api/types.gen";
import {
  addNodeToWorkflow,
  addStageToWorkflow,
  deleteNodeFromWorkflow,
  deleteStageFromWorkflow,
  duplicateNodeInWorkflow,
  generateNodeId,
  generateStageId,
  reorderStagesInWorkflow,
  toSnakeCaseId,
  updateStageInWorkflow,
} from "./mutations";

const CONCAT_OP: OpEntry = {
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
  source: "builtin_packs/standard_io/src/standard_io/text.py",
  valid: true,
  error: null,
};

const BASE_WORKFLOW: Workflow = {
  version: 1,
  name: "demo",
  stages: {
    ask: { title: "1. Ask", require_approval: false },
    print: { title: "2. Print", require_approval: false },
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
      title: "Echo",
      stage: "print",
      inputs: { text: { from_node: "pick", output: "choice" } },
    },
  },
};

const BASE_LAYOUT: WorkflowLayout = {
  schema: 1,
  nodes: {
    pick: { x: 40, y: 60 },
    echo: { x: 420, y: 60 },
  },
  viewport: { x: 0, y: 0, zoom: 1 },
};

describe("graph mutations (Task 6.9)", () => {
  it("converts names to valid snake_case node IDs and deduplicates", () => {
    expect(toSnakeCaseId("AskFooOrWoo")).toBe("ask_foo_or_woo");
    expect(toSnakeCaseId("123Test")).toBe("n_123_test");
    expect(generateNodeId("Concat", ["pick", "echo"])).toBe("concat");
    expect(generateNodeId("Concat", ["concat", "concat_2"])).toBe("concat_3");
  });

  it("adds a new node to the chosen stage with layout coordinates", () => {
    const res = addNodeToWorkflow(BASE_WORKFLOW, BASE_LAYOUT, CONCAT_OP, {
      stageId: "print",
    });

    expect(res.nodeId).toBe("concat");
    expect(res.workflow.nodes?.concat).toEqual({
      op: CONCAT_OP.id,
      title: CONCAT_OP.title,
      stage: "print",
      inputs: {},
    });
    expect(res.layout.nodes.concat).toBeDefined();
  });

  it("duplicates a node with cloned inputs and offset layout position", () => {
    const res = duplicateNodeInWorkflow(BASE_WORKFLOW, BASE_LAYOUT, "echo");
    expect(res).not.toBeNull();
    expect(res!.nodeId).toBe("echo_copy");
    expect(res!.workflow.nodes?.echo_copy?.op).toBe("standard_io/demo:Echo");
    expect(res!.workflow.nodes?.echo_copy?.inputs).toEqual({
      text: { from_node: "pick", output: "choice" },
    });
    expect(res!.layout.nodes.echo_copy.x).toBeGreaterThan(BASE_LAYOUT.nodes.echo.x);
  });

  it("deletes a node and removes dangling input references in downstream nodes", () => {
    const res = deleteNodeFromWorkflow(BASE_WORKFLOW, BASE_LAYOUT, "pick");
    expect(res.workflow.nodes?.pick).toBeUndefined();
    expect(res.layout.nodes.pick).toBeUndefined();
    // Downstream reference to $pick.choice is cleaned up
    expect(res.workflow.nodes?.echo?.inputs).toEqual({});
  });

  it("creates, updates, and deduplicates stage IDs", () => {
    expect(generateStageId("Data Prep", ["ask", "print"])).toBe("data_prep");
    expect(generateStageId("ask", ["ask", "print"])).toBe("ask_2");

    const addRes = addStageToWorkflow(BASE_WORKFLOW, "eval", "Evaluation", {
      requireApproval: true,
    });
    expect(addRes.stageId).toBe("eval");
    expect(addRes.workflow.stages?.eval).toEqual({
      title: "Evaluation",
      require_approval: true,
    });

    const updateRes = updateStageInWorkflow(addRes.workflow, "eval", {
      title: "Final Evaluation",
      require_approval: false,
    });
    expect(updateRes.stages?.eval).toEqual({
      title: "Final Evaluation",
      require_approval: false,
    });
  });

  it("deletes a stage and reassigns member nodes to default main stage", () => {
    const res = deleteStageFromWorkflow(BASE_WORKFLOW, BASE_LAYOUT, "print", {
      reassignToStageId: "main",
    });
    expect(res.workflow.stages?.print).toBeUndefined();
    // echo was moved to main
    expect(res.workflow.nodes?.echo?.stage).toBe("main");
    // pick was in ask and remains in ask
    expect(res.workflow.nodes?.pick?.stage).toBe("ask");
  });

  it("deletes a stage and deletes all member nodes when deleteNodes is true", () => {
    const res = deleteStageFromWorkflow(BASE_WORKFLOW, BASE_LAYOUT, "print", {
      deleteNodes: true,
    });
    expect(res.workflow.stages?.print).toBeUndefined();
    expect(res.workflow.nodes?.echo).toBeUndefined();
    expect(res.layout.nodes.echo).toBeUndefined();
  });

  it("reorders stages and prevents invalid DAG backwards edge order", () => {
    // pick in ask -> echo in print. Valid order: ask, print
    const invalid = reorderStagesInWorkflow(BASE_WORKFLOW, ["print", "ask"]);
    expect(invalid.success).toBe(false);
    if (!invalid.success) {
      expect(invalid.reason).toContain("depends on");
    }

    // Adding an independent stage 'prep' before 'ask'
    const wfWithPrep = addStageToWorkflow(BASE_WORKFLOW, "prep", "Prep").workflow;
    const valid = reorderStagesInWorkflow(wfWithPrep, ["prep", "ask", "print"]);
    expect(valid.success).toBe(true);
    if (valid.success) {
      expect(Object.keys(valid.workflow.stages ?? {})).toEqual(["prep", "ask", "print"]);
    }
  });
});
