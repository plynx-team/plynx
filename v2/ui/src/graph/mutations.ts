import type {
  NodePosition,
  NodeSpec,
  OpEntry,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import {
  computeDagrePositions,
  DEFAULT_STAGE_ID,
  getOrderedStageIds,
  STAGE_PAD_TOP,
  STAGE_PAD_X,
} from "./layout";
import { extractNodeRef } from "./types";

export function toSnakeCaseId(raw: string): string {
  const withUnderscores = raw
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .toLowerCase()
    .replace(/^_+|_+$/g, "");
  if (!withUnderscores) return "node";
  if (/^[a-z]/.test(withUnderscores)) return withUnderscores;
  return `n_${withUnderscores}`;
}

export function generateNodeId(
  baseName: string,
  existingIds: Iterable<string>,
): string {
  const existing = new Set(existingIds);
  const base = toSnakeCaseId(baseName);
  if (!existing.has(base)) {
    return base;
  }
  let suffix = 2;
  while (existing.has(`${base}_${suffix}`)) {
    suffix += 1;
  }
  return `${base}_${suffix}`;
}

export function ensureLayout(
  workflow: Workflow,
  layout: WorkflowLayout | null | undefined,
  opsMap: Record<string, OpEntry> = {},
): WorkflowLayout {
  const dagrePositions = computeDagrePositions(workflow, opsMap);
  const nodes: Record<string, NodePosition> = {};
  for (const nodeId of Object.keys(workflow.nodes ?? {})) {
    const existing = layout?.nodes?.[nodeId];
    if (existing && typeof existing.x === "number" && typeof existing.y === "number") {
      nodes[nodeId] = { x: existing.x, y: existing.y };
    } else {
      nodes[nodeId] = dagrePositions[nodeId] ?? { x: STAGE_PAD_X, y: STAGE_PAD_TOP };
    }
  }
  return {
    schema: 1,
    nodes,
    viewport: layout?.viewport
      ? { ...layout.viewport }
      : { x: 0, y: 0, zoom: 1 },
  };
}

export function addNodeToWorkflow(
  workflow: Workflow,
  layout: WorkflowLayout | null | undefined,
  op: OpEntry,
  options: {
    stageId?: string;
    position?: NodePosition;
    opsMap?: Record<string, OpEntry>;
  } = {},
): {
  workflow: Workflow;
  layout: WorkflowLayout;
  nodeId: string;
} {
  const opsMap = options.opsMap ?? {};
  const existingNodes = workflow.nodes ?? {};
  const orderedStages = getOrderedStageIds(workflow);
  const targetStage =
    options.stageId ||
    orderedStages[orderedStages.length - 1] ||
    DEFAULT_STAGE_ID;

  const nodeId = generateNodeId(op.name, Object.keys(existingNodes));
  const newSpec: NodeSpec = {
    op: op.id,
    title: op.title || op.name,
    stage: targetStage,
    inputs: {},
  };

  const baseLayout = ensureLayout(workflow, layout, opsMap);

  let pos: NodePosition;
  if (options.position) {
    pos = {
      x: Math.round(options.position.x),
      y: Math.round(options.position.y),
    };
  } else {
    // Place below the lowest node currently in targetStage, or compute via Dagre
    const sameStagePositions = Object.entries(existingNodes)
      .filter(([, spec]) => (spec.stage || DEFAULT_STAGE_ID) === targetStage)
      .map(([id]) => baseLayout.nodes[id])
      .filter((p): p is NodePosition => Boolean(p));

    if (sameStagePositions.length > 0) {
      const minX = Math.min(...sameStagePositions.map((p) => p.x));
      const maxY = Math.max(...sameStagePositions.map((p) => p.y));
      pos = { x: Math.round(minX), y: Math.round(maxY + 150) };
    } else {
      const nextWfPreview: Workflow = {
        ...workflow,
        nodes: { ...existingNodes, [nodeId]: newSpec },
      };
      const computed = computeDagrePositions(nextWfPreview, {
        ...opsMap,
        [op.id]: op,
      });
      pos = computed[nodeId] ?? { x: STAGE_PAD_X, y: STAGE_PAD_TOP };
    }
  }

  const nextStages = { ...(workflow.stages ?? {}) };
  if (!nextStages[targetStage]) {
    nextStages[targetStage] = {
      title: targetStage === DEFAULT_STAGE_ID ? "Workflow" : targetStage,
      require_approval: false,
    };
  }

  const nextWorkflow: Workflow = {
    ...workflow,
    stages: nextStages,
    nodes: {
      ...existingNodes,
      [nodeId]: newSpec,
    },
  };

  const nextLayout: WorkflowLayout = {
    schema: 1,
    nodes: {
      ...baseLayout.nodes,
      [nodeId]: pos,
    },
    viewport: { ...baseLayout.viewport },
  };

  return { workflow: nextWorkflow, layout: nextLayout, nodeId };
}

export function duplicateNodeInWorkflow(
  workflow: Workflow,
  layout: WorkflowLayout | null | undefined,
  sourceNodeId: string,
  opsMap: Record<string, OpEntry> = {},
): {
  workflow: Workflow;
  layout: WorkflowLayout;
  nodeId: string;
} | null {
  const existingNodes = workflow.nodes ?? {};
  const sourceSpec = existingNodes[sourceNodeId];
  if (!sourceSpec) return null;

  const baseLayout = ensureLayout(workflow, layout, opsMap);
  const nodeId = generateNodeId(`${sourceNodeId}_copy`, Object.keys(existingNodes));

  const clonedInputs: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(sourceSpec.inputs ?? {})) {
    if (v !== null && typeof v === "object") {
      clonedInputs[k] = JSON.parse(JSON.stringify(v)) as unknown;
    } else {
      clonedInputs[k] = v;
    }
  }

  const clonedSpec: NodeSpec = {
    op: sourceSpec.op,
    title: sourceSpec.title ? `${sourceSpec.title} (copy)` : null,
    stage: sourceSpec.stage || DEFAULT_STAGE_ID,
    inputs: clonedInputs,
  };

  const sourcePos = baseLayout.nodes[sourceNodeId] ?? {
    x: STAGE_PAD_X,
    y: STAGE_PAD_TOP,
  };

  const nextWorkflow: Workflow = {
    ...workflow,
    nodes: {
      ...existingNodes,
      [nodeId]: clonedSpec,
    },
  };

  const nextLayout: WorkflowLayout = {
    schema: 1,
    nodes: {
      ...baseLayout.nodes,
      [nodeId]: {
        x: Math.round(sourcePos.x + 40),
        y: Math.round(sourcePos.y + 140),
      },
    },
    viewport: { ...baseLayout.viewport },
  };

  return { workflow: nextWorkflow, layout: nextLayout, nodeId };
}

