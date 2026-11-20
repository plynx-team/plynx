import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type Edge,
  type NodeTypes,
  type OnEdgesChange,
  type OnMoveEnd,
  type OnNodesChange,
} from "@xyflow/react";
import type {
  OpEntry,
  OutputPortSpec,
  RunState,
  Workflow,
  WorkflowDocument,
  WorkflowLayout,
} from "../api/types.gen";
import { buildGraphElements } from "./layout";
import { OP_DRAG_MIME } from "./OpPalette";
import type { WorkflowRunDiff } from "./runDiff";
import { StageGroupNode } from "./StageGroupNode";
import { extractStageId, isStageGroupId, type GraphNode } from "./types";
import { WorkflowNode } from "./WorkflowNode";

const NODE_TYPES: NodeTypes = {
  stageGroup: StageGroupNode,
  workflowNode: WorkflowNode,
};

export interface GraphViewProps {
  workflowDoc?: WorkflowDocument | null;
  workflow?: Workflow | null;
  layout?: WorkflowLayout | null;
  runState?: RunState | null;
  runDiff?: WorkflowRunDiff | null;
  ops?: ReadonlyArray<OpEntry>;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string | undefined) => void;
  selectedEdgeId?: string;
  onSelectEdge?: (edgeId: string | undefined) => void;
  selectedStageId?: string;
  onSelectStage?: (stageId: string | undefined) => void;
  onDeleteStage?: (stageId: string) => void;
  readOnly?: boolean;
  onNodesChange?: OnNodesChange<GraphNode>;
  onEdgesChange?: OnEdgesChange<Edge>;
  onConnect?: (connection: Connection) => void;
  onNodeDragStop?: (nodeId: string, absX: number, absY: number) => void;
  onStageDragStop?: (stageId: string, dx: number, dy: number) => void;
  onDropOp?: (opId: string, position: { x: number; y: number }) => void;
  onViewportChange?: (viewport: { x: number; y: number; zoom: number }) => void;
  onLiteralChange?: (nodeId: string, portName: string, value: unknown) => void;
  onPreviewOutput?: (nodeId: string, output: OutputPortSpec) => void;
  hasSavedViewport?: boolean;
  fitViewTrigger?: number;
  heightClassName?: string;
}

function synthesizeWorkflowFromRun(runState: RunState): Workflow {
  const nodes: Workflow["nodes"] = {};
  for (const nodeId of Object.keys(runState.nodes)) {
    nodes[nodeId] = {
      op: "unknown",
      stage: "main",
      inputs: {},
    };
  }
  return {
    version: 1,
    name: runState.workflow_path,
    stages: { main: { title: "Workflow", require_approval: false } },
    nodes,
  };
}

