import dagre from "@dagrejs/dagre";
import type { Edge } from "@xyflow/react";
import type {
  InputPortSpec,
  NodePosition,
  NodeRunState,
  NodeSpec,
  OpEntry,
  OutputPortSpec,
  RunState,
  Stage,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import type { WorkflowRunDiff } from "./runDiff";
import {
  extractNodeRef,
  inputHandleId,
  outputHandleId,
  stageGroupId,
  type GraphNode,
  type StageGroupGraphNode,
  type WorkflowGraphNode,
} from "./types";

export const NODE_WIDTH = 220;
const NODE_HEADER_HEIGHT = 56;
const PORT_ROW_HEIGHT = 32;
const NODE_FOOTER_PADDING = 20;

export const STAGE_PAD_X = 36;
export const STAGE_PAD_TOP = 54;
export const STAGE_PAD_BOTTOM = 32;
export const STAGE_GAP_X = 80;
export const EMPTY_STAGE_WIDTH = 280;
export const EMPTY_STAGE_HEIGHT = 140;

export const DEFAULT_STAGE_ID = "main";
export const DEFAULT_STAGE_TITLE = "Workflow";

export function getOrderedStageIds(workflow: Workflow): Array<string> {
  const ordered: Array<string> = [];
  const seen = new Set<string>();

  if (workflow.stages) {
    for (const stageId of Object.keys(workflow.stages)) {
      if (!seen.has(stageId)) {
        seen.add(stageId);
        ordered.push(stageId);
      }
    }
  }

  if (workflow.nodes) {
    for (const node of Object.values(workflow.nodes)) {
      const stageId = node.stage || DEFAULT_STAGE_ID;
      if (!seen.has(stageId)) {
        seen.add(stageId);
        ordered.push(stageId);
      }
    }
  }

  if (ordered.length === 0) {
    ordered.push(DEFAULT_STAGE_ID);
  }

  return ordered;
}

export function resolveNodePorts(
  nodeId: string,
  spec: NodeSpec,
  workflow: Workflow,
  opEntry?: OpEntry,
): {
  inputs: Array<InputPortSpec>;
  outputs: Array<OutputPortSpec>;
} {
  if (opEntry) {
    return {
      inputs: [...opEntry.inputs],
      outputs: [...opEntry.outputs],
    };
  }

  // Fallback when op registry entry is unavailable: infer ports from workflow references & inputs
  const inputs: Array<InputPortSpec> = Object.keys(spec.inputs ?? {}).map(
    (name) => ({
      name,
      type: "str",
      media: null,
      options: null,
      min: null,
      max: null,
      step: null,
      required: false,
      default: null,
    }),
  );

  const outputNames = new Set<string>();
  for (const otherSpec of Object.values(workflow.nodes ?? {})) {
    for (const val of Object.values(otherSpec.inputs ?? {})) {
      const ref = extractNodeRef(val);
      if (ref && ref.from_node === nodeId) {
        outputNames.add(ref.output);
      }
    }
  }

  const outputs: Array<OutputPortSpec> = Array.from(outputNames).map((name) => ({
    name,
    type: "str",
    media: null,
  }));

  return { inputs, outputs };
}

export function estimateNodeDimensions(
  inputsCount: number,
  outputsCount: number,
): { width: number; height: number } {
  const portRows = Math.max(inputsCount + outputsCount, 1);
  return {
    width: NODE_WIDTH,
    height: NODE_HEADER_HEIGHT + portRows * PORT_ROW_HEIGHT + NODE_FOOTER_PADDING,
  };
}

export function computeDagrePositions(
  workflow: Workflow,
  opsMap: Record<string, OpEntry> = {},
): Record<string, NodePosition> {
  const nodesDef = workflow.nodes ?? {};
  const stageIds = getOrderedStageIds(workflow);
  const nodesByStage: Record<string, Array<string>> = {};
  for (const sid of stageIds) {
    nodesByStage[sid] = [];
  }
  for (const [nodeId, spec] of Object.entries(nodesDef)) {
    const sid = spec.stage || DEFAULT_STAGE_ID;
    if (!nodesByStage[sid]) {
      nodesByStage[sid] = [];
    }
    nodesByStage[sid].push(nodeId);
  }

  const positions: Record<string, NodePosition> = {};
  let stageOffsetX = STAGE_PAD_X;

  for (const sid of stageIds) {
    const memberIds = nodesByStage[sid] ?? [];
    if (memberIds.length === 0) {
      stageOffsetX += EMPTY_STAGE_WIDTH + STAGE_GAP_X;
      continue;
    }

    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: "LR",
      nodesep: 36,
      ranksep: 72,
      marginx: 0,
      marginy: 0,
    });

    const memberSet = new Set(memberIds);
    const dimsMap: Record<string, { width: number; height: number }> = {};

    for (const nodeId of memberIds) {
      const spec = nodesDef[nodeId];
      const ports = resolveNodePorts(nodeId, spec, workflow, opsMap[spec.op]);
      const dims = estimateNodeDimensions(ports.inputs.length, ports.outputs.length);
      dimsMap[nodeId] = dims;
      g.setNode(nodeId, { width: dims.width, height: dims.height });
    }

    // Add intra-stage edges to Dagre
    for (const nodeId of memberIds) {
      const spec = nodesDef[nodeId];
      for (const val of Object.values(spec.inputs ?? {})) {
        const ref = extractNodeRef(val);
        if (ref && memberSet.has(ref.from_node) && ref.from_node !== nodeId) {
          g.setEdge(ref.from_node, nodeId);
        }
      }
    }

    dagre.layout(g);

    let minX = Infinity;
    let minY = Infinity;
    let maxRight = -Infinity;

    for (const nodeId of memberIds) {
      const layoutNode = g.node(nodeId);
      const dims = dimsMap[nodeId];
      const left = layoutNode.x - dims.width / 2;
      const top = layoutNode.y - dims.height / 2;
      if (left < minX) minX = left;
      if (top < minY) minY = top;
      if (left + dims.width > maxRight) maxRight = left + dims.width;
    }

    const normMinX = Number.isFinite(minX) ? minX : 0;
    const normMinY = Number.isFinite(minY) ? minY : 0;
    const stageContentWidth = Number.isFinite(maxRight)
      ? Math.max(maxRight - normMinX, NODE_WIDTH)
      : NODE_WIDTH;

    for (const nodeId of memberIds) {
      const layoutNode = g.node(nodeId);
      const dims = dimsMap[nodeId];
      const left = layoutNode.x - dims.width / 2 - normMinX;
      const top = layoutNode.y - dims.height / 2 - normMinY;
      positions[nodeId] = {
        x: Math.round(stageOffsetX + left),
        y: Math.round(STAGE_PAD_TOP + top),
      };
    }

    stageOffsetX += stageContentWidth + STAGE_PAD_X * 2 + STAGE_GAP_X;
  }

  return positions;
}

