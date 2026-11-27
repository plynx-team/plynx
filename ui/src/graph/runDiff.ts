import type { NodeSpec, RunState, Workflow } from "../api/types.gen";
import { isStageValidatorNodeId } from "./types";

export interface InputDiffEntry {
  portName: string;
  runValue: unknown;
  editorValue: unknown;
}

export type NodeDiffStatus =
  | "unchanged"
  | "modified"
  | "not_in_run"
  | "new_in_run";

export interface NodeDiff {
  nodeId: string;
  status: NodeDiffStatus;
  opChanged: boolean;
  runOp?: string;
  editorOp?: string;
  changedInputs: Record<string, InputDiffEntry>;
}

export interface WorkflowRunDiff {
  hasChanges: boolean;
  nodes: Record<string, NodeDiff>;
  removedNodeIds: Array<string>;
}

function normalizeInputValue(val: unknown): unknown {
  if (val === undefined || val === null || val === "") {
    return null;
  }
  if (Array.isArray(val)) {
    return val.map(normalizeInputValue);
  }
  if (typeof val === "object") {
    const record = val as Record<string, unknown>;
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(record).sort()) {
      sorted[key] = normalizeInputValue(record[key]);
    }
    return sorted;
  }
  return val;
}

function valuesEqual(a: unknown, b: unknown): boolean {
  return (
    JSON.stringify(normalizeInputValue(a)) ===
    JSON.stringify(normalizeInputValue(b))
  );
}

/**
 * Compare the current Editor workflow against a selected Run's workflow snapshot.
 *
 * Diff Philosophy (Editor as Newer, matching "Editor modified since this run"):
 * The Run snapshot serves as the older baseline (- Run, red).
 * The current Editor workflow serves as the newer modified state (+ Editor, teal/green).
 * Runtime ``run_inputs`` supplied for unbound ports are NOT treated as workflow edits.
 */
export function computeWorkflowRunDiff(
  editorWorkflow: Workflow | null | undefined,
  runState: RunState | null | undefined,
): WorkflowRunDiff {
  if (!editorWorkflow || !runState) {
    return { hasChanges: false, nodes: {}, removedNodeIds: [] };
  }

  const editorNodes = editorWorkflow.nodes ?? {};
  // Prefer workflow_snapshot nodes, but fall back to runState.nodes
  const snapshotNodes: Record<string, NodeSpec> = {
    ...(runState.workflow_snapshot?.nodes ?? {}),
  };
  if (runState.nodes) {
    for (const nodeId of Object.keys(runState.nodes)) {
      if (isStageValidatorNodeId(nodeId)) {
        continue;
      }
      if (!snapshotNodes[nodeId]) {
        snapshotNodes[nodeId] = {
          op: "unknown",
          stage: "default",
          inputs: {},
        };
      }
    }
  }

  const nodes: Record<string, NodeDiff> = {};
  let hasChanges = false;

  for (const [nodeId, editorNode] of Object.entries(editorNodes)) {
    const snapNode = snapshotNodes[nodeId];
    if (!snapNode) {
      hasChanges = true;
      nodes[nodeId] = {
        nodeId,
        status: "not_in_run",
        opChanged: false,
        editorOp: editorNode.op,
        changedInputs: {},
      };
      continue;
    }

    const opChanged = editorNode.op !== snapNode.op;
    const allPortKeys = new Set<string>([
      ...Object.keys(editorNode.inputs ?? {}),
      ...Object.keys(snapNode.inputs ?? {}),
    ]);

    const changedInputs: Record<string, InputDiffEntry> = {};
    for (const portName of allPortKeys) {
      const editorValue = editorNode.inputs?.[portName];
      const runValue = snapNode.inputs?.[portName];
      if (!valuesEqual(editorValue, runValue)) {
        changedInputs[portName] = {
          portName,
          runValue,
          editorValue,
        };
      }
    }

    const isModified = opChanged || Object.keys(changedInputs).length > 0;
    if (isModified) {
      hasChanges = true;
    }

    nodes[nodeId] = {
      nodeId,
      status: isModified ? "modified" : "unchanged",
      opChanged,
      runOp: snapNode.op,
      editorOp: editorNode.op,
      changedInputs,
    };
  }

  const removedNodeIds = Object.keys(snapshotNodes).filter(
    (id) => !(id in editorNodes),
  );
  if (removedNodeIds.length > 0) {
    hasChanges = true;
    for (const snapId of removedNodeIds) {
      const snapNode = snapshotNodes[snapId];
      nodes[snapId] = {
        nodeId: snapId,
        status: "new_in_run",
        opChanged: false,
        runOp: snapNode?.op,
        changedInputs: {},
      };
    }
  }

  return {
    hasChanges,
    nodes,
    removedNodeIds,
  };
}
