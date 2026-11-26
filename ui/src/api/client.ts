import type {
  AgentTurnsResponse,
  AnswerCheckpointRequest,
  CreateRunRequest,
  CreateRunResponse,
  EventType,
  LogStream,
  OpEntry,
  RunEvent,
  RunListResponse,
  RunState,
  UploadResponse,
  ValidateWorkflowRequest,
  ValidateWorkflowResponse,
  Workflow,
  WorkflowDocument,
  WorkflowInputSpec,
  WorkflowListItem,
} from "./types.gen";

const EVENT_TYPES: ReadonlyArray<EventType> = [
  "run_status",
  "node_status",
  "node_checkpoint",
  "checkpoint_resolved",
  "stage_approval",
  "stage_resolved",
  "node_log",
];

export async function fetchOps(): Promise<Array<OpEntry>> {
  const response = await fetch("/api/v1/ops");
  if (!response.ok) {
    throw new Error(`Failed to fetch ops (${response.status})`);
  }
  return (await response.json()) as Array<OpEntry>;
}

export interface FetchRunsOptions {
  limit?: number;
  cursor?: string;
  workflowPath?: string;
}

export async function fetchRuns(
  options?: FetchRunsOptions,
): Promise<RunListResponse> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options?.cursor) {
    params.set("cursor", options.cursor);
  }
  if (options?.workflowPath) {
    params.set("workflow_path", options.workflowPath);
  }
  const qs = params.toString();
  const response = await fetch(`/api/v1/runs${qs ? `?${qs}` : ""}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch runs (${response.status})`);
  }
  return (await response.json()) as RunListResponse;
}

export async function fetchRunState(runId: string): Promise<RunState> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch run ${runId} (${response.status})`);
  }
  return (await response.json()) as RunState;
}

export async function fetchWorkflows(): Promise<Array<WorkflowListItem>> {
  const response = await fetch("/api/v1/workflows");
  if (!response.ok) {
    throw new Error(`Failed to fetch workflows (${response.status})`);
  }
  return (await response.json()) as Array<WorkflowListItem>;
}

export async function fetchWorkflow(path: string): Promise<WorkflowDocument> {
  const response = await fetch(`/api/v1/workflows/${encodeURIComponent(path)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch workflow ${path} (${response.status})`);
  }
  return (await response.json()) as WorkflowDocument;
}

export async function saveWorkflow(
  path: string,
  doc: WorkflowDocument,
): Promise<WorkflowDocument> {
  const encodedPath = path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const response = await fetch(`/api/v1/workflows/${encodedPath}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg =
      errorBody?.error?.message ||
      `Failed to save workflow ${path} (${response.status})`;
    throw new Error(msg);
  }
  return (await response.json()) as WorkflowDocument;
}

export async function validateWorkflowApi(
  workflow: Workflow,
): Promise<ValidateWorkflowResponse> {
  const payload: ValidateWorkflowRequest = { workflow };
  const response = await fetch("/api/v1/workflows/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Failed to validate workflow (${response.status})`);
  }
  return (await response.json()) as ValidateWorkflowResponse;
}

export async function fetchWorkflowInputs(
  path: string,
): Promise<Array<WorkflowInputSpec>> {
  const response = await fetch(
    `/api/v1/workflows/${encodeURIComponent(path)}/inputs`,
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch inputs for workflow ${path} (${response.status})`,
    );
  }
  return (await response.json()) as Array<WorkflowInputSpec>;
}

export async function createRun(
  req: CreateRunRequest,
): Promise<CreateRunResponse> {
  const response = await fetch("/api/v1/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message || `Failed to create run (${response.status})`;
    throw new Error(msg);
  }
  return (await response.json()) as CreateRunResponse;
}

export async function cancelRun(runId: string): Promise<void> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to cancel run ${runId} (${response.status})`);
  }
}

export async function resumeRun(runId: string): Promise<CreateRunResponse> {
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/resume`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to resume run ${runId} (${response.status})`);
  }
  return (await response.json()) as CreateRunResponse;
}

