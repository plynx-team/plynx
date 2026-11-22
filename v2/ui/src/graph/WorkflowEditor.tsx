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
  InputPortSpec,
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
import { GraphView, type WireDropOnPaneEvent } from "./GraphView";
import {
  computeDagrePositions,
  DEFAULT_STAGE_ID,
  getOrderedStageIds,
  resolveNodePorts,
} from "./layout";
import { parseHandleId } from "./types";
import {
  QuickConnectPopover,
  type QuickConnectDropData,
} from "./QuickConnectPopover";
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
  toSnakeCaseId,
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
import { computeWorkflowRunDiff } from "./runDiff";
import { validateConnection } from "./validation";

export type EditorViewMode = "graph" | "stepper" | "runs";

const TERMINAL_RUN_STATUSES = new Set(["SUCCESS", "FAILED", "CANCELED"]);

function serializeSnapshot(
  workflow: Workflow | null,
  layout: WorkflowLayout | null,
): string {
  const nodes = layout?.nodes ?? {};
  return JSON.stringify({ workflow, nodes });
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
    if (v === "graph" || v === "runs" || v === "stepper") {
      return v;
    }
    return "stepper";
  };
  const [viewMode, setViewMode] = useState<EditorViewMode>(getInitialViewMode);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [layout, setLayout] = useState<WorkflowLayout | null>(null);
  const [history, setHistory] = useState<WorkflowHistory | null>(null);
  const lastTextEditTimeRef = useRef<number>(0);
  const workflowRef = useRef<Workflow | null>(null);
  const layoutRef = useRef<WorkflowLayout | null>(null);

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
  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    () => queryParams?.run_id || null,
  );
  const isInspectingRun = selectedRunId !== null;
  const [selectedRun, setSelectedRun] = useState<RunState | null>(null);
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
        const initialLayout = ensureLayout(doc.workflow, doc.layout, map);
        const stageIds = getOrderedStageIds(doc.workflow);
        workflowRef.current = doc.workflow;
        layoutRef.current = initialLayout;
        setWorkflow(doc.workflow);
        setLayout(initialLayout);
        setHistory(createHistory({ workflow: doc.workflow, layout: initialLayout }));
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
        return updated;
      });
    },
    [],
  );

  const canUndo = Boolean(history && history.past.length > 0 && !isInspectingRun);
  const canRedo = Boolean(history && history.future.length > 0 && !isInspectingRun);

  const handleUndo = useCallback(() => {
    if (isInspectingRun) return;
    setHistory((curr) => {
      if (!curr) return null;
      const res = undoHistory(curr);
      if (!res) return curr;
      workflowRef.current = res.restored.workflow;
      layoutRef.current = res.restored.layout;
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
      return res.history;
    });
  }, [isInspectingRun]);

  const handleRedo = useCallback(() => {
    if (isInspectingRun) return;
    setHistory((curr) => {
      if (!curr) return null;
      const res = redoHistory(curr);
      if (!res) return curr;
      workflowRef.current = res.restored.workflow;
      layoutRef.current = res.restored.layout;
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
      return res.history;
    });
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
      updates: { title?: string; require_approval?: boolean },
    ) => {
      if (!workflow) return;
      const nextWf = updateStageInWorkflow(workflow, stageId, updates);
      commitStateChange(nextWf, undefined, { coalesce: true });
    },
    [workflow, commitStateChange],
  );

  const handleDeleteStageRequest = useCallback(
    (stageId: string) => {
      if (!workflow) return;
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
    [workflow, layout, opsMap, selectedStageId, targetStage, commitStateChange],
  );

  const handleConfirmDeleteStage = useCallback(() => {
    if (!workflow || !stageToDelete) return;
    const res = deleteStageFromWorkflow(workflow, layout, stageToDelete, {
      deleteNodes: deleteStageChoice === "delete",
      reassignToStageId: DEFAULT_STAGE_ID,
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
  }, [selectedNodeId, opsMap, commitStateChange]);

  const handleDeleteSelected = useCallback(() => {
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
  }, [selectedNodeId, opsMap, commitStateChange]);

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

      // Connect edge
      let nextWf: Workflow;
      if (data.handleType === "source") {
        // Wire: origin (output) -> new node (input)
        nextWf = connectEdgeInWorkflow(
          added.workflow,
          data.originNodeId,
          data.originPortName,
          added.nodeId,
          portName,
        );
      } else {
        // Wire: new node (output) -> origin (input)
        nextWf = connectEdgeInWorkflow(
          added.workflow,
          added.nodeId,
          portName,
          data.originNodeId,
          data.originPortName,
        );
      }

      commitStateChange(nextWf, added.layout);
      setSelectedNodeId(added.nodeId);
    },
    [quickConnectData, opsMap, commitStateChange],
  );

  const handleDeleteSelectedEdge = useCallback(() => {
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
  }, [selectedEdgeId, commitStateChange]);

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
      if (newView === "graph" || newView === "runs") {
        params.set("view", newView);
      } else if (newView === "stepper" && (newRunId || queryParams?.view === "stepper")) {
        params.set("view", "stepper");
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
      let nextView = viewMode;
      if (nextRunId !== null) {
        setOpsCollapsed(true);
        setRunsCollapsed(false);
        if (viewMode === "runs") {
          nextView = "stepper";
          setViewMode("stepper");
        }
      } else {
        setSelectedRun(null);
        setOpsCollapsed(false);
      }
      syncUrlParams(nextView, nextRunId);
    },
    [viewMode, syncUrlParams],
  );

  useEffect(() => {
    const v = queryParams?.view;
    if (v === "graph" || v === "runs" || v === "stepper") {
      setViewMode(v);
    } else if (!v) {
      setViewMode("stepper");
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
  }, [opsMap, commitStateChange]);

  const isDirty = useMemo(() => {
    if (savedSnapshot === null || !workflow) return false;
    return serializeSnapshot(workflow, layout) !== savedSnapshot;
  }, [savedSnapshot, workflow, layout]);

  const handleSave = useCallback(async () => {
    const currentWf = workflowRef.current;
    if (!currentWf || saving) return;
    const currentLayout = layoutRef.current;
    const finalLayout = ensureLayout(currentWf, currentLayout, opsMap);
    try {
      setSaving(true);
      setSaveError(null);
      const savedDoc = await saveWorkflow(workflowPath, {
        workflow: prepareWorkflowForSave(currentWf),
        layout: finalLayout,
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
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : String(err));
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

      if (event.key === "Escape" && selectedRunId !== null) {
        event.preventDefault();
        handleSelectRun(null);
        return;
      }

      if (isEditableElement(event.target)) return;
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
            aria-selected={viewMode === "stepper"}
            onClick={() => handleToggleViewMode("stepper")}
            className={`control-button first ${
              viewMode === "stepper" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="sliders" size={14} />
            <span className="control-button-text">Stepper</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "graph"}
            onClick={() => handleToggleViewMode("graph")}
            className={`control-button ${
              viewMode === "graph" ? "selected" : ""
            }`}
          >
            <FeatherIcon name="grid" size={14} />
            <span className="control-button-text">Graph</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === "runs"}
            onClick={() => handleToggleViewMode("runs")}
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
          icon="rotate-ccw"
          text="Undo"
          data-testid="btn-undo"
          disabled={!canUndo}
          onClick={handleUndo}
          title="Undo (Ctrl+Z / ⌘Z)"
        />

        <ControlButton
          icon="rotate-cw"
          text="Redo"
          data-testid="btn-redo"
          disabled={!canRedo}
          onClick={handleRedo}
          title="Redo (Ctrl+Shift+Z / ⌘⇧Z)"
        />

        <ControlButton
          icon="play"
          text="Run Workflow"
          data-testid="btn-run-workflow"
          variant="primary"
          onClick={() => {
            if (isDirty) {
              setShowUnsavedRunConfirm(true);
            } else {
              setRunWithoutSaving(false);
              setShowRunModal(true);
            }
          }}
        />

        <ControlButton
          icon="layout"
          text="Auto Layout"
          data-testid="btn-auto-layout"
          disabled={!workflow}
          onClick={handleAutoLayout}
        />

        <ControlButton
          icon="layers"
          text="+ Stage"
          data-testid="btn-add-stage"
          disabled={!workflow || isInspectingRun}
          onClick={() => {
            setShowAddStageModal(true);
            setNewStageModalTitle("");
            setNewStageModalRequireApproval(false);
          }}
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

        {selectedStageId && (
          <ControlButton
            icon="trash-2"
            text="Delete Stage"
            data-testid="btn-delete-stage-toolbar"
            variant="danger"
            disabled={stageIds.length <= 1 || isInspectingRun}
            onClick={() => handleDeleteStageRequest(selectedStageId)}
          />
        )}

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
              fullHeight={viewMode !== "graph" || isInspectingRun}
              pageSize={viewMode !== "graph" || isInspectingRun ? 12 : 6}
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

            {/* Open Checkpoints & Stage Approvals for the Selected Run (Graph view overlay only; Stepper view renders them inside its stage cards) */}
            {isInspectingRun && selectedRun && viewMode === "graph" && (
              <div
                className="absolute top-11 left-3 right-3 z-20 space-y-2 pointer-events-none empty:hidden max-h-[40vh] overflow-y-auto"
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
                  selectedStageId={selectedStageId}
                  onSelectStage={handleSelectStage}
                  onDeleteStage={handleDeleteStageRequest}
                  readOnly={isInspectingRun}
                  onConnect={handleConnect}
                  onNodeDragStop={handleNodeDragStop}
                  onStageDragStop={handleStageDragStop}
                  onDropOp={handleDropOp}
                  onWireDropOnPane={handleWireDropOnPane}
                  onLiteralChange={handleInlineLiteralChange}
                  onPreviewOutput={handlePreviewNodeOutput}
                  onMeasuredDimensionsChange={(dims) => {
                    measuredDimsRef.current = dims;
                  }}
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
            selectedStageId={selectedStageId}
            onSelectStage={handleSelectStage}
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
            onAddStage={handleAddStage}
            onUpdateStage={handleUpdateStage}
            onDeleteStage={handleDeleteStageRequest}
            onReorderStages={handleReorderStages}
          />
        </div>
      ) : null}

      {showUnsavedRunConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="unsaved-run-confirm-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
        >
          <div
            className="w-full max-w-md rounded border border-[#404040] bg-[#242424] shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#3c3c3c] px-4 py-3">
              <div className="flex items-center gap-2">
                <FeatherIcon
                  name="alert-triangle"
                  size={16}
                  style={{ color: "var(--color-warning, #ffa726)" }}
                />
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Unsaved Changes
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowUnsavedRunConfirm(false)}
                className="p-1 rounded hover:bg-[#3c3c3c]"
                style={{ color: "var(--text-secondary)" }}
              >
                <FeatherIcon name="x" size={14} />
              </button>
            </div>

            <div className="p-4 space-y-3 text-xs" style={{ color: "var(--text-secondary)" }}>
              <p>
                You have unsaved changes in this workflow. How would you like to launch the run?
              </p>
              <div className="rounded p-2.5 bg-[#1a1a1a] border border-[#333] space-y-1">
                <div>
                  <strong className="text-[var(--text-primary)]">Save & Run:</strong> Saves your current workflow to disk and executes it.
                </div>
                <div>
                  <strong className="text-[var(--text-primary)]">Run Without Saving:</strong> Keeps the file on disk untouched, but executes your in-memory editor workflow.
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-[#3c3c3c] bg-[#1e1e1e] px-4 py-2.5">
              <button
                type="button"
                data-testid="btn-cancel-unsaved-run"
                onClick={() => setShowUnsavedRunConfirm(false)}
                className="control-button !h-7 !px-3 text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="btn-run-without-saving"
                onClick={() => {
                  setShowUnsavedRunConfirm(false);
                  setRunWithoutSaving(true);
                  setShowRunModal(true);
                }}
                className="control-button !h-7 !px-3 text-xs"
              >
                Run Without Saving
              </button>
              <button
                type="button"
                data-testid="btn-save-and-run"
                onClick={async () => {
                  setShowUnsavedRunConfirm(false);
                  await handleSave();
                  setRunWithoutSaving(false);
                  setShowRunModal(true);
                }}
                className="control-button primary !h-7 !px-3 text-xs font-semibold"
              >
                Save & Run
              </button>
            </div>
          </div>
        </div>
      )}

      {showRunModal && (
        <RunInputsForm
          workflowPath={workflowPath}
          asModal={true}
          inMemoryWorkflow={runWithoutSaving ? workflow : undefined}
          inMemoryLayout={runWithoutSaving ? layout : undefined}
          opsMap={opsMap}
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

      {/* Add Stage Modal */}
      {showAddStageModal && (
        <div
          data-testid="modal-add-stage"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowAddStageModal(false)}
        >
          <div
            className="w-full max-w-sm rounded-lg p-5 shadow-xl space-y-4"
            style={{
              backgroundColor: "var(--bg-panel)",
              border: "1px solid var(--border-default)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <FeatherIcon
                name="layers"
                size={16}
                style={{ color: "var(--color-primary)" }}
              />
              <span>Add Stage</span>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-[var(--text-secondary)] mb-1">
                  Stage Title
                </label>
                <input
                  type="text"
                  data-testid="modal-input-stage-title"
                  placeholder="e.g. Processing"
                  value={newStageModalTitle}
                  onChange={(e) => setNewStageModalTitle(e.target.value)}
                  className="w-full px-2 py-1.5 text-xs rounded"
                  autoFocus
                />
              </div>

              <label className="flex items-start gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  data-testid="modal-checkbox-stage-gate"
                  checked={newStageModalRequireApproval}
                  onChange={(e) =>
                    setNewStageModalRequireApproval(e.target.checked)
                  }
                  className="mt-0.5 rounded"
                />
                <div>
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Require approval (Stage Gate)
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Pauses run execution before downstream stages begin.
                  </span>
                </div>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#3c3c3c]">
              <button
                type="button"
                onClick={() => {
                  setShowAddStageModal(false);
                  setNewStageModalTitle("");
                  setNewStageModalRequireApproval(false);
                }}
                className="control-button"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="modal-btn-create-stage"
                disabled={!newStageModalTitle.trim()}
                onClick={() => {
                  const title = newStageModalTitle.trim();
                  const slug = toSnakeCaseId(title);
                  handleAddStage(slug, title, {
                    requireApproval: newStageModalRequireApproval,
                  });
                  setShowAddStageModal(false);
                  setNewStageModalTitle("");
                  setNewStageModalRequireApproval(false);
                }}
                className="control-button primary"
              >
                Create Stage
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Stage with Operations Confirmation Modal */}
      {stageToDelete && (
        <div
          data-testid="modal-delete-stage"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setStageToDelete(null)}
        >
          <div
            className="w-full max-w-md rounded-lg p-5 shadow-xl space-y-4"
            style={{
              backgroundColor: "var(--bg-panel)",
              border: "1px solid var(--border-default)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <FeatherIcon
                name="alert-triangle"
                size={16}
                style={{ color: "var(--color-warning)" }}
              />
              <span>
                Delete Stage:{" "}
                {workflow?.stages?.[stageToDelete]?.title || stageToDelete}
              </span>
            </div>

            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              This stage contains{" "}
              <strong className="text-[var(--text-primary)]">
                {
                  Object.values(workflow?.nodes ?? {}).filter(
                    (n) => (n.stage || DEFAULT_STAGE_ID) === stageToDelete,
                  ).length
                }{" "}
                operations
              </strong>
              . Choose what to do with them:
            </p>

            <div className="space-y-2 text-xs">
              <label className="flex items-start gap-2 p-2.5 rounded bg-[#242424] border border-[#3c3c3c] cursor-pointer">
                <input
                  type="radio"
                  name="delete-stage-choice"
                  value="reassign"
                  checked={deleteStageChoice === "reassign"}
                  onChange={() => setDeleteStageChoice("reassign")}
                  className="mt-0.5"
                />
                <div>
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Keep operations and move to Workflow (main - Default)
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Operations and their connections will be retained in the
                    default stage.
                  </span>
                </div>
              </label>

              <label className="flex items-start gap-2 p-2.5 rounded bg-[#242424] border border-[#3c3c3c] cursor-pointer">
                <input
                  type="radio"
                  name="delete-stage-choice"
                  value="delete"
                  checked={deleteStageChoice === "delete"}
                  onChange={() => setDeleteStageChoice("delete")}
                  className="mt-0.5"
                />
                <div>
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--color-error)" }}
                  >
                    Delete operations along with the stage
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    All operations in this stage and their incoming/outgoing
                    wires will be deleted.
                  </span>
                </div>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#3c3c3c]">
              <button
                type="button"
                onClick={() => setStageToDelete(null)}
                className="control-button"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="btn-confirm-delete-stage"
                onClick={handleConfirmDeleteStage}
                className="control-button danger"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {quickConnectData && (
        <QuickConnectPopover
          data={quickConnectData}
          ops={ops}
          onSelect={handleQuickConnectSelect}
          onClose={() => setQuickConnectData(null)}
        />
      )}
    </div>
  );
}
