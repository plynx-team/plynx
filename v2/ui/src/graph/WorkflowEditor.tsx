import { useCallback, useEffect, useMemo, useState } from "react";
import type { Connection } from "@xyflow/react";
import {
  cancelRun,
  fetchOps,
  fetchRuns,
  fetchRunState,
  fetchWorkflow,
  resumeRun,
  saveWorkflow,
  subscribeRunEvents,
} from "../api/client";
import { applyRunEvent, createInitialRunState } from "../api/reducer";
import type {
  NodePosition,
  NodeSpec,
  OpEntry,
  OutputPortSpec,
  RunState,
  RunSummary,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import {
  ControlButton,
  ControlPanel,
  ControlSeparator,
} from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";
import { LogsPanel } from "../components/LogsPanel";
import { RunInputsForm } from "../components/RunInputsForm";
import {
  formatDuration,
  formatTimestamp,
  runStatusBadgeClasses,
} from "../components/RunList";
import { RunsHistoryPane } from "../components/RunsHistoryPane";
import { ArtifactPreviewDialog } from "../previewers/ArtifactPreviewDialog";
import { useRouter } from "../router/Router";
import { CheckpointCard } from "../stepper/CheckpointCard";
import { StageApprovalCard } from "../stepper/StageApprovalCard";
import { StepperView } from "../stepper/StepperView";
import { GraphView } from "./GraphView";
import {
  computeDagrePositions,
  DEFAULT_STAGE_ID,
  getOrderedStageIds,
} from "./layout";
import {
  addNodeToWorkflow,
  connectEdgeInWorkflow,
  deleteNodeFromWorkflow,
  disconnectEdgeInWorkflow,
  duplicateNodeInWorkflow,
  ensureLayout,
  prepareWorkflowForSave,
} from "./mutations";
import {
  buildOutputPreviewTarget,
  NodeInspector,
  type ArtifactPreviewTarget,
} from "./NodeInspector";
import { OpPalette } from "./OpPalette";
import { computeWorkflowRunDiff } from "./runDiff";
import { validateConnection } from "./validation";

export type EditorViewMode = "graph" | "stepper" | "runs";

const TERMINAL_RUN_STATUSES = new Set(["SUCCESS", "FAILED", "CANCELED"]);

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
  const [viewMode, setViewMode] = useState<EditorViewMode>("graph");
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [layout, setLayout] = useState<WorkflowLayout | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [hasSavedViewport, setHasSavedViewport] = useState<boolean>(false);
  const [fitViewTrigger, setFitViewTrigger] = useState<number>(0);
  const [ops, setOps] = useState<Array<OpEntry>>([]);
  const [workflowRuns, setWorkflowRuns] = useState<Array<RunSummary>>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunState | null>(null);
  const [runsCollapsed, setRunsCollapsed] = useState<boolean>(false);
  const [opsCollapsed, setOpsCollapsed] = useState<boolean>(false);
  const [runActionBusy, setRunActionBusy] = useState<boolean>(false);
  const [showRunModal, setShowRunModal] = useState<boolean>(false);
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
    setSelectedRunId(null);
    setSelectedRun(null);
    setRunsCollapsed(false);
    setOpsCollapsed(false);
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

        if (typeof fetchRuns === "function") {
          fetchRuns()
            .then((list) => {
              if (!active) return;
              const matches = list.runs.filter(
                (r) => r.workflow_path === workflowPath,
              );
              setWorkflowRuns(matches);
            })
            .catch(() => {});
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

  const handleInlineLiteralChange = useCallback(
    (nodeId: string, portName: string, nextVal: unknown) => {
      handleUpdateNodeSpec(nodeId, (prev) => {
        const nextInputs = { ...(prev.inputs ?? {}) };
        if (nextVal === undefined) {
          delete nextInputs[portName];
        } else {
          nextInputs[portName] = nextVal;
        }
        return { ...prev, inputs: nextInputs };
      });
    },
    [handleUpdateNodeSpec],
  );

  const handleSelectRun = useCallback((nextRunId: string | null) => {
    setSelectedRunId(nextRunId);
    setSelectedEdgeId(undefined);
    if (nextRunId !== null) {
      setOpsCollapsed(true);
      setRunsCollapsed(false);
      setViewMode((prev) => (prev === "runs" ? "graph" : prev));
    } else {
      setSelectedRun(null);
      setOpsCollapsed(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedRunId || typeof fetchRunState !== "function") {
      setSelectedRun(null);
      return;
    }

    let active = true;
    let unsubscribe: (() => void) | undefined;
    let resyncPending = false;

    fetchRunState(selectedRunId)
      .then((initial) => {
        if (!active) return;
        setSelectedRun(initial);
        setWorkflowRuns((prev) =>
          prev.map((item) =>
            item.id === initial.id
              ? {
                  ...item,
                  status: initial.status,
                  started_at: initial.started_at,
                  finished_at: initial.finished_at,
                  error: initial.error,
                }
              : item,
          ),
        );

        if (
          !TERMINAL_RUN_STATUSES.has(initial.status) &&
          typeof subscribeRunEvents === "function"
        ) {
          unsubscribe = subscribeRunEvents(
            selectedRunId,
            (event) => {
              if (!active) return;
              setSelectedRun((prev) => {
                const updated = applyRunEvent(
                  prev ?? createInitialRunState(selectedRunId),
                  event,
                );
                return updated;
              });
              if (event.type === "run_status") {
                setWorkflowRuns((prev) =>
                  prev.map((item) =>
                    item.id === selectedRunId
                      ? { ...item, status: event.data.status }
                      : item,
                  ),
                );
              }
            },
            () => {
              if (!active || resyncPending) return;
              resyncPending = true;
              fetchRunState(selectedRunId)
                .then((latest) => {
                  if (!active) return;
                  setSelectedRun(latest);
                  setWorkflowRuns((prev) =>
                    prev.map((item) =>
                      item.id === latest.id
                        ? {
                            ...item,
                            status: latest.status,
                            started_at: latest.started_at,
                            finished_at: latest.finished_at,
                            error: latest.error,
                          }
                        : item,
                    ),
                  );
                  if (TERMINAL_RUN_STATUSES.has(latest.status)) {
                    unsubscribe?.();
                    unsubscribe = undefined;
                  }
                })
                .catch(() => {})
                .finally(() => {
                  resyncPending = false;
                });
            },
          );
        }
      })
      .catch(() => {});

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [selectedRunId]);

  const handlePreviewNodeOutput = useCallback(
    (nodeId: string, output: OutputPortSpec) => {
      if (!selectedRun) return;
      setPreviewTarget(
        buildOutputPreviewTarget(selectedRun.id, nodeId, output),
      );
    },
    [selectedRun],
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

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void handleSave();
        return;
      }

      if (event.key === "Escape" && selectedRunId !== null) {
        event.preventDefault();
        handleSelectRun(null);
        return;
      }

      if (isEditableElement(event.target)) return;
      if (selectedRunId !== null) return;

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
    selectedRunId,
    handleSelectRun,
    handleSave,
    handleDeleteSelected,
    handleDeleteSelectedEdge,
    handleDuplicateSelected,
  ]);

  const isInspectingRun = selectedRunId !== null;
  const activeRunState = isInspectingRun ? selectedRun : null;

  const runDiff = useMemo(
    () =>
      isInspectingRun && selectedRun
        ? computeWorkflowRunDiff(workflow, selectedRun)
        : null,
    [isInspectingRun, selectedRun, workflow],
  );

  const handleCancelActiveRun = useCallback(async () => {
    if (!selectedRunId || typeof cancelRun !== "function") return;
    try {
      setRunActionBusy(true);
      await cancelRun(selectedRunId);
      const updated = await fetchRunState(selectedRunId);
      setSelectedRun(updated);
    } catch {
      // ignore
    } finally {
      setRunActionBusy(false);
    }
  }, [selectedRunId]);

  const handleResumeActiveRun = useCallback(async () => {
    if (!selectedRunId || typeof resumeRun !== "function") return;
    try {
      setRunActionBusy(true);
      await resumeRun(selectedRunId);
      const updated = await fetchRunState(selectedRunId);
      setSelectedRun(updated);
    } catch {
      // ignore
    } finally {
      setRunActionBusy(false);
    }
  }, [selectedRunId]);

  const syntheticRunState = useMemo<RunState>(() => {
    if (activeRunState) return activeRunState;
    const nodes: RunState["nodes"] = {};
    for (const nodeId of Object.keys(workflow?.nodes ?? {})) {
      nodes[nodeId] = {
        node_id: nodeId,
        status: "PENDING",
        cache_hit: false,
        attempt: 0,
      };
    }
    return {
      id: "draft",
      workflow_path: workflowPath,
      workflow_sha256: "",
      status: "RUNNING",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: Date.now() / 1000,
      nodes,
      checkpoints: [],
      stage_gates: {},
    };
  }, [activeRunState, workflow, workflowPath]);

  return (
    <div
      data-testid="workflow-editor"
      className="flex flex-1 min-h-0 flex-col overflow-hidden"
    >
      {/* Top Control Panel Toolbar (Legacy v1 Editor style) */}
      <ControlPanel>
        <div className="control-toggle" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "graph"}
            onClick={() => setViewMode("graph")}
            className={`control-button first ${
              viewMode === "graph" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="grid" size={14} />
            <span className="control-button-text">Graph</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "stepper"}
            onClick={() => setViewMode("stepper")}
            className={`control-button ${
              viewMode === "stepper" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="sliders" size={14} />
            <span className="control-button-text">Stepper</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "runs"}
            onClick={() => setViewMode("runs")}
            className={`control-button last ${
              viewMode === "runs" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="list" size={14} />
            <span className="control-button-text">
              Runs ({workflowRuns.length})
            </span>
          </button>
        </div>

        <ControlSeparator />

        <ControlButton
          icon="save"
          text={saving ? "Saving..." : "Save"}
          data-testid="btn-save-workflow"
          variant={isDirty ? "primary" : "default"}
          disabled={!workflow || saving}
          onClick={() => void handleSave()}
        />

        <ControlButton
          icon="play"
          text="Run Workflow"
          variant="primary"
          onClick={() => setShowRunModal(true)}
        />

        <ControlButton
          icon="layout"
          text="Auto Layout"
          data-testid="btn-auto-layout"
          disabled={!workflow}
          onClick={handleAutoLayout}
        />

        <ControlSeparator />

        <ControlButton
          icon="copy"
          text="Duplicate Node"
          data-testid="btn-duplicate-node"
          disabled={!selectedNodeId}
          onClick={handleDuplicateSelected}
        />

        <ControlButton
          icon="trash-2"
          text="Delete Node"
          data-testid="btn-delete-node"
          variant="danger"
          disabled={!selectedNodeId}
          onClick={handleDeleteSelected}
        />

        {selectedEdgeId && (
          <ControlButton
            icon="scissors"
            text="Disconnect Edge"
            data-testid="btn-delete-edge"
            onClick={handleDeleteSelectedEdge}
          />
        )}

        <div className="ml-auto flex items-center gap-2.5 pr-2 text-xs">
          <span
            className="font-mono truncate max-w-[260px]"
            style={{ color: "var(--text-secondary)" }}
            title={workflowPath}
          >
            {workflow?.name || workflowPath}
          </span>
          {isDirty ? (
            <span
              data-testid="dirty-indicator"
              className="status-badge WAITING"
            >
              Unsaved changes
            </span>
          ) : lastSavedAt ? (
            <span data-testid="save-status" className="status-badge READY">
              Saved
            </span>
          ) : null}
        </div>
      </ControlPanel>

      {error && (
        <div
          role="alert"
          className="px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      )}

      {saveError && (
        <div
          role="alert"
          data-testid="save-error-banner"
          className="flex items-center justify-between gap-3 px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          <div>
            <span className="font-semibold">Save failed: </span>
            <span>{saveError}</span>
          </div>
          <button
            type="button"
            aria-label="Dismiss save error"
            onClick={() => setSaveError(null)}
            className="px-1"
          >
            &times;
          </button>
        </div>
      )}

      {wireError && (
        <div
          role="alert"
          data-testid="wire-error-banner"
          className="flex items-center justify-between gap-3 px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid var(--color-warning)",
            backgroundColor: "rgba(255, 167, 38, 0.15)",
            color: "var(--color-warning)",
          }}
        >
          <div>
            <span className="font-semibold">Connection rejected: </span>
            <span>{wireError}</span>
          </div>
          <button
            type="button"
            aria-label="Dismiss connection error"
            onClick={() => setWireError(null)}
            className="px-1"
          >
            &times;
          </button>
        </div>
      )}

      {loading ? (
        <div
          className="p-10 text-center text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          Loading workflow graph editor...
        </div>
      ) : workflow ? (
        <div className="flex flex-1 min-h-0 flex-row overflow-hidden">
          {/* Left Docked Accordion Column (Fixed 250px: Runs & Mode + Operations) */}
          <div data-testid="left-dock" className="left-dock">
            <RunsHistoryPane
              runs={workflowRuns}
              selectedRunId={selectedRunId}
              onSelectRun={handleSelectRun}
              collapsed={runsCollapsed}
              onToggleCollapse={() => setRunsCollapsed((v) => !v)}
              hasUnsavedChanges={isDirty}
            />
            <OpPalette
              ops={ops}
              stages={stageIds}
              targetStage={targetStage}
              onTargetStageChange={setTargetStage}
              onAddOp={(op) => handleAddOp(op)}
              collapsed={opsCollapsed}
              onToggleCollapse={() => setOpsCollapsed((v) => !v)}
              readOnly={isInspectingRun}
            />
          </div>

          {/* Center Workspace */}
          <div
            data-testid="workspace-center"
            className={`workspace-center flex flex-1 min-w-0 flex-col overflow-hidden relative ${
              isInspectingRun ? "is-inspecting-run" : ""
            }`}
          >
            {/* Run Inspection Mode Top HUD Banner (overlay in Graph view, inline in Stepper/Runs) */}
            {isInspectingRun && (
              <div
                data-testid="run-mode-hud"
                className={`run-mode-hud ${
                  viewMode === "graph" ? "is-graph-overlay" : ""
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 flex-wrap">
                  <span
                    className="inline-flex items-center gap-1.5 font-semibold"
                    style={{ color: "#00d8ff" }}
                  >
                    <FeatherIcon
                      name={
                        selectedRun?.status === "RUNNING"
                          ? "loader"
                          : "eye"
                      }
                      size={13}
                      className={
                        selectedRun?.status === "RUNNING"
                          ? "animate-spin"
                          : ""
                      }
                    />
                    <span>Inspecting Run</span>
                  </span>
                  <span className="font-mono text-xs truncate">
                    #{selectedRunId}
                  </span>
                  {selectedRun && (
                    <span className={runStatusBadgeClasses(selectedRun.status)}>
                      {selectedRun.status}
                    </span>
                  )}
                  <span
                    className="text-[11px]"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Read-only snapshot
                  </span>
                  {runDiff?.hasChanges && (
                    <span
                      data-testid="run-hud-diff-indicator"
                      className="node-diff-badge"
                    >
                      <FeatherIcon name="git-commit" size={10} />
                      <span>Editor modified since this run</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {selectedRun &&
                    (selectedRun.status === "RUNNING" ||
                      selectedRun.status === "WAITING_FOR_USER") && (
                      <ControlButton
                        icon="x"
                        text="Cancel Run"
                        variant="danger"
                        disabled={runActionBusy || selectedRun.cancel_requested}
                        onClick={() => void handleCancelActiveRun()}
                      />
                    )}
                  {selectedRun &&
                    (selectedRun.status === "FAILED" ||
                      selectedRun.status === "CANCELED" ||
                      (selectedRun.status === "WAITING_FOR_USER" &&
                        !selectedRun.owner_pid)) && (
                      <ControlButton
                        icon="rotate-ccw"
                        text="Resume Run"
                        disabled={runActionBusy}
                        onClick={() => void handleResumeActiveRun()}
                      />
                    )}
                  <ControlButton
                    icon="edit-3"
                    text="Return to Editor"
                    data-testid="btn-return-to-editor"
                    variant="primary"
                    onClick={() => handleSelectRun(null)}
                  />
                </div>
              </div>
            )}

            {/* Open Checkpoints & Stage Approvals for the Selected Run */}
            {isInspectingRun && selectedRun && (
              <div
                className={
                  viewMode === "graph"
                    ? "absolute top-11 left-3 right-3 z-20 space-y-2 pointer-events-none empty:hidden max-h-[40vh] overflow-y-auto"
                    : "space-y-2 px-3 pt-2 empty:hidden"
                }
              >
                {Object.values(selectedRun.stage_gates)
                  .filter((g) => g.status === "WAITING")
                  .map((gate) => (
                    <div key={gate.stage_id} className="pointer-events-auto">
                      <StageApprovalCard
                        runId={selectedRun.id}
                        stageId={gate.stage_id}
                        gateState={gate}
                        stageTitle={
                          workflow.stages?.[gate.stage_id]?.title ||
                          gate.stage_id
                        }
                      />
                    </div>
                  ))}
                {selectedRun.checkpoints
                  .filter((cp) => cp.answer === null || cp.answer === undefined)
                  .map((cp) => (
                    <div
                      key={`${cp.node_id}.${cp.checkpoint_id}`}
                      className="pointer-events-auto"
                    >
                      <CheckpointCard
                        runId={selectedRun.id}
                        checkpoint={cp}
                      />
                    </div>
                  ))}
              </div>
            )}

            <div
              className={`flex-1 min-h-0 ${
                viewMode === "graph" ? "overflow-hidden h-full" : "overflow-y-auto"
              }`}
            >
              {viewMode === "graph" ? (
                <GraphView
                  workflow={workflow}
                  layout={layout}
                  runState={activeRunState}
                  runDiff={runDiff}
                  ops={ops}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={handleSelectNode}
                  selectedEdgeId={selectedEdgeId}
                  onSelectEdge={setSelectedEdgeId}
                  readOnly={isInspectingRun}
                  onConnect={handleConnect}
                  onNodeDragStop={handleNodeDragStop}
                  onDropOp={handleDropOp}
                  onViewportChange={handleViewportChange}
                  onLiteralChange={handleInlineLiteralChange}
                  onPreviewOutput={handlePreviewNodeOutput}
                  hasSavedViewport={hasSavedViewport}
                  fitViewTrigger={fitViewTrigger}
                  heightClassName="h-full"
                />
              ) : viewMode === "stepper" ? (
                <StepperView
                  runState={syntheticRunState}
                  workflowDoc={{ workflow, layout }}
                  runDiff={runDiff}
                  selectedNodeId={selectedNodeId}
                  onSelectNode={handleSelectNode}
                />
              ) : (
                <div className="list h-full">
                  <div
                    className="list-header"
                    style={{
                      gridTemplateColumns:
                        "minmax(200px, 1.5fr) 150px 120px 180px 110px",
                    }}
                  >
                    <div className="list-field">Run ID</div>
                    <div className="list-field">Status</div>
                    <div className="list-field">Duration</div>
                    <div className="list-field">Created</div>
                    <div className="list-field">View</div>
                  </div>
                  {workflowRuns.length === 0 ? (
                    <div
                      className="p-8 text-center text-xs"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      No runs recorded for this workflow yet. Click{" "}
                      <strong>Run Workflow</strong> to launch one.
                    </div>
                  ) : (
                    workflowRuns.map((run) => (
                      <div
                        key={run.id}
                        onClick={() => handleSelectRun(run.id)}
                        className={`list-item ${
                          selectedRunId === run.id ? "selected" : ""
                        }`}
                        style={{
                          gridTemplateColumns:
                            "minmax(200px, 1.5fr) 150px 120px 180px 110px",
                        }}
                      >
                        <div
                          className="list-field font-mono text-xs font-semibold"
                          style={{ color: "var(--color-primary)" }}
                        >
                          {run.id}
                        </div>
                        <div className="list-field">
                          <span className={runStatusBadgeClasses(run.status)}>
                            {run.status}
                          </span>
                        </div>
                        <div
                          className="list-field text-xs"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {formatDuration(run.started_at, run.finished_at)}
                        </div>
                        <div
                          className="list-field text-xs"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {formatTimestamp(run.created_at)}
                        </div>
                        <div className="list-field">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/runs/${run.id}`);
                            }}
                            className="control-button !h-6 !min-h-6 !px-2 !text-xs"
                          >
                            <FeatherIcon name="external-link" size={11} />
                            <span>Snapshot</span>
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Bottom Docked Logs Drawer if a node is selected while inspecting a run */}
            {selectedNodeId && activeRunState && (
              <LogsPanel
                runId={activeRunState.id}
                nodeId={selectedNodeId}
                onClose={() => setSelectedNodeId(undefined)}
              />
            )}
          </div>

          {/* Right Docked PropertiesBar */}
          <NodeInspector
            nodeId={selectedNodeId}
            workflow={workflow}
            opsMap={opsMap}
            runState={activeRunState}
            nodeDiff={
              selectedNodeId ? runDiff?.nodes?.[selectedNodeId] : undefined
            }
            readOnly={isInspectingRun}
            onUpdateNodeSpec={handleUpdateNodeSpec}
            onBindReference={handleBindReference}
            onUnbindInput={handleUnbindInput}
            onPreviewArtifact={setPreviewTarget}
          />
        </div>
      ) : null}

      {showRunModal && (
        <RunInputsForm
          workflowPath={workflowPath}
          asModal={true}
          onClose={() => setShowRunModal(false)}
          onRunStarted={(newRunId) => {
            setShowRunModal(false);
            const now = Date.now() / 1000;
            setWorkflowRuns((prev) => [
              {
                id: newRunId,
                workflow_path: workflowPath,
                workflow_sha256: "",
                status: "RUNNING",
                cancel_requested: false,
                pinned: false,
                created_at: now,
                started_at: now,
              },
              ...prev.filter((r) => r.id !== newRunId),
            ]);
            handleSelectRun(newRunId);
            if (typeof fetchRuns === "function") {
              fetchRuns()
                .then((list) => {
                  const matches = list.runs.filter(
                    (r) => r.workflow_path === workflowPath,
                  );
                  if (matches.length > 0) {
                    setWorkflowRuns(matches);
                  }
                })
                .catch(() => {});
            }
          }}
        />
      )}

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
