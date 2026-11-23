import type { Node } from "@xyflow/react";
import type {
  InputPortSpec,
  NodeRef,
  NodeRunState,
  NodeSpec,
  NodeStatus,
  OpEntry,
  OutputPortSpec,
  StageGateState,
} from "../api/types.gen";
import type { NodeDiff } from "./runDiff";

export const STAGE_NODE_PREFIX = "__stage__:";

export function getStatusHint(
  status?: NodeStatus,
  isNotInRun?: boolean,
  error?: string | null,
): string {
  if (isNotInRun) {
    return "Status: NOT IN RUN - This operation did not exist in the selected run";
  }
  switch (status) {
    case "SUCCESS":
      return "Status: SUCCESS - Operation completed successfully";
    case "RUNNING":
      return "Status: RUNNING - Operation is currently executing";
    case "BUILDING_ENVIRONMENT":
      return "Status: BUILDING_ENVIRONMENT - Preparing execution environment";
    case "WAITING_FOR_USER":
      return "Status: WAITING_FOR_USER - Paused waiting for user input or approval";
    case "FAILED":
      return error ? `Status: FAILED - ${error}` : "Status: FAILED - Operation failed";
    case "CANCELED":
      return "Status: CANCELED - Execution was canceled";
    case "BLOCKED":
      return "Status: BLOCKED - Upstream dependency failed or canceled";
    case "PENDING":
      return "Status: PENDING - Waiting for upstream dependencies";
    default:
      return "Status: IDLE - Blueprint draft (not running)";
  }
}

export function getCacheHint(nodeState?: NodeRunState): string {
  if (!nodeState?.cache_hit) return "";
  if (nodeState.cache_key) {
    return `Cached (Cache hit): Outputs reused from previous run via cache (Key: ${nodeState.cache_key.slice(0, 10)}...)`;
  }
  return "Cached (Cache hit): Outputs reused from previous run without re-running";
}

const REF_STRING_REGEX = /^\$([a-z][a-z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)$/;

export function stageGroupId(stageId: string): string {
  return `${STAGE_NODE_PREFIX}${stageId}`;
}

export function isStageGroupId(nodeId: string): boolean {
  return nodeId.startsWith(STAGE_NODE_PREFIX);
}

export function extractStageId(groupNodeId: string): string {
  return groupNodeId.slice(STAGE_NODE_PREFIX.length);
}

export function inputHandleId(portName: string): string {
  return `in:${portName}`;
}

export function outputHandleId(portName: string): string {
  return `out:${portName}`;
}

export function parseHandleId(
  handleId: string | null | undefined,
): { kind: "in" | "out"; name: string } | null {
  if (!handleId) return null;
  if (handleId.startsWith("in:")) {
    return { kind: "in", name: handleId.slice(3) };
  }
  if (handleId.startsWith("out:")) {
    return { kind: "out", name: handleId.slice(4) };
  }
  return null;
}

export function extractNodeRef(value: unknown): NodeRef | null {
  if (typeof value === "string") {
    const match = REF_STRING_REGEX.exec(value);
    if (match) {
      return { from_node: match[1], output: match[2] };
    }
    return null;
  }
  if (
    typeof value === "object" &&
    value !== null &&
    "from_node" in value &&
    "output" in value
  ) {
    const rec = value as Record<string, unknown>;
    if (typeof rec.from_node === "string" && typeof rec.output === "string") {
      return { from_node: rec.from_node, output: rec.output };
    }
  }
  return null;
}

export interface StageGroupNodeData extends Record<string, unknown> {
  stageId: string;
  title: string;
  requireApproval: boolean;
  gateState?: StageGateState;
  nodeCount: number;
  isSelected?: boolean;
  isDropTarget?: boolean;
  onSelectStage?: (stageId: string) => void;
  onDeleteStage?: (stageId: string) => void;
}

export interface WorkflowNodeData extends Record<string, unknown> {
  nodeId: string;
  spec: NodeSpec;
  opEntry?: OpEntry;
  nodeState?: NodeRunState;
  nodeDiff?: NodeDiff;
  inputs: ReadonlyArray<InputPortSpec>;
  outputs: ReadonlyArray<OutputPortSpec>;
  isSelected: boolean;
  readOnly: boolean;
  onLiteralChange?: (nodeId: string, portName: string, value: unknown) => void;
  onPreviewOutput?: (nodeId: string, output: OutputPortSpec) => void;
}

export type StageGroupGraphNode = Node<StageGroupNodeData, "stageGroup">;
export type WorkflowGraphNode = Node<WorkflowNodeData, "workflowNode">;
export type GraphNode = StageGroupGraphNode | WorkflowGraphNode;