export function deleteNodeFromWorkflow(
  workflow: Workflow,
  layout: WorkflowLayout | null | undefined,
  targetNodeId: string,
  opsMap: Record<string, OpEntry> = {},
): {
  workflow: Workflow;
  layout: WorkflowLayout;
} {
  const existingNodes = workflow.nodes ?? {};
  const baseLayout = ensureLayout(workflow, layout, opsMap);

  const nextNodes: Record<string, NodeSpec> = {};
  for (const [nodeId, spec] of Object.entries(existingNodes)) {
    if (nodeId === targetNodeId) continue;

    // Remove any input references pointing to the deleted node
    let inputsChanged = false;
    const cleanedInputs: Record<string, unknown> = {};
    for (const [portName, val] of Object.entries(spec.inputs ?? {})) {
      const ref = extractNodeRef(val);
      if (ref && ref.from_node === targetNodeId) {
        inputsChanged = true;
        continue;
      }
      cleanedInputs[portName] = val;
    }

    nextNodes[nodeId] = inputsChanged
      ? { ...spec, inputs: cleanedInputs }
      : spec;
  }

  const nextLayoutNodes = { ...baseLayout.nodes };
  delete nextLayoutNodes[targetNodeId];

  return {
    workflow: {
      ...workflow,
      nodes: nextNodes,
    },
    layout: {
      schema: 1,
      nodes: nextLayoutNodes,
      viewport: { ...baseLayout.viewport },
    },
  };
}
