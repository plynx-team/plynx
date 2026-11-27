import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  BaselineDriftAlert,
  InputPortSpec,
  NodePosition,
  NodeSpec,
  OpEntry,
  OutputPortSpec,
  RunState,
  RunSummary,
  StageValidatorSpec,
  Viewport,
  Workflow,
  WorkflowLayout,
} from "../api/types.gen";
import { ControlButton } from "../components/ControlPanel";
import { FeatherIcon } from "../components/FeatherIcon";
import { RunInspector } from "../components/RunInspector";
import { runStatusBadgeClasses } from "../components/RunList";
import { RunsHistoryPane } from "../components/RunsHistoryPane";
import { useRouter } from "../router/Router";
import { StepperView } from "../stepper/StepperView";
import { GraphView, type WireDropOnPaneEvent } from "./GraphView";
import {
  computeDagrePositions,
  DEFAULT_STAGE_ID,
  getOrderedStageIds,
  resolveNodePorts,
} from "./layout";
import {
  inputHandleId,
  isStageValidatorNodeId,
  outputHandleId,
  parseHandleId,
} from "./types";
import type { QuickConnectDropData } from "./QuickConnectPopover";
import {
  addNodeToWorkflow,
  addStageToWorkflow,
  connectEdgeInWorkflow,
  deleteNodeFromWorkflow,
  deleteStageFromWorkflow,
  disconnectEdgeInWorkflow,
  duplicateNodeInWorkflow,
  ensureLayout,
  prepareWorkflowForSave,
  reorderStagesInWorkflow,
  updateStageInWorkflow,
} from "./mutations";
import {
  createHistory,
  pushHistory,
  redoHistory,
  undoHistory,
  type WorkflowHistory,
} from "./history";
import {
  buildOutputPreviewTarget,
  NodeInspector,
  type ArtifactPreviewTarget,
} from "./NodeInspector";
import { OpPalette } from "./OpPalette";
import type { RunLayoutMode } from "./layout";
import { computeWorkflowRunDiff } from "./runDiff";
import { validateConnection } from "./validation";
import { WorkflowEditorModals } from "./WorkflowEditorModals";
import { WorkflowEditorToolbar } from "./WorkflowEditorToolbar";

export type EditorViewMode = "graph" | "stepper";

const TERMINAL_RUN_STATUSES = new Set(["SUCCESS", "FAILED", "CANCELED"]);

function serializeSnapshot(
  workflow: Workflow | null,
  layout: WorkflowLayout | null,
): string {
  const nodes = layout?.nodes ?? {};
  return JSON.stringify({ workflow, nodes });
}

