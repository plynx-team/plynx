import type { Connection } from "@xyflow/react";
import type {
  InputPortSpec,
  OpEntry,
  OutputPortSpec,
  Workflow,
} from "../api/types.gen";
import { DEFAULT_STAGE_ID, getOrderedStageIds, resolveNodePorts } from "./layout";
import { extractNodeRef, parseHandleId } from "./types";

export type PortCompatibilityResult =
  | { valid: true }
  | { valid: false; reason: string };

export function portsCompatible(
  src: OutputPortSpec,
  dst: InputPortSpec,
): PortCompatibilityResult {
  if (src.type !== dst.type && !(src.type === "int" && dst.type === "float")) {
    return {
      valid: false,
      reason: `Port type mismatch: output "${src.name}" (${src.type}) cannot connect to input "${dst.name}" (${dst.type})`,
    };
  }
  if (
    dst.type === "file" &&
    dst.media &&
    src.media &&
    dst.media !== src.media
  ) {
    return {
      valid: false,
      reason: `Media mismatch: output "${src.name}" (${src.media}) cannot connect to input "${dst.name}" (${dst.media})`,
    };
  }
  return { valid: true };
}

export function wouldCreateCycle(
  workflow: Workflow,
  sourceNodeId: string,
  targetNodeId: string,
): boolean {
  if (sourceNodeId === targetNodeId) return true;

  // Build forward adjacency list: upstream -> downstream nodes
  const adjacency: Record<string, Array<string>> = {};
  for (const [nodeId, spec] of Object.entries(workflow.nodes ?? {})) {
    for (const val of Object.values(spec.inputs ?? {})) {
      const ref = extractNodeRef(val);
      if (!ref) continue;
      if (!adjacency[ref.from_node]) {
        adjacency[ref.from_node] = [];
      }
      adjacency[ref.from_node].push(nodeId);
    }
  }

  // BFS from targetNodeId: if we can reach sourceNodeId, adding source -> target creates a cycle
  const visited = new Set<string>();
  const queue: Array<string> = [targetNodeId];
  while (queue.length > 0) {
    const cur = queue.shift()!;
    if (cur === sourceNodeId) return true;
    if (visited.has(cur)) continue;
    visited.add(cur);
    for (const next of adjacency[cur] ?? []) {
      if (!visited.has(next)) {
        queue.push(next);
      }
    }
  }
  return false;
}

export type ConnectionValidationResult =
  | {
      valid: true;
      sourceNodeId: string;
      sourcePort: string;
      targetNodeId: string;
      targetPort: string;
    }
  | {
      valid: false;
      reason: string;
    };

export function validateConnection(
  connection: Connection,
  workflow: Workflow,
  opsMap: Record<string, OpEntry> = {},
): ConnectionValidationResult {
  const { source, target, sourceHandle, targetHandle } = connection;
  if (!source || !target) {
    return { valid: false, reason: "Connection is missing source or target node" };
  }

  const parsedSource = parseHandleId(sourceHandle);
  const parsedTarget = parseHandleId(targetHandle);
  const sourcePortName = parsedSource?.name ?? sourceHandle ?? "";
  const targetPortName = parsedTarget?.name ?? targetHandle ?? "";

  if (!sourcePortName || !targetPortName) {
    return { valid: false, reason: "Connection is missing source or target port" };
  }

  if (source === target) {
    return { valid: false, reason: "Cannot connect a node to itself" };
  }

  const nodesDef = workflow.nodes ?? {};
  const srcSpec = nodesDef[source];
  const dstSpec = nodesDef[target];
  if (!srcSpec || !dstSpec) {
    return { valid: false, reason: "Source or target node does not exist" };
  }

  // Stage order check: inter-stage edges must go forward only (PROTOCOL.md section 2)
  const orderedStages = getOrderedStageIds(workflow);
  const stageIndex: Record<string, number> = {};
  orderedStages.forEach((sid, idx) => {
    stageIndex[sid] = idx;
  });

  const srcStage = srcSpec.stage || DEFAULT_STAGE_ID;
  const dstStage = dstSpec.stage || DEFAULT_STAGE_ID;
  const srcIdx = stageIndex[srcStage] ?? 0;
  const dstIdx = stageIndex[dstStage] ?? 0;
  if (dstIdx < srcIdx) {
    return {
      valid: false,
      reason: `Backward stage edge: cannot connect "${source}" (stage "${srcStage}") to "${target}" (stage "${dstStage}")`,
    };
  }

  // Cycle check
  if (wouldCreateCycle(workflow, source, target)) {
    return {
      valid: false,
      reason: `Cycle detected: connecting "${source}" to "${target}" would create a cycle`,
    };
  }

  // Port type and media compatibility
  const srcOp = opsMap[srcSpec.op];
  const dstOp = opsMap[dstSpec.op];
  const srcPorts = resolveNodePorts(source, srcSpec, workflow, srcOp);
  const dstPorts = resolveNodePorts(target, dstSpec, workflow, dstOp);

  const srcPort = srcPorts.outputs.find((p) => p.name === sourcePortName);
  const dstPort = dstPorts.inputs.find((p) => p.name === targetPortName);

  if (srcOp && !srcPort) {
    return {
      valid: false,
      reason: `Unknown output port "${sourcePortName}" on node "${source}"`,
    };
  }
  if (dstOp && !dstPort) {
    return {
      valid: false,
      reason: `Unknown input port "${targetPortName}" on node "${target}"`,
    };
  }

  if (srcPort && dstPort) {
    const compat = portsCompatible(srcPort, dstPort);
    if (!compat.valid) {
      return compat;
    }
  }

  return {
    valid: true,
    sourceNodeId: source,
    sourcePort: sourcePortName,
    targetNodeId: target,
    targetPort: targetPortName,
  };
}

