import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchOps, fetchWorkflow } from "../api/client";
import type {
  NodePosition,
  OpEntry,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import { Link, useRouter } from "../router/Router";
import { GraphView } from "./GraphView";
import { computeDagrePositions, DEFAULT_STAGE_ID, getOrderedStageIds } from "./layout";
import {
  addNodeToWorkflow,
  deleteNodeFromWorkflow,
  duplicateNodeInWorkflow,
  ensureLayout,
} from "./mutations";
import { OpPalette } from "./OpPalette";

function isEditableElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

export function WorkflowEditor({ workflowPath }: { workflowPath: string }) {
  const { navigate } = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [layout, setLayout] = useState<WorkflowLayout | null>(null);
  const [ops, setOps] = useState<Array<OpEntry>>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(
    undefined,
  );
  const [targetStage, setTargetStage] = useState<string>(DEFAULT_STAGE_ID);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const opsMap = useMemo<Record<string, OpEntry>>(() => {
    const map: Record<string, OpEntry> = {};
    for (const op of ops) {
      map[op.id] = op;
    }
    return map;
  }, [ops]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setSelectedNodeId(undefined);

    Promise.all([fetchWorkflow(workflowPath), fetchOps()])
      .then(([doc, opEntries]) => {
        if (!active) return;
        const map: Record<string, OpEntry> = {};
        for (const op of opEntries) {
          map[op.id] = op;
        }
        const initialLayout = ensureLayout(doc.workflow, doc.layout, map);
        const stageIds = getOrderedStageIds(doc.workflow);
        setWorkflow(doc.workflow);
        setLayout(initialLayout);
        setOps(opEntries);
        setTargetStage(stageIds[stageIds.length - 1] ?? DEFAULT_STAGE_ID);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [workflowPath]);

  const stageIds = useMemo(
    () => (workflow ? getOrderedStageIds(workflow) : [DEFAULT_STAGE_ID]),
    [workflow],
  );

  // Sync targetStage when selecting a node
  const handleSelectNode = useCallback(
    (nodeId: string | undefined) => {
      setSelectedNodeId(nodeId);
      if (nodeId && workflow?.nodes?.[nodeId]) {
        setTargetStage(workflow.nodes[nodeId].stage || DEFAULT_STAGE_ID);
      }
    },
    [workflow],
  );

  const handleAddOp = useCallback(
    (op: OpEntry, position?: NodePosition) => {
      if (!workflow) return;
      const result = addNodeToWorkflow(workflow, layout, op, {
        stageId: targetStage,
        position,
        opsMap,
      });
      setWorkflow(result.workflow);
      setLayout(result.layout);
      setSelectedNodeId(result.nodeId);
    },
    [workflow, layout, targetStage, opsMap],
  );

  const handleDropOp = useCallback(
    (opId: string, position: { x: number; y: number }) => {
      const op = opsMap[opId];
      if (!op || !op.valid) return;
      handleAddOp(op, position);
    },
    [opsMap, handleAddOp],
  );

  const handleDuplicateSelected = useCallback(() => {
    if (!workflow || !selectedNodeId) return;
    const result = duplicateNodeInWorkflow(
      workflow,
      layout,
      selectedNodeId,
      opsMap,
    );
    if (!result) return;
    setWorkflow(result.workflow);
    setLayout(result.layout);
    setSelectedNodeId(result.nodeId);
  }, [workflow, layout, selectedNodeId, opsMap]);

  const handleDeleteSelected = useCallback(() => {
    if (!workflow || !selectedNodeId) return;
    const result = deleteNodeFromWorkflow(
      workflow,
      layout,
      selectedNodeId,
      opsMap,
    );
    setWorkflow(result.workflow);
    setLayout(result.layout);
    setSelectedNodeId(undefined);
  }, [workflow, layout, selectedNodeId, opsMap]);

  const handleAutoLayout = useCallback(() => {
    if (!workflow) return;
    const positions = computeDagrePositions(workflow, opsMap);
    setLayout((prev) => ({
      schema: 1,
      nodes: positions,
      viewport: prev?.viewport ?? { x: 0, y: 0, zoom: 1 },
    }));
  }, [workflow, opsMap]);

  const handleNodeDragStop = useCallback(
    (nodeId: string, absX: number, absY: number) => {
      setLayout((prev) => {
        const base = prev ?? {
          schema: 1 as const,
          nodes: {},
          viewport: { x: 0, y: 0, zoom: 1 },
        };
        return {
          ...base,
          nodes: {
            ...base.nodes,
            [nodeId]: { x: absX, y: absY },
          },
        };
      });
    },
    [],
  );

  const handleViewportChange = useCallback(
    (viewport: { x: number; y: number; zoom: number }) => {
      setLayout((prev) => {
        const base = prev ?? {
          schema: 1 as const,
          nodes: {},
          viewport: { x: 0, y: 0, zoom: 1 },
        };
        return {
          ...base,
          viewport,
        };
      });
    },
    [],
  );

  // Keyboard shortcuts: Delete/Backspace to delete selected node, Cmd/Ctrl+D to duplicate
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isEditableElement(event.target)) return;
      if (!selectedNodeId) return;

      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        handleDeleteSelected();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") {
        event.preventDefault();
        handleDuplicateSelected();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedNodeId, handleDeleteSelected, handleDuplicateSelected]);

  const selectedSpec =
    selectedNodeId && workflow?.nodes ? workflow.nodes[selectedNodeId] : undefined;
  const selectedOp = selectedSpec ? opsMap[selectedSpec.op] : undefined;

  return (
    <div data-testid="workflow-editor" className="space-y-4">
      {/* Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/70 px-4 py-3">
        <div className="min-w-0 space-y-0.5">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Link to="/workflows" className="hover:text-slate-200">
              &larr; Workflows
            </Link>
            <span>/</span>
            <span className="truncate font-mono text-slate-300">
              {workflowPath}
            </span>
          </div>
          <h1 className="text-base font-bold text-white">
            {workflow?.name || workflowPath}
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="btn-duplicate-node"
            disabled={!selectedNodeId}
            onClick={handleDuplicateSelected}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Duplicate Node
          </button>
          <button
            type="button"
            data-testid="btn-delete-node"
            disabled={!selectedNodeId}
            onClick={handleDeleteSelected}
            className="rounded-md border border-rose-900 bg-rose-950/60 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-900/60 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Delete Node
          </button>
          <button
            type="button"
            data-testid="btn-auto-layout"
            disabled={!workflow}
            onClick={handleAutoLayout}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-40"
          >
            Auto Layout
          </button>
          <button
            type="button"
            onClick={() => navigate(`/workflows/${workflowPath}`)}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500"
          >
            Run Workflow
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-rose-900 bg-rose-950/60 p-3 text-sm text-rose-300"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
          Loading workflow graph editor...
        </div>
      ) : workflow ? (
        <div className="flex gap-4 h-[calc(100vh-14rem)] min-h-[540px]">
          {/* Left: Operation Palette */}
          <OpPalette
            ops={ops}
            stages={stageIds}
            targetStage={targetStage}
            onTargetStageChange={setTargetStage}
            onAddOp={(op) => handleAddOp(op)}
          />

          {/* Center: Graph Canvas */}
          <div className="flex-1 min-w-0">
            <GraphView
              workflow={workflow}
              layout={layout}
              ops={ops}
              selectedNodeId={selectedNodeId}
              onSelectNode={handleSelectNode}
              readOnly={false}
              onNodeDragStop={handleNodeDragStop}
              onDropOp={handleDropOp}
              onViewportChange={handleViewportChange}
              heightClassName="h-full"
            />
          </div>

          {/* Right: Selected Node Summary (expanded to full inspector in Task 6.11) */}
          <aside
            data-testid="editor-selection-panel"
            className="w-72 shrink-0 rounded-lg border border-slate-800 bg-slate-900/60 p-4 overflow-y-auto"
          >
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300 border-b border-slate-800 pb-2">
              Inspector
            </h2>
            {selectedNodeId && selectedSpec ? (
              <div className="mt-3 space-y-3 text-xs">
                <div>
                  <span className="text-slate-500">Node ID</span>
                  <p className="mt-0.5 font-mono text-white">{selectedNodeId}</p>
                </div>
                <div>
                  <span className="text-slate-500">Title</span>
                  <p className="mt-0.5 text-slate-200">
                    {selectedSpec.title || selectedOp?.title || selectedNodeId}
                  </p>
                </div>
                <div>
                  <span className="text-slate-500">Operation</span>
                  <p className="mt-0.5 font-mono text-slate-300 break-all">
                    {selectedSpec.op}
                  </p>
                </div>
                <div>
                  <span className="text-slate-500">Stage</span>
                  <p className="mt-0.5 font-mono text-slate-300">
                    {selectedSpec.stage || DEFAULT_STAGE_ID}
                  </p>
                </div>
                {selectedOp?.description && (
                  <div>
                    <span className="text-slate-500">Description</span>
                    <p className="mt-0.5 text-slate-400">
                      {selectedOp.description}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-4 text-xs text-slate-500">
                Select a node on the canvas to inspect, duplicate, or delete it.
                Click or drag an operation from the palette to add a node.
              </p>
            )}
          </aside>
        </div>
      ) : null}
    </div>
  );
}