function readLocalViewport(workflowPath: string): Viewport | null {
  try {
    const raw = window.localStorage.getItem(`plynx:viewport:${workflowPath}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Viewport>;
    if (
      typeof parsed.x === "number" &&
      typeof parsed.y === "number" &&
      typeof parsed.zoom === "number"
    ) {
      return { x: parsed.x, y: parsed.y, zoom: parsed.zoom };
    }
  } catch {
    // Ignore storage access errors
  }
  return null;
}

function writeLocalViewport(workflowPath: string, viewport: Viewport): void {
  try {
    window.localStorage.setItem(
      `plynx:viewport:${workflowPath}`,
      JSON.stringify(viewport),
    );
  } catch {
    // Ignore storage access errors
  }
}

function isEditableElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

export function WorkflowEditor({ workflowPath }: { workflowPath: string }) {
  const { navigate, queryParams } = useRouter();
  const getInitialViewMode = (): EditorViewMode => {
    const v = queryParams?.view;
    if (v === "graph" || v === "stepper") {
      return v;
    }
    return "graph";
  };
  const [viewMode, setViewMode] = useState<EditorViewMode>(getInitialViewMode);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [layout, setLayout] = useState<WorkflowLayout | null>(null);
  const [history, setHistory] = useState<WorkflowHistory | null>(null);
  const historyRef = useRef<WorkflowHistory | null>(null);
  const lastTextEditTimeRef = useRef<number>(0);
  const workflowRef = useRef<Workflow | null>(null);
  const layoutRef = useRef<WorkflowLayout | null>(null);

  useEffect(() => {
    historyRef.current = history;
  }, [history]);

  useEffect(() => {
    workflowRef.current = workflow;
  }, [workflow]);

  useEffect(() => {
    layoutRef.current = layout;
  }, [layout]);
  const [savedSnapshot, setSavedSnapshot] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [hasSavedViewport, setHasSavedViewport] = useState<boolean>(false);
  const [fitViewTrigger, setFitViewTrigger] = useState<number>(0);
  const [ops, setOps] = useState<Array<OpEntry>>([]);
  const [workflowRuns, setWorkflowRuns] = useState<Array<RunSummary>>([]);
  const [driftAlerts, setDriftAlerts] = useState<Array<BaselineDriftAlert>>([]);
  const [runsNextCursor, setRunsNextCursor] = useState<string | null>(null);
  const [runsLoadingMore, setRunsLoadingMore] = useState<boolean>(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    () => queryParams?.run_id || null,
  );
  const [runSubSeq, setRunSubSeq] = useState<number>(0);
  const isInspectingRun = selectedRunId !== null;
  const [selectedRun, setSelectedRun] = useState<RunState | null>(null);
  const [runLayoutMode, setRunLayoutMode] = useState<RunLayoutMode>("relayout");
  const [runsCollapsed, setRunsCollapsed] = useState<boolean>(false);
  const [opsCollapsed, setOpsCollapsed] = useState<boolean>(false);
  const [runActionBusy, setRunActionBusy] = useState<boolean>(false);
  const [showRunModal, setShowRunModal] = useState<boolean>(false);
  const [showUnsavedRunConfirm, setShowUnsavedRunConfirm] = useState<boolean>(false);
  const [runWithoutSaving, setRunWithoutSaving] = useState<boolean>(false);
  const [previewTarget, setPreviewTarget] =
    useState<ArtifactPreviewTarget | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(
    undefined,
  );
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | undefined>(
    undefined,
  );
  const [selectedStageId, setSelectedStageId] = useState<string | undefined>(
    undefined,
  );
  const [stageToDelete, setStageToDelete] = useState<string | null>(null);
  const [deleteStageChoice, setDeleteStageChoice] = useState<
    "reassign" | "delete"
  >("reassign");
  const [showAddStageModal, setShowAddStageModal] = useState<boolean>(false);
  const [newStageModalTitle, setNewStageModalTitle] = useState<string>("");
  const [newStageModalRequireApproval, setNewStageModalRequireApproval] =
    useState<boolean>(false);
  const [wireError, setWireError] = useState<string | null>(null);
  const [quickConnectData, setQuickConnectData] =
    useState<QuickConnectDropData | null>(null);
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

  const queryRunIdRef = useRef<string | null>(queryParams?.run_id || null);
  useEffect(() => {
    queryRunIdRef.current = queryParams?.run_id || null;
  }, [queryParams?.run_id]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setSaveError(null);
    setLastSavedAt(null);
    setSavedSnapshot(null);
    setSelectedNodeId(undefined);
    setSelectedEdgeId(undefined);
    setSelectedStageId(undefined);
    setStageToDelete(null);
    const initialRunId = queryRunIdRef.current;
    setSelectedRunId(initialRunId);
    setSelectedRun(null);
    setDriftAlerts([]);
    setRunsCollapsed(false);
    setOpsCollapsed(Boolean(initialRunId));
    setWireError(null);

    Promise.all([fetchWorkflow(workflowPath), fetchOps()])
      .then(([doc, opEntries]) => {
        if (!active) return;
        const map: Record<string, OpEntry> = {};
        for (const op of opEntries) {
          map[op.id] = op;
        }
        const localViewport = readLocalViewport(workflowPath);
        const initialLayout = ensureLayout(
          doc.workflow,
          localViewport
            ? {
                schema: 1,
                nodes: doc.layout?.nodes ?? {},
                viewport: localViewport,
              }
            : doc.layout,
          map,
        );
        const stageIds = getOrderedStageIds(doc.workflow);
        const initialHistory = createHistory({
          workflow: doc.workflow,
          layout: initialLayout,
        });
        workflowRef.current = doc.workflow;
        layoutRef.current = initialLayout;
        historyRef.current = initialHistory;
        setWorkflow(doc.workflow);
        setLayout(initialLayout);
        setHistory(initialHistory);
        setSavedSnapshot(serializeSnapshot(doc.workflow, initialLayout));
        setHasSavedViewport(Boolean(localViewport ?? doc.layout?.viewport));
        setOps(opEntries);
        setTargetStage(stageIds[stageIds.length - 1] ?? DEFAULT_STAGE_ID);
        setLoading(false);

        if (typeof fetchRuns === "function") {
          fetchRuns({ workflowPath, limit: 50 })
            .then((list) => {
              if (!active) return;
              const matches = list.runs.filter(
                (r) => r.workflow_path === workflowPath,
              );
              setWorkflowRuns(matches);
              setDriftAlerts(
                (list.drift_alerts ?? []).filter(
                  (a) => a.workflow_path === workflowPath,
                ),
              );
              setRunsNextCursor(list.next_cursor ?? null);
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
      if (nodeId) {
        setSelectedStageId(undefined);
      }
      if (nodeId && workflow?.nodes?.[nodeId]) {
        setTargetStage(workflow.nodes[nodeId].stage || DEFAULT_STAGE_ID);
      }
    },
    [workflow],
  );

  const handleSelectStage = useCallback((stageId: string | undefined) => {
    setSelectedStageId(stageId);
    if (stageId) {
      setSelectedNodeId(undefined);
      setSelectedEdgeId(undefined);
      setTargetStage(stageId);
    }
  }, []);

  const commitStateChange = useCallback(
    (
      nextWorkflowOrUpdater: Workflow | ((prev: Workflow) => Workflow),
      nextLayoutOrUpdater?:
        | WorkflowLayout
        | ((prev: WorkflowLayout) => WorkflowLayout)
        | null,
      options?: { coalesce?: boolean },
    ) => {
      const currentWf = workflowRef.current;
      if (!currentWf) return;

      const finalWf =
        typeof nextWorkflowOrUpdater === "function"
          ? nextWorkflowOrUpdater(currentWf)
          : nextWorkflowOrUpdater;

      const currentLayout = layoutRef.current ?? {
        schema: 1 as const,
        nodes: {},
        viewport: { x: 0, y: 0, zoom: 1 },
      };

      const finalLayout = nextLayoutOrUpdater
        ? typeof nextLayoutOrUpdater === "function"
          ? nextLayoutOrUpdater(currentLayout)
          : nextLayoutOrUpdater
        : currentLayout;

      workflowRef.current = finalWf;
      layoutRef.current = finalLayout;
      setWorkflow(finalWf);
      if (nextLayoutOrUpdater) {
        setLayout(finalLayout);
      }

      setHistory((curr) => {
        if (!curr) {
          return createHistory({ workflow: finalWf, layout: finalLayout });
        }
        const updated = pushHistory(
          curr,
          { workflow: finalWf, layout: finalLayout },
          {
            coalesce: options?.coalesce,
            lastActionTime: lastTextEditTimeRef.current,
          },
        );
        if (options?.coalesce) {
          lastTextEditTimeRef.current = Date.now();
        } else {
          lastTextEditTimeRef.current = 0;
        }
        historyRef.current = updated;
        return updated;
      });
    },
    [],
  );

  const canUndo = Boolean(history && history.past.length > 0 && !isInspectingRun);
  const canRedo = Boolean(history && history.future.length > 0 && !isInspectingRun);

  const handleUndo = useCallback(() => {
    if (isInspectingRun) return;
    const curr = historyRef.current;
    if (!curr) return;
    const res = undoHistory(curr);
    if (!res) return;
    historyRef.current = res.history;
    workflowRef.current = res.restored.workflow;
    layoutRef.current = res.restored.layout;
    setHistory(res.history);
    setWorkflow(res.restored.workflow);
    setLayout((prevLayout) => ({
      ...res.restored.layout,
      viewport: prevLayout?.viewport ?? res.restored.layout.viewport,
    }));
    setSelectedNodeId((prev) =>
      prev && res.restored.workflow.nodes?.[prev] ? prev : undefined,
    );
    setSelectedStageId((prev) =>
      prev && res.restored.workflow.stages?.[prev] ? prev : undefined,
    );
    setSelectedEdgeId(undefined);
  }, [isInspectingRun]);

  const handleRedo = useCallback(() => {
    if (isInspectingRun) return;
    const curr = historyRef.current;
    if (!curr) return;
    const res = redoHistory(curr);
    if (!res) return;
    historyRef.current = res.history;
    workflowRef.current = res.restored.workflow;
    layoutRef.current = res.restored.layout;
    setHistory(res.history);
    setWorkflow(res.restored.workflow);
    setLayout((prevLayout) => ({
      ...res.restored.layout,
      viewport: prevLayout?.viewport ?? res.restored.layout.viewport,
    }));
    setSelectedNodeId((prev) =>
      prev && res.restored.workflow.nodes?.[prev] ? prev : undefined,
    );
    setSelectedStageId((prev) =>
      prev && res.restored.workflow.stages?.[prev] ? prev : undefined,
    );
    setSelectedEdgeId(undefined);
  }, [isInspectingRun]);

  const handleAddStage = useCallback(
    (
      rawStageId: string,
      title?: string,
      options?: { requireApproval?: boolean },
    ) => {
      if (!workflow) return;
      const res = addStageToWorkflow(workflow, rawStageId, title, options);
      commitStateChange(res.workflow);
      setSelectedStageId(res.stageId);
      setSelectedNodeId(undefined);
      setSelectedEdgeId(undefined);
      setTargetStage(res.stageId);
    },
    [workflow, commitStateChange],
  );

  const handleUpdateStage = useCallback(
    (
      stageId: string,
      updates: {
        title?: string;
        require_approval?: boolean;
        validator?: StageValidatorSpec | null;
      },
    ) => {
      if (!workflow) return;
      const nextWf = updateStageInWorkflow(workflow, stageId, updates);
      commitStateChange(nextWf, undefined, { coalesce: true });
    },
    [workflow, commitStateChange],
  );

  const handleDeleteStageRequest = useCallback(
    (stageId: string) => {
      if (!workflow || isInspectingRun) return;
      const memberNodeIds = Object.keys(workflow.nodes ?? {}).filter(
        (nid) => (workflow.nodes?.[nid]?.stage || DEFAULT_STAGE_ID) === stageId,
      );
      if (memberNodeIds.length === 0) {
        const res = deleteStageFromWorkflow(workflow, layout, stageId, {
          opsMap,
        });
        commitStateChange(res.workflow, res.layout);
        if (selectedStageId === stageId) {
          setSelectedStageId(undefined);
        }
        if (targetStage === stageId) {
          const remaining = getOrderedStageIds(res.workflow);
          setTargetStage(remaining[remaining.length - 1] ?? DEFAULT_STAGE_ID);
        }
      } else {
        setStageToDelete(stageId);
        setDeleteStageChoice("reassign");
      }
    },
    [isInspectingRun, workflow, layout, opsMap, selectedStageId, targetStage, commitStateChange],
  );

  const handleConfirmDeleteStage = useCallback(() => {
    if (!workflow || !stageToDelete) return;
    const remainingStages = getOrderedStageIds(workflow).filter(
      (sid) => sid !== stageToDelete,
    );
    if (remainingStages.length === 0) {
      setStageToDelete(null);
      return;
    }
    const reassignToStageId = remainingStages[0];
    const res = deleteStageFromWorkflow(workflow, layout, stageToDelete, {
      deleteNodes: deleteStageChoice === "delete",
      reassignToStageId,
      opsMap,
    });
    commitStateChange(res.workflow, res.layout);
    if (selectedStageId === stageToDelete) {
      setSelectedStageId(undefined);
    }
    if (targetStage === stageToDelete) {
      const remaining = getOrderedStageIds(res.workflow);
      setTargetStage(remaining[remaining.length - 1] ?? DEFAULT_STAGE_ID);
    }
    setStageToDelete(null);
  }, [
    workflow,
    layout,
    stageToDelete,
    deleteStageChoice,
    opsMap,
    selectedStageId,
    targetStage,
    commitStateChange,
  ]);

  const handleReorderStages = useCallback(
    (newOrder: string[]) => {
      if (!workflow) return { success: false, reason: "No workflow loaded" };
      const res = reorderStagesInWorkflow(workflow, newOrder);
      if (res.success) {
        commitStateChange(res.workflow);
        return { success: true };
      }
      return { success: false, reason: res.reason };
    },
    [workflow, commitStateChange],
  );

  const handleAddOp = useCallback(
    (op: OpEntry, position?: NodePosition, stageId?: string) => {
      const currentWf = workflowRef.current;
      const currentLayout = layoutRef.current;
      if (!currentWf) return;
      const effectiveStage = stageId || selectedStageId || targetStage;
      const result = addNodeToWorkflow(currentWf, currentLayout, op, {
        stageId: effectiveStage,
        position,
        opsMap,
      });
      commitStateChange(result.workflow, result.layout);
      setSelectedNodeId(result.nodeId);
    },
    [selectedStageId, targetStage, opsMap, commitStateChange],
  );

  const handleDropOp = useCallback(
    (opId: string, position: { x: number; y: number }, stageId?: string) => {
      const op = opsMap[opId];
      if (!op || !op.valid) return;
      handleAddOp(op, position, stageId);
    },
    [opsMap, handleAddOp],
  );

  const handleDuplicateSelected = useCallback(() => {
    if (isInspectingRun) return;
    const currentWf = workflowRef.current;
    const currentLayout = layoutRef.current;
    if (!currentWf || !selectedNodeId) return;
    const result = duplicateNodeInWorkflow(
      currentWf,
      currentLayout,
      selectedNodeId,
      opsMap,
    );
    if (!result) return;
    commitStateChange(result.workflow, result.layout);
    setSelectedNodeId(result.nodeId);
  }, [isInspectingRun, selectedNodeId, opsMap, commitStateChange]);

  const handleDeleteSelected = useCallback(() => {
    if (isInspectingRun) return;
    const currentWf = workflowRef.current;
    const currentLayout = layoutRef.current;
    if (!currentWf || !selectedNodeId) return;
    const result = deleteNodeFromWorkflow(
      currentWf,
      currentLayout,
      selectedNodeId,
      opsMap,
    );
    commitStateChange(result.workflow, result.layout);
    setSelectedNodeId(undefined);
    setSelectedEdgeId(undefined);
    setWireError(null);
  }, [isInspectingRun, selectedNodeId, opsMap, commitStateChange]);

  const handleConnect = useCallback(
    (connection: Connection) => {
      const currentWf = workflowRef.current;
      if (!currentWf) return;
      const result = validateConnection(connection, currentWf, opsMap);
      if (!result.valid) {
        setWireError(result.reason);
        return;
      }
      setWireError(null);
      const nextWf = connectEdgeInWorkflow(
        currentWf,
        result.sourceNodeId,
        result.sourcePort,
        result.targetNodeId,
        result.targetPort,
      );
      commitStateChange(nextWf);
    },
    [opsMap, commitStateChange],
  );

  const handleWireDropOnPane = useCallback(
    (event: WireDropOnPaneEvent) => {
      if (isInspectingRun) return;
      const currentWf = workflowRef.current;
      if (!currentWf) return;
      const originNode = currentWf.nodes?.[event.originNodeId];
      if (!originNode) return;
      const opEntry = opsMap[originNode.op];
      const ports = resolveNodePorts(
        event.originNodeId,
        originNode,
        currentWf,
        opEntry,
      );
      const parsed = parseHandleId(event.originHandleId);
      const portName = parsed?.name ?? event.originHandleId;

      let originPort: InputPortSpec | OutputPortSpec | undefined;
      if (event.handleType === "source") {
        originPort = ports.outputs.find((p) => p.name === portName);
      } else {
        originPort = ports.inputs.find((p) => p.name === portName);
      }
      if (!originPort) {
        originPort = { name: portName, type: "str" };
      }

      setQuickConnectData({
        originNodeId: event.originNodeId,
        originNodeTitle: originNode.title || originNode.op,
        originPortName: portName,
        handleType: event.handleType,
        originPort,
        screenPos: event.screenPos,
        flowPos: event.flowPos,
        stageId: event.stageId,
      });
    },
    [isInspectingRun, opsMap],
  );

  const handleQuickConnectSelect = useCallback(
    (opId: string, portName: string) => {
      const data = quickConnectData;
      setQuickConnectData(null);
      if (!data) return;

      const currentWf = workflowRef.current;
      const currentLayout = layoutRef.current;
      if (!currentWf) return;

      const op = opsMap[opId];
      if (!op || !op.valid) return;

      // Stage order preservation: inter-stage edges must only go forward
      let effectiveStage = data.stageId;
      const originNodeSpec = currentWf.nodes?.[data.originNodeId];
      if (originNodeSpec) {
        const originStage = originNodeSpec.stage || DEFAULT_STAGE_ID;
        const orderedStages = getOrderedStageIds(currentWf);
        const stageIdx = (sid: string) => orderedStages.indexOf(sid);
        if (data.handleType === "source") {
          // origin -> new: new node stage must be >= origin stage
          if (stageIdx(effectiveStage) < stageIdx(originStage)) {
            effectiveStage = originStage;
          }
        } else {
          // new -> origin: new node stage must be <= origin stage
          if (stageIdx(effectiveStage) > stageIdx(originStage)) {
            effectiveStage = originStage;
          }
        }
      }

      // Add node
      const added = addNodeToWorkflow(currentWf, currentLayout, op, {
        stageId: effectiveStage,
        position: data.flowPos,
        opsMap,
      });

      // Validate connection before committing
      const proposedConnection: Connection =
        data.handleType === "source"
          ? {
              source: data.originNodeId,
              sourceHandle: outputHandleId(data.originPortName),
              target: added.nodeId,
              targetHandle: inputHandleId(portName),
            }
          : {
              source: added.nodeId,
              sourceHandle: outputHandleId(portName),
              target: data.originNodeId,
              targetHandle: inputHandleId(data.originPortName),
            };
      const validation = validateConnection(
        proposedConnection,
        added.workflow,
        opsMap,
      );
      if (!validation.valid) {
        setWireError(validation.reason);
        return;
      }
      setWireError(null);

      // Connect edge
      const nextWf = connectEdgeInWorkflow(
        added.workflow,
        validation.sourceNodeId,
        validation.sourcePort,
        validation.targetNodeId,
        validation.targetPort,
      );

      commitStateChange(nextWf, added.layout);
      setSelectedNodeId(added.nodeId);
    },
    [quickConnectData, opsMap, commitStateChange],
  );

  const handleDeleteSelectedEdge = useCallback(() => {
    if (isInspectingRun) return;
    const currentWf = workflowRef.current;
    if (!currentWf || !selectedEdgeId) return;
    const arrowIdx = selectedEdgeId.indexOf("->");
    if (arrowIdx === -1) return;
    const targetPart = selectedEdgeId.slice(arrowIdx + 2);
    const dotIdx = targetPart.indexOf(".");
    if (dotIdx === -1) return;
    const targetNodeId = targetPart.slice(0, dotIdx);
    const targetPort = targetPart.slice(dotIdx + 1);
    const nextWf = disconnectEdgeInWorkflow(
      currentWf,
      targetNodeId,
      targetPort,
    );
    commitStateChange(nextWf);
    setSelectedEdgeId(undefined);
    setWireError(null);
  }, [isInspectingRun, selectedEdgeId, commitStateChange]);

  const handleUpdateNodeSpec = useCallback(
    (
      nodeId: string,
      updater: (spec: NodeSpec) => NodeSpec,
      options?: { coalesce?: boolean },
    ) => {
      const currentWf = workflowRef.current;
      if (!currentWf?.nodes?.[nodeId]) return;
      const nextWf: Workflow = {
        ...currentWf,
        nodes: {
          ...currentWf.nodes,
          [nodeId]: updater(currentWf.nodes[nodeId]),
        },
      };
      commitStateChange(nextWf, undefined, {
        coalesce: options?.coalesce ?? true,
      });
    },
    [commitStateChange],
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

  const syncUrlParams = useCallback(
    (newView: EditorViewMode, newRunId: string | null) => {
      const params = new URLSearchParams();
      if (newView === "stepper") {
        params.set("view", newView);
      } else if (newView === "graph" && (newRunId || queryParams?.view === "graph")) {
        params.set("view", "graph");
      }
      if (newRunId) {
        params.set("run_id", newRunId);
      }
      const qs = params.toString();
      const nextUrl = `/editor/${workflowPath}${qs ? `?${qs}` : ""}`;
      navigate(nextUrl, { replace: true });
    },
    [workflowPath, queryParams?.view, navigate],
  );

  const handleToggleViewMode = useCallback(
    (mode: EditorViewMode) => {
      setViewMode(mode);
      syncUrlParams(mode, selectedRunId);
    },
    [selectedRunId, syncUrlParams],
  );

  const handleSelectRun = useCallback(
    (nextRunId: string | null) => {
      setSelectedRunId(nextRunId);
      setSelectedEdgeId(undefined);
      setSelectedStageId(undefined);
      if (nextRunId !== null) {
        setOpsCollapsed(true);
        setRunsCollapsed(false);
      } else {
        setSelectedRun(null);
        setOpsCollapsed(false);
      }
      syncUrlParams(viewMode, nextRunId);
    },
    [viewMode, syncUrlParams],
  );

  const handleLoadMoreRuns = useCallback(async () => {
    if (!runsNextCursor || runsLoadingMore || typeof fetchRuns !== "function") {
      return;
    }
    try {
      setRunsLoadingMore(true);
      const list = await fetchRuns({
        workflowPath,
        limit: 50,
        cursor: runsNextCursor,
      });
      setWorkflowRuns((prev) => {
        const seen = new Set(prev.map((r) => r.id));
        const nextItems = list.runs.filter(
          (r) => r.workflow_path === workflowPath && !seen.has(r.id),
        );
        return [...prev, ...nextItems];
      });
      setRunsNextCursor(list.next_cursor ?? null);
    } catch {
      // ignore
    } finally {
      setRunsLoadingMore(false);
    }
  }, [runsNextCursor, runsLoadingMore, workflowPath]);

  useEffect(() => {
    const v = queryParams?.view;
    if (v === "graph" || v === "stepper") {
      setViewMode(v);
    } else if (!v) {
      setViewMode("graph");
    }

    const targetRunId = queryParams?.run_id || null;
    setSelectedRunId((prev) => {
      if (prev !== targetRunId) {
        if (targetRunId !== null) {
          setOpsCollapsed(true);
        } else {
          setSelectedRun(null);
          setOpsCollapsed(false);
        }
        return targetRunId;
      }
      return prev;
    });
  }, [queryParams?.view, queryParams?.run_id]);

  useEffect(() => {
    if (!selectedRunId || typeof fetchRunState !== "function") {
      setSelectedRun(null);
      return;
    }

    let active = true;
    let unsubscribe: (() => void) | undefined;
    let resyncPending = false;

    const triggerResync = () => {
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
    };

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
              let shouldResyncSnapshot = false;
              setSelectedRun((prev) => {
                if (
                  event.type === "node_status" &&
                  !isStageValidatorNodeId(event.data.node_id) &&
                  prev?.workflow_snapshot?.nodes &&
                  !(event.data.node_id in prev.workflow_snapshot.nodes)
                ) {
                  shouldResyncSnapshot = true;
                }
                if (event.type === "checkpoint_resolved") {
                  shouldResyncSnapshot = true;
                }
                const updated = applyRunEvent(
                  prev ?? createInitialRunState(selectedRunId),
                  event,
                );
                return updated;
              });
              if (shouldResyncSnapshot) {
                triggerResync();
              }
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
            triggerResync,
          );
        }
      })
      .catch(() => {});

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [selectedRunId, runSubSeq]);

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
      const currentWf = workflowRef.current;
      if (!currentWf) return;
      setWireError(null);
      const nextWf = connectEdgeInWorkflow(
        currentWf,
        sourceNodeId,
        sourcePort,
        targetNodeId,
        targetPort,
      );
      commitStateChange(nextWf);
    },
    [commitStateChange],
  );

  const handleUnbindInput = useCallback(
    (targetNodeId: string, targetPort: string) => {
      const currentWf = workflowRef.current;
      if (!currentWf) return;
      setWireError(null);
      const nextWf = disconnectEdgeInWorkflow(
        currentWf,
        targetNodeId,
        targetPort,
      );
      commitStateChange(nextWf);
    },
    [commitStateChange],
  );

  const measuredDimsRef = useRef<
    Record<string, { width: number; height: number }>
  >({});

  const handleAutoLayout = useCallback(() => {
    if (isInspectingRun) return;
    const currentWf = workflowRef.current;
    if (!currentWf) return;
    const positions = computeDagrePositions(
      currentWf,
      opsMap,
      measuredDimsRef.current,
    );
    const nextLayout: WorkflowLayout = {
      schema: 1,
      nodes: positions,
      viewport: layoutRef.current?.viewport ?? { x: 0, y: 0, zoom: 1 },
    };
    commitStateChange(currentWf, nextLayout);
    setFitViewTrigger((c) => c + 1);
  }, [isInspectingRun, opsMap, commitStateChange]);

  const isDirty = useMemo(() => {
    if (savedSnapshot === null || !workflow) return false;
    return serializeSnapshot(workflow, layout) !== savedSnapshot;
  }, [savedSnapshot, workflow, layout]);

  const handleSave = useCallback(async (): Promise<boolean> => {
    const currentWf = workflowRef.current;
    if (!currentWf || saving) return false;
    const currentLayout = layoutRef.current;
    const finalLayout = ensureLayout(currentWf, currentLayout, opsMap);
    try {
      setSaving(true);
      setSaveError(null);
      const savedDoc = await saveWorkflow(workflowPath, {
        workflow: prepareWorkflowForSave(currentWf),
        layout: {
          schema: 1,
          nodes: finalLayout.nodes,
        },
      });
      const normalizedLayout = ensureLayout(
        savedDoc.workflow,
        savedDoc.layout ?? finalLayout,
        opsMap,
      );
      workflowRef.current = savedDoc.workflow;
      layoutRef.current = normalizedLayout;
      setWorkflow(savedDoc.workflow);
      setLayout(normalizedLayout);
      setSavedSnapshot(serializeSnapshot(savedDoc.workflow, normalizedLayout));
      setHasSavedViewport(true);
      setLastSavedAt(Date.now());
      return true;
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : String(err));
      return false;
    } finally {
      setSaving(false);
    }
  }, [opsMap, saving, workflowPath]);

  const handleNodeDragStop = useCallback(
    (nodeId: string, absX: number, absY: number) => {
      const currentLayout = layoutRef.current ?? {
        schema: 1 as const,
        nodes: {},
        viewport: { x: 0, y: 0, zoom: 1 },
      };
      const existing = currentLayout.nodes[nodeId];
      if (existing && existing.x === absX && existing.y === absY) {
        return;
      }
      const nextLayout: WorkflowLayout = {
        ...currentLayout,
        nodes: {
          ...currentLayout.nodes,
          [nodeId]: { x: absX, y: absY },
        },
      };
      if (workflowRef.current) {
        commitStateChange(workflowRef.current, nextLayout);
      }
    },
    [commitStateChange],
  );

  const handleStageDragStop = useCallback(
    (stageId: string, dx: number, dy: number) => {
      const wf = workflowRef.current;
      if (!wf || (dx === 0 && dy === 0)) return;
      const memberNodeIds = Object.keys(wf.nodes ?? {}).filter(
        (nid) => (wf.nodes?.[nid]?.stage || DEFAULT_STAGE_ID) === stageId,
      );
      if (memberNodeIds.length === 0) return;

      const base = ensureLayout(wf, layoutRef.current, opsMap);
      const nextNodes = { ...base.nodes };
      for (const nid of memberNodeIds) {
        const currentPos = nextNodes[nid] ?? { x: 0, y: 0 };
        nextNodes[nid] = {
          x: Math.round(currentPos.x + dx),
          y: Math.round(currentPos.y + dy),
        };
      }
      const nextLayout: WorkflowLayout = {
        ...base,
        nodes: nextNodes,
      };
      commitStateChange(wf, nextLayout);
    },
    [opsMap, commitStateChange],
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

      if (isEditableElement(event.target)) return;

      const isModalOpen = Boolean(
        showRunModal ||
          showUnsavedRunConfirm ||
          previewTarget ||
          stageToDelete ||
          showAddStageModal ||
          (typeof document !== "undefined" && document.querySelector('[role="dialog"]')),
      );
      if (isModalOpen) return;

      if (event.key === "Escape" && selectedRunId !== null) {
        event.preventDefault();
        handleSelectRun(null);
        return;
      }

      if (selectedRunId !== null) return;

      // Undo: Cmd+Z (Mac) or Ctrl+Z (Win/Linux) without Shift
      if (
        (event.metaKey || event.ctrlKey) &&
        !event.shiftKey &&
        event.key.toLowerCase() === "z"
      ) {
        event.preventDefault();
        handleUndo();
        return;
      }

      // Redo: Cmd+Shift+Z, Ctrl+Shift+Z, Cmd+Y, or Ctrl+Y
      if (
        ((event.metaKey || event.ctrlKey) &&
          event.shiftKey &&
          event.key.toLowerCase() === "z") ||
        ((event.metaKey || event.ctrlKey) &&
          !event.shiftKey &&
          event.key.toLowerCase() === "y")
      ) {
        event.preventDefault();
        handleRedo();
        return;
      }

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
        if (selectedStageId && stageIds.length > 1) {
          event.preventDefault();
          handleDeleteStageRequest(selectedStageId);
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
    selectedStageId,
    stageIds,
    selectedRunId,
    showRunModal,
    showUnsavedRunConfirm,
    previewTarget,
    stageToDelete,
    showAddStageModal,
    handleSelectRun,
    handleSave,
    handleUndo,
    handleRedo,
    handleDeleteSelected,
    handleDeleteSelectedEdge,
    handleDeleteStageRequest,
    handleDuplicateSelected,
  ]);

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

  const handleStageApproved = useCallback(async () => {
    if (!selectedRunId || typeof fetchRunState !== "function") return;
    try {
      const updated = await fetchRunState(selectedRunId);
      setSelectedRun(updated);
      setRunSubSeq((s) => s + 1);
    } catch {
      // ignore
    }
  }, [selectedRunId]);

  const handleResumeActiveRun = useCallback(async () => {
    if (!selectedRunId || typeof resumeRun !== "function") return;
    try {
      setRunActionBusy(true);
      await resumeRun(selectedRunId);
      const updated = await fetchRunState(selectedRunId);
      setSelectedRun(updated);
      setRunSubSeq((s) => s + 1);
    } catch {
      // ignore
    } finally {
      setRunActionBusy(false);
    }
  }, [selectedRunId]);

  return (
    <div
      data-testid="workflow-editor"
      className="flex flex-1 min-h-0 flex-col overflow-hidden"
    >
      {/* Top Control Panel Toolbar */}
      <WorkflowEditorToolbar
        viewMode={viewMode}
        onToggleViewMode={handleToggleViewMode}
        workflow={workflow}
        workflowPath={workflowPath}
        saving={saving}
        isDirty={isDirty}
        isInspectingRun={isInspectingRun}
        lastSavedAt={lastSavedAt}
        canUndo={canUndo}
        canRedo={canRedo}
        selectedNodeId={selectedNodeId}
        selectedStageId={selectedStageId}
        selectedEdgeId={selectedEdgeId}
        stageCount={stageIds.length}
        onSave={() => void handleSave()}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onRunClick={() => {
          if (isDirty) {
            setShowUnsavedRunConfirm(true);
          } else {
            setRunWithoutSaving(false);
            setShowRunModal(true);
          }
        }}
        onAutoLayout={handleAutoLayout}
        onOpenAddStage={() => {
          setShowAddStageModal(true);
          setNewStageModalTitle("");
          setNewStageModalRequireApproval(false);
        }}
        onDuplicateNode={handleDuplicateSelected}
        onDeleteNode={handleDeleteSelected}
        onDeleteStage={handleDeleteStageRequest}
        onDeleteEdge={handleDeleteSelectedEdge}
        runLayoutMode={runLayoutMode}
        onChangeRunLayoutMode={setRunLayoutMode}
      />

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

      {!isInspectingRun && driftAlerts.length > 0 && (
        <div
          role="status"
          data-testid="baseline-drift-banner"
          className="flex items-center justify-between gap-3 px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid rgba(171, 71, 188, 0.45)",
            backgroundColor: "rgba(171, 71, 188, 0.12)",
            color: "#e1bee7",
          }}
        >
          <div className="flex items-center gap-1.5 min-w-0">
            <FeatherIcon name="git-branch" size={12} />
            <span className="font-semibold shrink-0">Baseline Drift:</span>
            <span className="truncate">{driftAlerts[0].message}</span>
          </div>
          <button
            type="button"
            aria-label="Dismiss baseline drift alert"
            onClick={() => setDriftAlerts([])}
            className="px-1 shrink-0"
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
              fullHeight={viewMode !== "graph" || isInspectingRun}
              pageSize={viewMode !== "graph" || isInspectingRun ? 12 : 6}
              hasMore={Boolean(runsNextCursor)}
              loadingMore={runsLoadingMore}
              onLoadMore={() => void handleLoadMoreRuns()}
            />
            {viewMode === "graph" && !isInspectingRun && (
              <OpPalette
                ops={ops}
                onAddOp={(op) => handleAddOp(op)}
                collapsed={opsCollapsed}
                onToggleCollapse={() => setOpsCollapsed((v) => !v)}
                readOnly={isInspectingRun}
              />
            )}
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

            {isInspectingRun && selectedRun?.error && (
              <div
                data-testid="run-error-banner"
                className="px-3 py-1.5 text-xs flex items-center gap-1.5 shrink-0"
                style={{
                  borderBottom: "1px solid var(--color-error)",
                  backgroundColor: "rgba(244, 67, 54, 0.15)",
                  color: "#ff8a80",
                }}
              >
                <FeatherIcon name="alert-triangle" size={12} />
                <span className="font-semibold">Error:</span> {selectedRun.error}
              </div>
            )}

            {isInspectingRun && selectedRun ? (
              <RunInspector
                runState={selectedRun}
                viewMode={viewMode}
                ops={ops}
                opsMap={opsMap}
                editorWorkflow={workflow}
                fallbackLayout={layout}
                runDiff={runDiff}
                selectedNodeId={selectedNodeId}
                onSelectNode={handleSelectNode}
                onPreviewArtifact={setPreviewTarget}
                onApproved={handleStageApproved}
                onCheckpointAnswered={() => void handleStageApproved()}
                showNodeInspector={false}
                runLayoutMode={runLayoutMode}
                onChangeRunLayoutMode={setRunLayoutMode}
                showLayoutToggle={false}
              />
            ) : (
              <div
                className={`flex-1 min-h-0 ${
                  viewMode === "graph"
                    ? "overflow-hidden h-full"
                    : "overflow-y-auto"
                }`}
              >
                {viewMode === "graph" ? (
                  <GraphView
                    workflow={workflow}
                    layout={layout}
                    runState={null}
                    runDiff={null}
                    ops={ops}
                    selectedNodeId={selectedNodeId}
                    onSelectNode={handleSelectNode}
                    selectedEdgeId={selectedEdgeId}
                    onSelectEdge={setSelectedEdgeId}
                    selectedStageId={selectedStageId}
                    onSelectStage={handleSelectStage}
                    onSelectValidator={(sid) => handleSelectStage(sid)}
                    onDeleteStage={handleDeleteStageRequest}
                    readOnly={false}
                    onConnect={handleConnect}
                    onNodeDragStop={handleNodeDragStop}
                    onStageDragStop={handleStageDragStop}
                    onDropOp={handleDropOp}
                    onWireDropOnPane={handleWireDropOnPane}
                    onViewportChange={(vp) => {
                      writeLocalViewport(workflowPath, vp);
                    }}
                    onLiteralChange={handleInlineLiteralChange}
                    onPreviewOutput={handlePreviewNodeOutput}
                    onMeasuredDimensionsChange={(dims) => {
                      measuredDimsRef.current = dims;
                    }}
                    hasSavedViewport={hasSavedViewport}
                    fitViewTrigger={fitViewTrigger}
                    heightClassName="h-full"
                  />
                ) : (
                  <StepperView
                    runState={null}
                    workflowDoc={{ workflow, layout }}
                    runDiff={null}
                    selectedNodeId={selectedNodeId}
                    onSelectNode={handleSelectNode}
                    opsMap={opsMap}
                    onApproved={handleStageApproved}
                  />
                )}
              </div>
            )}
          </div>

          {/* Right Docked PropertiesBar */}
          <NodeInspector
            nodeId={selectedNodeId}
            selectedStageId={isInspectingRun ? undefined : selectedStageId}
            onSelectStage={handleSelectStage}
            workflow={
              isInspectingRun && selectedRun?.workflow_snapshot
                ? selectedRun.workflow_snapshot
                : workflow
            }
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
            onCheckpointAnswered={() => void handleStageApproved()}
            onAddStage={handleAddStage}
            onUpdateStage={handleUpdateStage}
            onDeleteStage={handleDeleteStageRequest}
            onReorderStages={handleReorderStages}
          />
        </div>
      ) : null}

      <WorkflowEditorModals
        workflowPath={workflowPath}
        workflow={workflow}
        layout={layout}
        ops={ops}
        opsMap={opsMap}
        showUnsavedRunConfirm={showUnsavedRunConfirm}
        onCloseUnsavedRunConfirm={() => setShowUnsavedRunConfirm(false)}
        onRunWithoutSaving={() => {
          setShowUnsavedRunConfirm(false);
          setRunWithoutSaving(true);
          setShowRunModal(true);
        }}
        onSaveAndRun={async () => {
          const saved = await handleSave();
          if (!saved) return;
          setShowUnsavedRunConfirm(false);
          setRunWithoutSaving(false);
          setShowRunModal(true);
        }}
        showRunModal={showRunModal}
        runWithoutSaving={runWithoutSaving}
        onCloseRunModal={() => setShowRunModal(false)}
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
            fetchRuns({ workflowPath, limit: 50 })
              .then((list) => {
                const matches = list.runs.filter(
                  (r) => r.workflow_path === workflowPath,
                );
                if (matches.length > 0) {
                  setWorkflowRuns(matches);
                  setRunsNextCursor(list.next_cursor ?? null);
                }
                setDriftAlerts(
                  (list.drift_alerts ?? []).filter(
                    (a) => a.workflow_path === workflowPath,
                  ),
                );
              })
              .catch(() => {});
          }
        }}
        previewTarget={previewTarget}
        onClosePreview={() => setPreviewTarget(null)}
        showAddStageModal={showAddStageModal}
        newStageModalTitle={newStageModalTitle}
        newStageModalRequireApproval={newStageModalRequireApproval}
        onChangeNewStageTitle={setNewStageModalTitle}
        onChangeNewStageRequireApproval={setNewStageModalRequireApproval}
        onCloseAddStageModal={() => {
          setShowAddStageModal(false);
          setNewStageModalTitle("");
          setNewStageModalRequireApproval(false);
        }}
        onCreateStage={handleAddStage}
        stageToDelete={stageToDelete}
        deleteStageChoice={deleteStageChoice}
        onChangeDeleteStageChoice={setDeleteStageChoice}
        onCloseDeleteStage={() => setStageToDelete(null)}
        onConfirmDeleteStage={handleConfirmDeleteStage}
        quickConnectData={quickConnectData}
        onQuickConnectSelect={handleQuickConnectSelect}
        onCloseQuickConnect={() => setQuickConnectData(null)}
      />
    </div>
  );
}