export interface BuildGraphOptions {
  layout?: WorkflowLayout | null;
  opsMap?: Record<string, OpEntry>;
  runState?: RunState | null;
  runDiff?: WorkflowRunDiff | null;
  selectedNodeId?: string;
  readOnly?: boolean;
  onLiteralChange?: (nodeId: string, portName: string, value: unknown) => void;
  onPreviewOutput?: (nodeId: string, output: OutputPortSpec) => void;
}

export interface BuiltGraphElements {
  nodes: Array<GraphNode>;
  edges: Array<Edge>;
  absolutePositions: Record<string, NodePosition>;
  stageGroupPositions: Record<string, NodePosition>;
}

export function buildGraphElements(
  workflow: Workflow,
  options: BuildGraphOptions = {},
): BuiltGraphElements {
  const {
    layout = null,
    opsMap = {},
    runState = null,
    runDiff = null,
    selectedNodeId,
    readOnly = true,
    onLiteralChange,
    onPreviewOutput,
  } = options;

  const nodesDef = workflow.nodes ?? {};
  const stagesDef: Record<string, Stage> = workflow.stages ?? {};
  const stageIds = getOrderedStageIds(workflow);

  const dagrePositions = computeDagrePositions(workflow, opsMap);
  const absolutePositions: Record<string, NodePosition> = {};

  for (const nodeId of Object.keys(nodesDef)) {
    const saved = layout?.nodes?.[nodeId];
    if (saved && typeof saved.x === "number" && typeof saved.y === "number") {
      absolutePositions[nodeId] = { x: saved.x, y: saved.y };
    } else {
      absolutePositions[nodeId] = dagrePositions[nodeId] ?? { x: STAGE_PAD_X, y: STAGE_PAD_TOP };
    }
  }

  const nodesByStage: Record<string, Array<string>> = {};
  for (const sid of stageIds) {
    nodesByStage[sid] = [];
  }
  for (const [nodeId, spec] of Object.entries(nodesDef)) {
    const sid = spec.stage || DEFAULT_STAGE_ID;
    if (!nodesByStage[sid]) {
      nodesByStage[sid] = [];
    }
    nodesByStage[sid].push(nodeId);
  }

  const stageNodes: Array<StageGroupGraphNode> = [];
  const childNodes: Array<WorkflowGraphNode> = [];
  const stageGroupPositions: Record<string, NodePosition> = {};

  let emptyStageCursorX = 0;

  for (const sid of stageIds) {
    const memberIds = nodesByStage[sid] ?? [];
    const stageSpec = stagesDef[sid];
    const title =
      stageSpec?.title ||
      (sid === DEFAULT_STAGE_ID ? DEFAULT_STAGE_TITLE : sid);
    const requireApproval = Boolean(stageSpec?.require_approval);
    const gateState = runState?.stage_gates?.[sid];

    let groupX: number;
    let groupY: number;
    let groupWidth: number;
    let groupHeight: number;

    if (memberIds.length === 0) {
      groupX = emptyStageCursorX;
      groupY = 0;
      groupWidth = EMPTY_STAGE_WIDTH;
      groupHeight = EMPTY_STAGE_HEIGHT;
      emptyStageCursorX = groupX + groupWidth + STAGE_GAP_X;
    } else {
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;

      for (const nodeId of memberIds) {
        const spec = nodesDef[nodeId];
        const pos = absolutePositions[nodeId];
        const ports = resolveNodePorts(nodeId, spec, workflow, opsMap[spec.op]);
        const dims = estimateNodeDimensions(ports.inputs.length, ports.outputs.length);
        if (pos.x < minX) minX = pos.x;
        if (pos.y < minY) minY = pos.y;
        if (pos.x + dims.width > maxX) maxX = pos.x + dims.width;
        if (pos.y + dims.height > maxY) maxY = pos.y + dims.height;
      }

      groupX = Math.round(minX - STAGE_PAD_X);
      groupY = Math.round(minY - STAGE_PAD_TOP);
      groupWidth = Math.round(maxX - minX + STAGE_PAD_X * 2);
      groupHeight = Math.round(maxY - minY + STAGE_PAD_TOP + STAGE_PAD_BOTTOM);
      emptyStageCursorX = Math.max(emptyStageCursorX, groupX + groupWidth + STAGE_GAP_X);
    }

    const groupId = stageGroupId(sid);
    stageGroupPositions[sid] = { x: groupX, y: groupY };

    stageNodes.push({
      id: groupId,
      type: "stageGroup",
      position: { x: groupX, y: groupY },
      style: {
        width: groupWidth,
        height: groupHeight,
        zIndex: -1,
      },
      draggable: false,
      selectable: false,
      focusable: false,
      data: {
        stageId: sid,
        title,
        requireApproval,
        gateState,
        nodeCount: memberIds.length,
      },
    });

    for (const nodeId of memberIds) {
      const spec = nodesDef[nodeId];
      const opEntry = opsMap[spec.op];
      const ports = resolveNodePorts(nodeId, spec, workflow, opEntry);
      const nodeState: NodeRunState | undefined = runState?.nodes?.[nodeId];
      const absPos = absolutePositions[nodeId];

      childNodes.push({
        id: nodeId,
        type: "workflowNode",
        parentId: groupId,
        position: {
          x: Math.round(absPos.x - groupX),
          y: Math.round(absPos.y - groupY),
        },
        selected: selectedNodeId === nodeId,
        draggable: !readOnly,
        data: {
          nodeId,
          spec,
          opEntry,
          nodeState,
          nodeDiff: runDiff?.nodes?.[nodeId],
          inputs: ports.inputs,
          outputs: ports.outputs,
          isSelected: selectedNodeId === nodeId,
          readOnly,
          onLiteralChange,
          onPreviewOutput,
        },
      });
    }
  }

  // Build edges from NodeRef inputs
  const edges: Array<Edge> = [];
  for (const [targetId, spec] of Object.entries(nodesDef)) {
    const targetState = runState?.nodes?.[targetId];
    for (const [portName, val] of Object.entries(spec.inputs ?? {})) {
      const ref = extractNodeRef(val);
      if (!ref || !nodesDef[ref.from_node]) continue;

      const sourceState = runState?.nodes?.[ref.from_node];
      const isRunning =
        sourceState?.status === "RUNNING" ||
        targetState?.status === "RUNNING" ||
        targetState?.status === "BUILDING_ENVIRONMENT";

      let stroke = "#777777";
      if (sourceState?.status === "SUCCESS") {
        stroke = "#38c172";
      } else if (sourceState?.status === "FAILED") {
        stroke = "#f44336";
      } else if (isRunning) {
        stroke = "#00d8ff";
      }

      edges.push({
        id: `${ref.from_node}.${ref.output}->${targetId}.${portName}`,
        source: ref.from_node,
        sourceHandle: outputHandleId(ref.output),
        target: targetId,
        targetHandle: inputHandleId(portName),
        animated: isRunning,
        style: {
          stroke,
          strokeWidth: 4,
        },
        data: {
          fromNode: ref.from_node,
          output: ref.output,
          toNode: targetId,
          input: portName,
        },
      });
    }
  }

  // React Flow requires parent nodes to appear before child nodes
  return {
    nodes: [...stageNodes, ...childNodes],
    edges,
    absolutePositions,
    stageGroupPositions,
  };
}
