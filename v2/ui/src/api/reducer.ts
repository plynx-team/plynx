import type {
  CheckpointState,
  NodeRunState,
  RunEvent,
  RunState,
  StageGateState,
} from "./types.gen";

export function createInitialRunState(
  runId: string,
  workflowPath = "",
): RunState {
  return {
    id: runId,
    workflow_path: workflowPath,
    workflow_sha256: "",
    status: "RUNNING",
    run_inputs: {},
    owner_pid: null,
    cancel_requested: false,
    pinned: false,
    created_at: 0,
    started_at: null,
    finished_at: null,
    error: null,
    nodes: {},
    checkpoints: [],
    stage_gates: {},
  };
}

export function applyRunEvent(state: RunState, event: RunEvent): RunState {
  switch (event.type) {
    case "run_status": {
      return {
        ...state,
        status: event.data.status,
        error:
          event.data.status === "RUNNING"
            ? (event.data.error ?? null)
            : (event.data.error ?? state.error ?? null),
      };
    }
    case "node_status": {
      const existing: NodeRunState | undefined =
        state.nodes[event.data.node_id];
      const updatedNode: NodeRunState = {
        node_id: event.data.node_id,
        status: event.data.status,
        cache_hit: event.data.cache_hit,
        cache_key: existing?.cache_key ?? null,
        attempt: event.data.attempt,
        exit_code: event.data.exit_code ?? existing?.exit_code ?? null,
        error: event.data.error ?? existing?.error ?? null,
        started_at: existing?.started_at ?? null,
        finished_at: existing?.finished_at ?? null,
      };
      return {
        ...state,
        nodes: {
          ...state.nodes,
          [event.data.node_id]: updatedNode,
        },
      };
    }
    case "node_checkpoint": {
      const existingCp = state.checkpoints.find(
        (cp) =>
          cp.node_id === event.data.node_id &&
          cp.checkpoint_id === event.data.checkpoint_id,
      );
      // Do not revert an already-resolved checkpoint when historical SSE events replay
      if (existingCp && existingCp.answered_at !== null && existingCp.answered_at !== undefined) {
        return state;
      }
      const newCp: CheckpointState = {
        node_id: event.data.node_id,
        checkpoint_id: event.data.checkpoint_id,
        question: event.data.question,
        options: event.data.options ?? null,
        allow_freeform: event.data.allow_freeform,
        answer: null,
        created_at: existingCp?.created_at ?? event.ts,
        answered_at: null,
      };
      const filtered = state.checkpoints.filter(
        (cp) =>
          !(
            cp.node_id === newCp.node_id &&
            cp.checkpoint_id === newCp.checkpoint_id
          ),
      );
      return {
        ...state,
        checkpoints: [...filtered, newCp],
      };
    }
    case "checkpoint_resolved": {
      const updatedCheckpoints = state.checkpoints.map((cp) =>
        cp.node_id === event.data.node_id &&
        cp.checkpoint_id === event.data.checkpoint_id
          ? { ...cp, answered_at: event.ts }
          : cp,
      );
      return {
        ...state,
        checkpoints: updatedCheckpoints,
      };
    }
    case "stage_approval": {
      const prevGate = state.stage_gates[event.data.stage_id];
      // Do not revert an already-approved gate when historical SSE events replay
      if (prevGate?.status === "APPROVED") {
        return state;
      }
      const gate: StageGateState = {
        stage_id: event.data.stage_id,
        status: "WAITING",
        created_at: prevGate?.created_at ?? event.ts,
        decided_at: null,
      };
      return {
        ...state,
        stage_gates: {
          ...state.stage_gates,
          [event.data.stage_id]: gate,
        },
      };
    }
    case "stage_resolved": {
      const prev: StageGateState | undefined =
        state.stage_gates[event.data.stage_id];
      const gate: StageGateState = {
        stage_id: event.data.stage_id,
        status: "APPROVED",
        created_at: prev?.created_at ?? event.ts,
        decided_at: event.ts,
      };
      return {
        ...state,
        stage_gates: {
          ...state.stage_gates,
          [event.data.stage_id]: gate,
        },
      };
    }
    case "node_log": {
      return state;
    }
  }
}

export function reduceRunEvents(
  initialState: RunState,
  events: ReadonlyArray<RunEvent>,
): RunState {
  return events.reduce(applyRunEvent, initialState);
}
