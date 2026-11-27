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
  type OnConnectStartParams,
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
import {
  buildGraphElements,
  DEFAULT_STAGE_ID,
  findClosestStage,
  findStageAtPosition,
  type RunLayoutMode,
} from "./layout";
import { OP_DRAG_MIME } from "./OpPalette";
import type { WorkflowRunDiff } from "./runDiff";
import { StageGroupNode } from "./StageGroupNode";
import {
  extractStageId,
  isStageGroupId,
  isStageValidatorNodeId,
  type GraphNode,
  type StageGroupGraphNode,
} from "./types";
import { WorkflowNode } from "./WorkflowNode";

const NODE_TYPES: NodeTypes = {
  stageGroup: StageGroupNode,
  workflowNode: WorkflowNode,
};

export interface WireDropOnPaneEvent {
  originNodeId: string;
  originHandleId: string;
  handleType: "source" | "target";
  screenPos: { x: number; y: number };
  flowPos: { x: number; y: number };
  stageId: string;
}

export interface GraphViewProps {
  workflowDoc?: WorkflowDocument | null;
  workflow?: Workflow | null;
  layout?: WorkflowLayout | null;
  runLayoutMode?: RunLayoutMode;
  runState?: RunState | null;
  runDiff?: WorkflowRunDiff | null;
  ops?: ReadonlyArray<OpEntry>;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string | undefined) => void;
  selectedEdgeId?: string;
  onSelectEdge?: (edgeId: string | undefined) => void;
  selectedStageId?: string;
  onSelectStage?: (stageId: string | undefined) => void;
  onSelectValidator?: (stageId: string, validatorNodeId: string) => void;
  onDeleteStage?: (stageId: string) => void;
  readOnly?: boolean;
  onNodesChange?: OnNodesChange<GraphNode>;
  onEdgesChange?: OnEdgesChange<Edge>;
  onConnect?: (connection: Connection) => void;
  onNodeDragStop?: (nodeId: string, absX: number, absY: number) => void;
  onStageDragStop?: (stageId: string, dx: number, dy: number) => void;
  onDropOp?: (
    opId: string,
    position: { x: number; y: number },
    stageId?: string,
  ) => void;
  onWireDropOnPane?: (event: WireDropOnPaneEvent) => void;
  onViewportChange?: (viewport: { x: number; y: number; zoom: number }) => void;
  onLiteralChange?: (nodeId: string, portName: string, value: unknown) => void;
  onPreviewOutput?: (nodeId: string, output: OutputPortSpec) => void;
  onMeasuredDimensionsChange?: (
    dims: Record<string, { width: number; height: number }>,
  ) => void;
  hasSavedViewport?: boolean;
  fitViewTrigger?: number;
  heightClassName?: string;
}