function GraphCanvasInner({
  workflowDoc,
  workflow: workflowProp,
  layout: layoutProp,
  runState,
  runDiff = null,
  ops = [],
  selectedNodeId,
  onSelectNode,
  selectedEdgeId,
  onSelectEdge,
  selectedStageId,
  onSelectStage,
  onDeleteStage,
  readOnly = true,
  onNodesChange: externalOnNodesChange,
  onEdgesChange,
  onConnect,
  onNodeDragStop,
  onStageDragStop,
  onDropOp,
  onViewportChange,
  onLiteralChange,
  onPreviewOutput,
  hasSavedViewport,
  fitViewTrigger = 0,
  heightClassName = "h-full",
}: GraphViewProps) {
  const reactFlow = useReactFlow<GraphNode, Edge>();

  const effectiveWorkflow = useMemo<Workflow | null>(() => {
    if (workflowProp) return workflowProp;
    if (workflowDoc?.workflow) return workflowDoc.workflow;
    if (runState) return synthesizeWorkflowFromRun(runState);
    return null;
  }, [workflowProp, workflowDoc, runState]);

  const effectiveLayout = layoutProp ?? workflowDoc?.layout ?? null;

  const opsMap = useMemo<Record<string, OpEntry>>(() => {
    const map: Record<string, OpEntry> = {};
    for (const entry of ops) {
      map[entry.id] = entry;
    }
    return map;
  }, [ops]);

  const measuredDimsRef = useRef<
    Record<string, { width: number; height: number }>
  >({});
  const [measuredDims, setMeasuredDims] = useState<
    Record<string, { width: number; height: number }>
  >({});

  const built = useMemo(() => {
    if (!effectiveWorkflow) {
      return {
        nodes: [] as Array<GraphNode>,
        edges: [] as Array<Edge>,
        stageGroupPositions: {} as Record<string, { x: number; y: number }>,
      };
    }
    return buildGraphElements(effectiveWorkflow, {
      layout: effectiveLayout,
      opsMap,
      runState,
      runDiff,
      selectedNodeId,
      selectedStageId,
      onSelectStage,
      onDeleteStage,
      readOnly,
      onLiteralChange,
      onPreviewOutput,
      measuredDimensions: measuredDims,
    });
  }, [
    effectiveWorkflow,
    effectiveLayout,
    opsMap,
    runState,
    runDiff,
    selectedNodeId,
    selectedStageId,
    onSelectStage,
    onDeleteStage,
    readOnly,
    onLiteralChange,
    onPreviewOutput,
    measuredDims,
  ]);

  const [rfNodes, setRfNodes] = useState<Array<GraphNode>>(built.nodes);

  useEffect(() => {
    setRfNodes(built.nodes);
  }, [built.nodes]);

  useEffect(() => {
    if (fitViewTrigger > 0) {
      requestAnimationFrame(() => {
        void reactFlow.fitView({ padding: 0.2 });
      });
    }
  }, [fitViewTrigger, reactFlow]);

  const useSavedViewport =
    hasSavedViewport ?? Boolean(effectiveLayout?.viewport);

  const renderedEdges = useMemo(() => {
    if (!selectedEdgeId) return built.edges;
    return built.edges.map((edge) =>
      edge.id === selectedEdgeId
        ? {
            ...edge,
            selected: true,
            style: {
              ...edge.style,
              stroke: "#2680eb",
              strokeWidth: 5,
            },
          }
        : edge,
    );
  }, [built.edges, selectedEdgeId]);

  const handleNodesChange: OnNodesChange<GraphNode> = useCallback(
    (changes) => {
      let dimsChanged = false;
      const nextDims = { ...measuredDimsRef.current };
      for (const change of changes) {
        if (
          change.type === "dimensions" &&
          change.dimensions &&
          change.dimensions.width > 0 &&
          change.dimensions.height > 0
        ) {
          const prev = nextDims[change.id];
          if (
            !prev ||
            Math.abs(prev.width - change.dimensions.width) > 1 ||
            Math.abs(prev.height - change.dimensions.height) > 1
          ) {
            nextDims[change.id] = change.dimensions;
            dimsChanged = true;
          }
        }
      }
      if (dimsChanged) {
        measuredDimsRef.current = nextDims;
        setMeasuredDims(nextDims);
      }

      if (!readOnly) {
        setRfNodes((prev) => changes.applyTo(prev));
      }
      externalOnNodesChange?.(changes);
    },
    [readOnly, externalOnNodesChange],
  );

  const handleMoveEnd: OnMoveEnd | undefined = onViewportChange
    ? (event, viewport) => {
        if (!event) return;
        onViewportChange({
          x: Math.round(viewport.x * 100) / 100,
          y: Math.round(viewport.y * 100) / 100,
          zoom: Math.round(viewport.zoom * 1000) / 1000,
        });
      }
    : undefined;

  if (!effectiveWorkflow) {
    return (
      <div
        data-testid="graph-view-empty"
        className={`flex ${heightClassName} items-center justify-center text-sm`}
        style={{
          backgroundColor: "var(--bg-canvas)",
          color: "var(--text-secondary)",
        }}
      >
        No workflow loaded.
      </div>
    );
  }

  return (
    <div
      data-testid="graph-view"
      className={`${heightClassName} relative w-full overflow-hidden`}
      style={{ backgroundColor: "var(--bg-canvas)" }}
      onDragOver={(e) => {
        if (readOnly || !onDropOp) return;
        if (e.dataTransfer.types.includes(OP_DRAG_MIME)) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }
      }}
      onDrop={(e) => {
        if (readOnly || !onDropOp) return;
        const opId = e.dataTransfer.getData(OP_DRAG_MIME);
        if (!opId) return;
        e.preventDefault();
        const flowPos = reactFlow.screenToFlowPosition({
          x: e.clientX,
          y: e.clientY,
        });
        onDropOp(opId, flowPos);
      }}
    >
      {/* Legacy v1 bottom-left workflow title watermark */}
      <div className="BackgroundLabels">
        <div className="Title">{effectiveWorkflow.name}</div>
        {effectiveWorkflow.description && (
          <div className="Description">{effectiveWorkflow.description}</div>
        )}
      </div>

      <ReactFlow<GraphNode, Edge>
        nodes={rfNodes}
        edges={renderedEdges}
        nodeTypes={NODE_TYPES}
        defaultViewport={
          useSavedViewport ? (effectiveLayout?.viewport ?? undefined) : undefined
        }
        fitView={!useSavedViewport}
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        edgesReconnectable={false}
        elementsSelectable={true}
        deleteKeyCode={null}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_event, node) => {
          if (!isStageGroupId(node.id)) {
            onSelectEdge?.(undefined);
            onSelectStage?.(undefined);
            onSelectNode?.(node.id);
          } else {
            onSelectNode?.(undefined);
            onSelectEdge?.(undefined);
            onSelectStage?.(extractStageId(node.id));
          }
        }}
        onEdgeClick={(_event, edge) => {
          if (!readOnly) {
            onSelectNode?.(undefined);
            onSelectStage?.(undefined);
            onSelectEdge?.(edge.id);
          }
        }}
        onPaneClick={() => {
          if (!readOnly) {
            onSelectNode?.(undefined);
            onSelectEdge?.(undefined);
            onSelectStage?.(undefined);
          }
        }}
        onNodeDragStop={(_event, node) => {
          if (isStageGroupId(node.id)) {
            if (!onStageDragStop) return;
            const stageId = extractStageId(node.id);
            const initialPos = built.stageGroupPositions[stageId] ?? { x: 0, y: 0 };
            const dx = Math.round(node.position.x - initialPos.x);
            const dy = Math.round(node.position.y - initialPos.y);
            if (dx !== 0 || dy !== 0) {
              onStageDragStop(stageId, dx, dy);
            }
            return;
          }
          if (!onNodeDragStop) return;
          const stageId = effectiveWorkflow.nodes?.[node.id]?.stage || "main";
          const groupPos = built.stageGroupPositions[stageId] ?? { x: 0, y: 0 };
          onNodeDragStop(
            node.id,
            Math.round(groupPos.x + node.position.x),
            Math.round(groupPos.y + node.position.y),
          );
        }}
        onMoveEnd={handleMoveEnd}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#383838" gap={16} size={1.5} />
        <Controls showInteractive={!readOnly} />
        <MiniMap
          nodeColor={(node) => {
            if (node.type === "stageGroup") return "#2b2b2b";
            const status = (node.data as { nodeState?: { status?: string } })
              ?.nodeState?.status;
            if (status === "SUCCESS") return "#38c172";
            if (status === "RUNNING") return "#00d8ff";
            if (status === "FAILED") return "#f44336";
            if (status === "WAITING_FOR_USER") return "#ffa726";
            return "#666666";
          }}
          maskColor="rgba(30, 30, 30, 0.6)"
        />
      </ReactFlow>
    </div>
  );
}

export function GraphView(props: GraphViewProps) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
