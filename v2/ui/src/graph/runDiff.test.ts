import { describe, expect, it } from "vitest";
import type { RunState, Workflow } from "../api/types.gen";
import { computeWorkflowRunDiff } from "./runDiff";

function makeBaseRun(snapshot: Workflow, runInputs: Record<string, unknown> = {}): RunState {
  return {
    id: "20261120-100000-abcd",
    workflow_path: "workflows/demo.yaml",
    workflow_sha256: "sha123",
    status: "SUCCESS",
    run_inputs: runInputs,
    cancel_requested: false,
    pinned: false,
    created_at: 1700000000,
    nodes: {},
    checkpoints: [],
    stage_gates: {},
    workflow_snapshot: snapshot,
  };
}

describe("computeWorkflowRunDiff (Task 6.19)", () => {
  it("returns unchanged when editor workflow matches run workflow_snapshot", () => {
    const wf: Workflow = {
      version: 1,
      name: "Demo",
      nodes: {
        step1: {
          op: "builtin/demo:echo",
          inputs: { text: "hello" },
        },
      },
    };
    const run = makeBaseRun(wf);
    const diff = computeWorkflowRunDiff(wf, run);
    expect(diff.hasChanges).toBe(false);
    expect(diff.nodes.step1.status).toBe("unchanged");
    expect(Object.keys(diff.nodes.step1.changedInputs)).toHaveLength(0);
  });

  it("detects modified input literals and wire references on a node", () => {
    const snapshot: Workflow = {
      version: 1,
      nodes: {
        step1: {
          op: "builtin/demo:echo",
          inputs: { text: "original", count: 2 },
        },
      },
    };
    const editor: Workflow = {
      version: 1,
      nodes: {
        step1: {
          op: "builtin/demo:echo",
          inputs: { text: "edited prompt", count: 2 },
        },
      },
    };
    const diff = computeWorkflowRunDiff(editor, makeBaseRun(snapshot));
    expect(diff.hasChanges).toBe(true);
    expect(diff.nodes.step1.status).toBe("modified");
    expect(diff.nodes.step1.changedInputs.text).toEqual({
      portName: "text",
      runValue: "original",
      editorValue: "edited prompt",
    });
    expect(diff.nodes.step1.changedInputs.count).toBeUndefined();
  });

  it("detects not_in_run (workflow node absent from run) and new_in_run (run node absent from workflow)", () => {
    const snapshot: Workflow = {
      version: 1,
      nodes: {
        old_node: { op: "builtin/demo:echo", inputs: {} },
      },
    };
    const editor: Workflow = {
      version: 1,
      nodes: {
        new_node: { op: "builtin/demo:echo", inputs: {} },
      },
    };
    const diff = computeWorkflowRunDiff(editor, makeBaseRun(snapshot));
    expect(diff.hasChanges).toBe(true);
    expect(diff.nodes.new_node.status).toBe("not_in_run");
    expect(diff.nodes.old_node.status).toBe("new_in_run");
    expect(diff.removedNodeIds).toEqual(["old_node"]);
  });
});