function synthesizeWorkflowFromRun(runState: RunState): Workflow {
  const nodes: Workflow["nodes"] = {};
  for (const nodeId of Object.keys(runState.nodes)) {
    if (isStageValidatorNodeId(nodeId)) {
      continue;
    }
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
  runLayoutMode = "original",
  runState,
  runDiff = null,
  ops = [],
  selectedNodeId,
  onSelectNode,
  selectedEdgeId,
  onSelectEdge,
  selectedStageId,
  onSelectStage,
  onSelectValidator,
  onDeleteStage,
  readOnly = true,
  onNodesChange: externalOnNodesChange,
  onEdgesChange,
  onConnect,
  onNodeDragStop,
  onStageDragStop,
  onDropOp,
  onWireDropOnPane,
  onViewportChange,
  onLiteralChange,
  onPreviewOutput,
  onMeasuredDimensionsChange,
  fitViewTrigger = 0,
  heightClassName = "h-full",
}: GraphViewProps) {
  const reactFlow = useReactFlow<GraphNode, Edge>();
  const containerRef = useRef<HTMLDivElement>(null);
  const connectingRef = useRef<OnConnectStartParams | null>(null);
  const didConnectRef = useRef<boolean>(false);

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
      runLayoutMode,
      opsMap,
      runState,
      runDiff,
      selectedNodeId,
      selectedStageId,
      onSelectStage,
      onSelectValidator,
      onDeleteStage,
      readOnly,
      onLiteralChange,
      onPreviewOutput,
      measuredDimensions: measuredDims,
    });
  }, [
    effectiveWorkflow,
    effectiveLayout,
    runLayoutMode,
    opsMap,
    runState,
    runDiff,
    selectedNodeId,
    selectedStageId,
    onSelectStage,
    onSelectValidator,
    onDeleteStage,
    readOnly,
    onLiteralChange,
    onPreviewOutput,
    measuredDims,
  ]);

  const [hoveredStageId, setHoveredStageId] = useState<string | undefined>(
    undefined,
  );

  const stageNodes = useMemo(() => {
    return built.nodes.filter((n): n is StageGroupGraphNode =>
      isStageGroupId(n.id),
    );
  }, [built.nodes]);

  const [rfNodes, setRfNodes] = useState<Array<GraphNode>>(built.nodes);

  useEffect(() => {
    if (!hoveredStageId) {
      setRfNodes(built.nodes);
    } else {
      setRfNodes(
        built.nodes.map((node): GraphNode => {
          if (node.type === "stageGroup") {
            const sid = extractStageId(node.id);
            const isTarget = sid === hoveredStageId;
            return {
              ...node,
              data: {
                ...node.data,
                isDropTarget: isTarget,
              },
            };
          }
          return node;
        }),
      );
    }
  }, [built.nodes, hoveredStageId]);

  useEffect(() => {
    if (fitViewTrigger > 0) {
      requestAnimationFrame(() => {
        void reactFlow.fitView({ padding: 0.2, minZoom: 0.125 });
      });
    }
  }, [fitViewTrigger, reactFlow]);

  const initialFitDoneRef = useRef(false);
  useEffect(() => {
    if (!initialFitDoneRef.current && rfNodes.length > 0) {
      initialFitDoneRef.current = true;
      requestAnimationFrame(() => {
        void reactFlow.fitView({ padding: 0.2, minZoom: 0.125 });
      });
    }
  }, [rfNodes.length, reactFlow]);

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
        onMeasuredDimensionsChange?.(nextDims);
      }

      if (!readOnly) {
        setRfNodes((prev) => changes.applyTo(prev));
      }
      externalOnNodesChange?.(changes);
    },
    [readOnly, externalOnNodesChange, onMeasuredDimensionsChange],
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
      ref={containerRef}
      data-testid="graph-view"
      className={`${heightClassName} relative w-full overflow-hidden`}
      style={{ backgroundColor: "var(--bg-canvas)" }}
      onDragOver={(e) => {
        if (readOnly || !onDropOp) return;
        const types = e.dataTransfer?.types;
        const hasOpMime = types ? Array.from(types).includes(OP_DRAG_MIME) : false;
        if (hasOpMime) {
          e.preventDefault();
          if (e.dataTransfer) {
            e.dataTransfer.dropEffect = "copy";
          }
          let flowPos = reactFlow.screenToFlowPosition({
            x: e.clientX,
            y: e.clientY,
          });
          if (!Number.isFinite(flowPos.x) || !Number.isFinite(flowPos.y)) {
            const vp = reactFlow.getViewport?.() ?? { x: 0, y: 0, zoom: 1 };
            const zoom = Number.isFinite(vp.zoom) && vp.zoom > 0 ? vp.zoom : 1;
            const vpX = Number.isFinite(vp.x) ? vp.x : 0;
            const vpY = Number.isFinite(vp.y) ? vp.y : 0;
            const containerRect = e.currentTarget.getBoundingClientRect();
            const clientX = Number.isFinite(e.clientX) ? e.clientX : 0;
            const clientY = Number.isFinite(e.clientY) ? e.clientY : 0;
            const left = Number.isFinite(containerRect?.left) ? containerRect.left : 0;
            const top = Number.isFinite(containerRect?.top) ? containerRect.top : 0;
            flowPos = {
              x: (clientX - left - vpX) / zoom,
              y: (clientY - top - vpY) / zoom,
            };
          }
          const hit = findStageAtPosition(flowPos, stageNodes);
          if (hit !== hoveredStageId) {
            setHoveredStageId(hit);
          }
        }
      }}
      onDragLeave={(e) => {
        if (
          e.relatedTarget instanceof Node &&
          e.currentTarget.contains(e.relatedTarget)
        ) {
          return;
        }
        setHoveredStageId(undefined);
      }}
      onDrop={(e) => {
        if (readOnly || !onDropOp) return;
        setHoveredStageId(undefined);
        const opId = e.dataTransfer.getData(OP_DRAG_MIME);
        if (!opId) return;
        e.preventDefault();
        let flowPos = reactFlow.screenToFlowPosition({
          x: e.clientX,
          y: e.clientY,
        });
        if (!Number.isFinite(flowPos.x) || !Number.isFinite(flowPos.y)) {
          const vp = reactFlow.getViewport?.() ?? { x: 0, y: 0, zoom: 1 };
          const zoom = Number.isFinite(vp.zoom) && vp.zoom > 0 ? vp.zoom : 1;
          const vpX = Number.isFinite(vp.x) ? vp.x : 0;
          const vpY = Number.isFinite(vp.y) ? vp.y : 0;
          const containerRect = e.currentTarget.getBoundingClientRect();
          const clientX = Number.isFinite(e.clientX) ? e.clientX : 0;
          const clientY = Number.isFinite(e.clientY) ? e.clientY : 0;
          const left = Number.isFinite(containerRect?.left) ? containerRect.left : 0;
          const top = Number.isFinite(containerRect?.top) ? containerRect.top : 0;
          flowPos = {
            x: (clientX - left - vpX) / zoom,
            y: (clientY - top - vpY) / zoom,
          };
        }
        const detectedStageId =
          findStageAtPosition(flowPos, stageNodes) ??
          findClosestStage(flowPos, stageNodes, DEFAULT_STAGE_ID);
        onDropOp(opId, flowPos, detectedStageId);
      }}
    >
      {/* Legacy v1 bottom-left workflow title watermark */}
      <div className="BackgroundLabels">
        <div className="Title">{effectiveWorkflow.name}</div>
        {effectiveWorkflow.description && (
          <div className="Description" title={effectiveWorkflow.description}>
            {effectiveWorkflow.description}
          </div>
        )}
      </div>

      <ReactFlow<GraphNode, Edge>
        nodes={rfNodes}
        edges={renderedEdges}
        nodeTypes={NODE_TYPES}
        fitView={true}
        fitViewOptions={{ padding: 0.2, minZoom: 0.125 }}
        minZoom={0.125}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        edgesReconnectable={false}
        elementsSelectable={true}
        deleteKeyCode={null}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnectStart={(_event, params) => {
          didConnectRef.current = false;
          connectingRef.current = params;
        }}
        onConnect={(connection) => {
          didConnectRef.current = true;
          connectingRef.current = null;
          onConnect?.(connection);
        }}
        onConnectEnd={(event) => {
          if (didConnectRef.current || readOnly || !onWireDropOnPane) {
            connectingRef.current = null;
            return;
          }
          const startParams = connectingRef.current;
          connectingRef.current = null;
          if (!startParams?.nodeId || !startParams?.handleId) {
            return;
          }

          const target = event.target as HTMLElement | null;
          const isPane =
            Boolean(
              target?.classList?.contains("react-flow__pane") ||
                target?.closest(".react-flow__pane"),
            ) &&
            !target?.closest(".react-flow__handle") &&
            !target?.closest(".workflow-node");

          if (!isPane) return;

          const clientX =
            "clientX" in event
              ? event.clientX
              : event.touches?.[0]?.clientX ?? 0;
          const clientY =
            "clientY" in event
              ? event.clientY
              : event.touches?.[0]?.clientY ?? 0;

          let flowPos = reactFlow.screenToFlowPosition({
            x: clientX,
            y: clientY,
          });
          if (!Number.isFinite(flowPos.x) || !Number.isFinite(flowPos.y)) {
            const vp = reactFlow.getViewport?.() ?? { x: 0, y: 0, zoom: 1 };
            const zoom = Number.isFinite(vp.zoom) && vp.zoom > 0 ? vp.zoom : 1;
            const vpX = Number.isFinite(vp.x) ? vp.x : 0;
            const vpY = Number.isFinite(vp.y) ? vp.y : 0;
            const containerRect = containerRef.current?.getBoundingClientRect() ?? {
              left: 0,
              top: 0,
            };
            flowPos = {
              x: (clientX - containerRect.left - vpX) / zoom,
              y: (clientY - containerRect.top - vpY) / zoom,
            };
          }

          const stageId =
            findStageAtPosition(flowPos, stageNodes) ??
            findClosestStage(flowPos, stageNodes, DEFAULT_STAGE_ID);

          onWireDropOnPane({
            originNodeId: startParams.nodeId,
            originHandleId: startParams.handleId,
            handleType:
              startParams.handleType === "target" ? "target" : "source",
            screenPos: { x: clientX, y: clientY },
            flowPos,
            stageId,
          });
        }}
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
          onSelectNode?.(undefined);
          onSelectEdge?.(undefined);
          onSelectStage?.(undefined);
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
