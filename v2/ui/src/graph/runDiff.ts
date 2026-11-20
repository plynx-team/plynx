import type { NodeSpec, RunState, Workflow } from "../api/types.gen";

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

function resolveSnapshotInput(
  nodeId: string,
  portName: string,
  snapNode: NodeSpec,
  runInputs: Record<string, unknown> | undefined,
): unknown {
  const qualifiedKey = `${nodeId}.${portName}`;
  if (runInputs && qualifiedKey in runInputs) {
    return runInputs[qualifiedKey];
  }
  return snapNode.inputs?.[portName];
}

/**
 * Compare the current Editor workflow against a selected Run's frozen workflow_snapshot.
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
      if (!snapshotNodes[nodeId]) {
        snapshotNodes[nodeId] = {
          op: "unknown",
          stage: "default",
          inputs: {},
        };
      }
    }
  }

  const runInputs = runState.run_inputs;

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
    if (runInputs) {
      const prefix = `${nodeId}.`;
      for (const k of Object.keys(runInputs)) {
        if (k.startsWith(prefix)) {
          allPortKeys.add(k.slice(prefix.length));
        }
      }
    }

    const changedInputs: Record<string, InputDiffEntry> = {};
    for (const portName of allPortKeys) {
      const editorValue = editorNode.inputs?.[portName];
      const runValue = resolveSnapshotInput(
        nodeId,
        portName,
        snapNode,
        runInputs,
      );
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
