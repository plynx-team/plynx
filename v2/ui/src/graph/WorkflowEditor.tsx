import { useCallback, useEffect, useMemo, useState } from "react";
import type { Connection } from "@xyflow/react";
import {
  fetchOps,
  fetchRuns,
  fetchRunState,
  fetchWorkflow,
  saveWorkflow,
} from "../api/client";
import type {
  NodePosition,
  NodeSpec,
  OpEntry,
  RunState,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import { ArtifactPreviewDialog } from "../previewers/ArtifactPreviewDialog";
import { Link, useRouter } from "../router/Router";
import { GraphView } from "./GraphView";
import { computeDagrePositions, DEFAULT_STAGE_ID, getOrderedStageIds } from "./layout";
import {
  addNodeToWorkflow,
  connectEdgeInWorkflow,
  deleteNodeFromWorkflow,
  disconnectEdgeInWorkflow,
  duplicateNodeInWorkflow,
  ensureLayout,
  prepareWorkflowForSave,
} from "./mutations";
import { NodeInspector, type ArtifactPreviewTarget } from "./NodeInspector";
import { OpPalette } from "./OpPalette";
import { validateConnection } from "./validation";

function serializeSnapshot(
  workflow: Workflow | null,
  layout: WorkflowLayout | null,
): string {
  return JSON.stringify({ workflow, layout });
}

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
  const [savedSnapshot, setSavedSnapshot] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [hasSavedViewport, setHasSavedViewport] = useState<boolean>(false);
  const [fitViewTrigger, setFitViewTrigger] = useState<number>(0);
  const [ops, setOps] = useState<Array<OpEntry>>([]);
  const [latestRun, setLatestRun] = useState<RunState | null>(null);
  const [previewTarget, setPreviewTarget] =
    useState<ArtifactPreviewTarget | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(
    undefined,
  );
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | undefined>(
    undefined,
  );
  const [wireError, setWireError] = useState<string | null>(null);
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
    setSaveError(null);
    setLastSavedAt(null);
    setSavedSnapshot(null);
    setSelectedNodeId(undefined);
    setSelectedEdgeId(undefined);
    setWireError(null);

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
        setSavedSnapshot(serializeSnapshot(doc.workflow, initialLayout));
        setHasSavedViewport(Boolean(doc.layout?.viewport));
        setOps(opEntries);
        setTargetStage(stageIds[stageIds.length - 1] ?? DEFAULT_STAGE_ID);
        setLoading(false);

        // Best-effort load latest run for this workflow to enable artifact previews
        if (typeof fetchRuns === "function") {
          fetchRuns()
            .then((list) => {
              if (!active) return;
              const match = list.runs.find(
                (r) => r.workflow_path === workflowPath,
              );
              if (match && typeof fetchRunState === "function") {
                return fetchRunState(match.id).then((state) => {
                  if (active) setLatestRun(state);
                });
              }
              return undefined;
            })
            .catch(() => {
              // Non-critical if no run exists yet
            });
        }
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
    setSelectedEdgeId(undefined);
    setWireError(null);
  }, [workflow, layout, selectedNodeId, opsMap]);

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!workflow) return;
      const result = validateConnection(connection, workflow, opsMap);
      if (!result.valid) {
        setWireError(result.reason);
        return;
      }
      setWireError(null);
      setWorkflow((prev) =>
        prev
          ? connectEdgeInWorkflow(
              prev,
              result.sourceNodeId,
              result.sourcePort,
              result.targetNodeId,
              result.targetPort,
            )
          : prev,
      );
    },
    [workflow, opsMap],
  );

  const handleDeleteSelectedEdge = useCallback(() => {
    if (!workflow || !selectedEdgeId) return;
    const arrowIdx = selectedEdgeId.indexOf("->");
    if (arrowIdx === -1) return;
    const targetPart = selectedEdgeId.slice(arrowIdx + 2);
    const dotIdx = targetPart.indexOf(".");
    if (dotIdx === -1) return;
    const targetNodeId = targetPart.slice(0, dotIdx);
    const targetPort = targetPart.slice(dotIdx + 1);
    setWorkflow((prev) =>
      prev ? disconnectEdgeInWorkflow(prev, targetNodeId, targetPort) : prev,
    );
    setSelectedEdgeId(undefined);
    setWireError(null);
  }, [workflow, selectedEdgeId]);

  const handleUpdateNodeSpec = useCallback(
    (nodeId: string, updater: (spec: NodeSpec) => NodeSpec) => {
      setWorkflow((prev) => {
        if (!prev?.nodes?.[nodeId]) return prev;
        return {
          ...prev,
          nodes: {
            ...prev.nodes,
            [nodeId]: updater(prev.nodes[nodeId]),
          },
        };
      });
    },
    [],
  );

  const handleBindReference = useCallback(
    (
      targetNodeId: string,
      targetPort: string,
      sourceNodeId: string,
      sourcePort: string,
    ) => {
      setWireError(null);
      setWorkflow((prev) =>
        prev
          ? connectEdgeInWorkflow(
              prev,
              sourceNodeId,
              sourcePort,
              targetNodeId,
              targetPort,
            )
          : prev,
      );
    },
    [],
  );

  const handleUnbindInput = useCallback(
    (targetNodeId: string, targetPort: string) => {
      setWireError(null);
      setWorkflow((prev) =>
        prev ? disconnectEdgeInWorkflow(prev, targetNodeId, targetPort) : prev,
      );
    },
    [],
  );

  const handleAutoLayout = useCallback(() => {
    if (!workflow) return;
    const positions = computeDagrePositions(workflow, opsMap);
    setLayout((prev) => ({
      schema: 1,
      nodes: positions,
      viewport: prev?.viewport ?? { x: 0, y: 0, zoom: 1 },
    }));
    setFitViewTrigger((c) => c + 1);
  }, [workflow, opsMap]);

  const isDirty = useMemo(() => {
    if (savedSnapshot === null || !workflow) return false;
    return serializeSnapshot(workflow, layout) !== savedSnapshot;
  }, [savedSnapshot, workflow, layout]);

  const handleSave = useCallback(async () => {
    if (!workflow || saving) return;
    const finalLayout = ensureLayout(workflow, layout, opsMap);
    try {
      setSaving(true);
      setSaveError(null);
      const savedDoc = await saveWorkflow(workflowPath, {
        workflow: prepareWorkflowForSave(workflow),
        layout: finalLayout,
      });
      const normalizedLayout = ensureLayout(
        savedDoc.workflow,
        savedDoc.layout ?? finalLayout,
        opsMap,
      );
      setWorkflow(savedDoc.workflow);
      setLayout(normalizedLayout);
      setSavedSnapshot(serializeSnapshot(savedDoc.workflow, normalizedLayout));
      setHasSavedViewport(true);
      setLastSavedAt(Date.now());
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [workflow, layout, opsMap, saving, workflowPath]);

  const handleNodeDragStop = useCallback(
    (nodeId: string, absX: number, absY: number) => {
      setLayout((prev) => {
        const base = prev ?? {
          schema: 1 as const,
          nodes: {},
          viewport: { x: 0, y: 0, zoom: 1 },
        };
        const existing = base.nodes[nodeId];
        if (existing && existing.x === absX && existing.y === absY) {
          return prev;
        }
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

  // Warn before unloading when there are unsaved edits
  useEffect(() => {
    if (!isDirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty]);

  // Keyboard shortcuts: Cmd/Ctrl+S to save, Delete/Backspace to delete selected node or edge, Cmd/Ctrl+D to duplicate
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void handleSave();
        return;
      }

      if (isEditableElement(event.target)) return;

      if (event.key === "Delete" || event.key === "Backspace") {
        if (selectedEdgeId) {
          event.preventDefault();
          handleDeleteSelectedEdge();
          return;
        }
        if (selectedNodeId) {
          event.preventDefault();
          handleDeleteSelected();
          return;
        }
      }
      if (
        selectedNodeId &&
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "d"
      ) {
        event.preventDefault();
        handleDuplicateSelected();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [
    selectedNodeId,
    selectedEdgeId,
    handleSave,
    handleDeleteSelected,
    handleDeleteSelectedEdge,
    handleDuplicateSelected,
  ]);

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
          <div className="flex items-center gap-2.5">
            <h1 className="text-base font-bold text-white">
              {workflow?.name || workflowPath}
            </h1>
            {isDirty ? (
              <span
                data-testid="dirty-indicator"
                className="inline-flex items-center gap-1.5 rounded-full border border-amber-700/80 bg-amber-950/70 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                Unsaved changes
              </span>
            ) : lastSavedAt ? (
              <span
                data-testid="save-status"
                className="inline-flex items-center rounded-full border border-emerald-800/80 bg-emerald-950/60 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300"
              >
                Saved
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="btn-save-workflow"
            disabled={!workflow || saving}
            onClick={() => void handleSave()}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold shadow-sm transition-colors disabled:opacity-40 ${
              isDirty
                ? "bg-amber-600 text-white hover:bg-amber-500"
                : "border border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800"
            }`}
          >
            {saving ? "Saving..." : "Save"}
          </button>
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
          {selectedEdgeId && (
            <button
              type="button"
              data-testid="btn-delete-edge"
              onClick={handleDeleteSelectedEdge}
              className="rounded-md border border-amber-800 bg-amber-950/60 px-3 py-1.5 text-xs font-medium text-amber-300 hover:bg-amber-900/60"
            >
              Disconnect Edge
            </button>
          )}
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

      {saveError && (
        <div
          role="alert"
          data-testid="save-error-banner"
          className="flex items-center justify-between gap-3 rounded-md border border-rose-900 bg-rose-950/70 px-4 py-2.5 text-xs text-rose-200"
        >
          <div>
            <span className="font-semibold text-rose-300">Save failed: </span>
            <span>{saveError}</span>
          </div>
          <button
            type="button"
            aria-label="Dismiss save error"
            onClick={() => setSaveError(null)}
            className="rounded px-1.5 py-0.5 text-rose-400 hover:bg-rose-900/50 hover:text-rose-200"
          >
            &times;
          </button>
        </div>
      )}

      {wireError && (
        <div
          role="alert"
          data-testid="wire-error-banner"
          className="flex items-center justify-between gap-3 rounded-md border border-amber-800 bg-amber-950/70 px-4 py-2.5 text-xs text-amber-200"
        >
          <div>
            <span className="font-semibold text-amber-300">
              Connection rejected:{" "}
            </span>
            <span>{wireError}</span>
          </div>
          <button
            type="button"
            aria-label="Dismiss connection error"
            onClick={() => setWireError(null)}
            className="rounded px-1.5 py-0.5 text-amber-400 hover:bg-amber-900/50 hover:text-amber-200"
          >
            &times;
          </button>
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
              selectedEdgeId={selectedEdgeId}
              onSelectEdge={setSelectedEdgeId}
              readOnly={false}
              onConnect={handleConnect}
              onNodeDragStop={handleNodeDragStop}
              onDropOp={handleDropOp}
              onViewportChange={handleViewportChange}
              hasSavedViewport={hasSavedViewport}
              fitViewTrigger={fitViewTrigger}
              heightClassName="h-full"
            />
          </div>

          {/* Right: Node Inspector */}
          <NodeInspector
            nodeId={selectedNodeId}
            workflow={workflow}
            opsMap={opsMap}
            runState={latestRun}
            readOnly={false}
            onUpdateNodeSpec={handleUpdateNodeSpec}
            onBindReference={handleBindReference}
            onUnbindInput={handleUnbindInput}
            onPreviewArtifact={setPreviewTarget}
          />
        </div>
      ) : null}

      {previewTarget && (
        <ArtifactPreviewDialog
          title={previewTarget.title}
          url={previewTarget.url}
          filename={previewTarget.filename}
          mediaType={previewTarget.mediaType}
          onClose={() => setPreviewTarget(null)}
        />
      )}
    </div>
  );
}