export function getCompatibleUpstreamOutputs(
  workflow: Workflow,
  targetNodeId: string,
  targetPort: InputPortSpec,
  opsMap: Record<string, OpEntry> = {},
): Array<{ nodeId: string; output: OutputPortSpec }> {
  const nodesDef = workflow.nodes ?? {};
  const dstSpec = nodesDef[targetNodeId];
  if (!dstSpec) return [];

  const orderedStages = getOrderedStageIds(workflow);
  const stageIndex: Record<string, number> = {};
  orderedStages.forEach((sid, idx) => {
    stageIndex[sid] = idx;
  });
  const dstIdx = stageIndex[dstSpec.stage || DEFAULT_STAGE_ID] ?? 0;

  const candidates: Array<{ nodeId: string; output: OutputPortSpec }> = [];
  for (const [srcNodeId, srcSpec] of Object.entries(nodesDef)) {
    if (srcNodeId === targetNodeId) continue;
    const srcIdx = stageIndex[srcSpec.stage || DEFAULT_STAGE_ID] ?? 0;
    if (dstIdx < srcIdx) continue;
    if (wouldCreateCycle(workflow, srcNodeId, targetNodeId)) continue;

    const srcPorts = resolveNodePorts(
      srcNodeId,
      srcSpec,
      workflow,
      opsMap[srcSpec.op],
    );
    for (const outPort of srcPorts.outputs) {
      if (portsCompatible(outPort, targetPort).valid) {
        candidates.push({ nodeId: srcNodeId, output: outPort });
      }
    }
  }
  return candidates;
}

export function validateStageChange(
  workflow: Workflow,
  nodeId: string,
  newStage: string,
): { valid: true } | { valid: false; reason: string } {
  const nodesDef = workflow.nodes ?? {};
  const spec = nodesDef[nodeId];
  if (!spec) {
    return { valid: false, reason: `Node "${nodeId}" does not exist` };
  }

  const orderedStages = getOrderedStageIds(workflow);
  if (!orderedStages.includes(newStage)) {
    orderedStages.push(newStage);
  }
  const stageIndex: Record<string, number> = {};
  orderedStages.forEach((sid, idx) => {
    stageIndex[sid] = idx;
  });

  const newIdx = stageIndex[newStage] ?? 0;

  // Check incoming edges to nodeId
  for (const val of Object.values(spec.inputs ?? {})) {
    const ref = extractNodeRef(val);
    if (!ref || !nodesDef[ref.from_node]) continue;
    const srcStage = nodesDef[ref.from_node].stage || DEFAULT_STAGE_ID;
    const srcIdx = stageIndex[srcStage] ?? 0;
    if (newIdx < srcIdx) {
      return {
        valid: false,
        reason: `Cannot move "${nodeId}" to stage "${newStage}": upstream "${ref.from_node}" is in later stage "${srcStage}"`,
      };
    }
  }

  // Check outgoing edges from nodeId
  for (const [otherId, otherSpec] of Object.entries(nodesDef)) {
    if (otherId === nodeId) continue;
    for (const val of Object.values(otherSpec.inputs ?? {})) {
      const ref = extractNodeRef(val);
      if (ref && ref.from_node === nodeId) {
        const dstStage = otherSpec.stage || DEFAULT_STAGE_ID;
        const dstIdx = stageIndex[dstStage] ?? 0;
        if (dstIdx < newIdx) {
          return {
            valid: false,
            reason: `Cannot move "${nodeId}" to stage "${newStage}": downstream "${otherId}" is in earlier stage "${dstStage}"`,
          };
        }
      }
    }
  }

  return { valid: true };
}