export async function answerCheckpoint(
  runId: string,
  nodeId: string,
  checkpointId: string,
  answer: string | Record<string, string | string[]>,
): Promise<void> {
  const payload: AnswerCheckpointRequest =
    typeof answer === "string" ? { answer } : { answers: answer };
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/checkpoints/${encodeURIComponent(
      nodeId,
    )}/${encodeURIComponent(checkpointId)}/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to answer checkpoint ${checkpointId} (${response.status})`,
    );
  }
}

export async function approveStage(
  runId: string,
  stageId: string,
  inputs?: Record<string, unknown>,
): Promise<void> {
  const options: RequestInit = {
    method: "POST",
  };
  if (inputs && Object.keys(inputs).length > 0) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify({ inputs });
  }
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/stages/${encodeURIComponent(
      stageId,
    )}/approve`,
    options,
  );
  if (!response.ok) {
    throw new Error(
      `Failed to approve stage gate ${stageId} (${response.status})`,
    );
  }
}

export async function submitStageInputs(
  runId: string,
  stageId: string,
  inputs: Record<string, unknown>,
): Promise<void> {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/stages/${encodeURIComponent(
      stageId,
    )}/inputs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs }),
    },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to submit stage inputs for ${stageId} (${response.status})`,
    );
  }
}

export async function fetchNodeLogs(
  runId: string,
  nodeId: string,
  offset = 0,
  stream: LogStream = "stdout",
): Promise<{ lines: Array<string>; offset: number }> {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(
      nodeId,
    )}/logs/${encodeURIComponent(stream)}?offset=${offset}`,
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch logs for node ${nodeId} (${response.status})`,
    );
  }
  const text = await response.text();
  const nextOffsetHeader = response.headers.get("X-Next-Offset");
  const nextOffset =
    nextOffsetHeader !== null && !Number.isNaN(Number(nextOffsetHeader))
      ? Number(nextOffsetHeader)
      : offset + text.length;
  const lines = text
    ? text.split(/\r?\n/).filter((line, idx, arr) => !(idx === arr.length - 1 && line === ""))
    : [];
  return { lines, offset: nextOffset };
}

export async function fetchNodeAgentTurns(
  runId: string,
  nodeId: string,
): Promise<AgentTurnsResponse> {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(
      nodeId,
    )}/agent-turns`,
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch agent turns for node ${nodeId} (${response.status})`,
    );
  }
  return (await response.json()) as AgentTurnsResponse;
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/v1/uploads", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`Upload failed (${response.status})`);
  }
  return (await response.json()) as UploadResponse;
}

export interface SubscribeRunEventsOptions {
  logOffset?: number;
}

interface SharedSubscription {
  source: EventSource;
  listeners: Set<(event: RunEvent) => void>;
  errorListeners: Set<(err: Event) => void>;
}

const sharedSubscriptions = new Map<string, SharedSubscription>();

export function subscribeRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (err: Event) => void,
  options?: SubscribeRunEventsOptions,
): () => void {
  const params = new URLSearchParams();
  if (options?.logOffset !== undefined) {
    params.set("log_offset", String(options.logOffset));
  }
  const query = params.toString();
  const url = `/api/v1/runs/${encodeURIComponent(runId)}/stream${
    query ? `?${query}` : ""
  }`;

  let sub = sharedSubscriptions.get(url);
  if (!sub) {
    const source = new EventSource(url);
    const listeners = new Set<(event: RunEvent) => void>();
    const errorListeners = new Set<(err: Event) => void>();

    const handleMessage = (ev: MessageEvent<string>) => {
      const parsed = JSON.parse(ev.data) as RunEvent;
      for (const listener of listeners) {
        listener(parsed);
      }
    };

    for (const eventName of EVENT_TYPES) {
      source.addEventListener(eventName, handleMessage as EventListener);
    }

    source.onerror = (err: Event) => {
      for (const errorListener of errorListeners) {
        errorListener(err);
      }
    };

    sub = { source, listeners, errorListeners };
    sharedSubscriptions.set(url, sub);
  }

  sub.listeners.add(onEvent);
  if (onError) {
    sub.errorListeners.add(onError);
  }

  return () => {
    const currentSub = sharedSubscriptions.get(url);
    if (!currentSub) return;
    currentSub.listeners.delete(onEvent);
    if (onError) {
      currentSub.errorListeners.delete(onError);
    }
    if (currentSub.listeners.size === 0) {
      currentSub.source.close();
      sharedSubscriptions.delete(url);
    }
  };
}
