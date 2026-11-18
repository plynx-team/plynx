import type {
  AnswerCheckpointRequest,
  CreateRunRequest,
  CreateRunResponse,
  EventType,
  RunEvent,
  RunListResponse,
  RunState,
  UploadResponse,
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

export async function fetchRuns(): Promise<RunListResponse> {
  const response = await fetch("/api/v1/runs");
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
  answer: string,
): Promise<void> {
  const payload: AnswerCheckpointRequest = { answer };
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
): Promise<void> {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/stage-gates/${encodeURIComponent(
      stageId,
    )}/approve`,
    {
      method: "POST",
    },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to approve stage gate ${stageId} (${response.status})`,
    );
  }
}

export async function fetchNodeLogs(
  runId: string,
  nodeId: string,
  offset = 0,
): Promise<{ lines: Array<string>; offset: number }> {
  const response = await fetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/logs/${encodeURIComponent(
      nodeId,
    )}?offset=${offset}`,
  );
  if (!response.ok) {
    throw new Error(
      `Failed to fetch logs for node ${nodeId} (${response.status})`,
    );
  }
  return (await response.json()) as { lines: Array<string>; offset: number };
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

export function subscribeRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const source = new EventSource(
    `/api/v1/runs/${encodeURIComponent(runId)}/stream`,
  );
  const handleMessage = (ev: MessageEvent<string>) => {
    const parsed = JSON.parse(ev.data) as RunEvent;
    onEvent(parsed);
  };
  for (const eventName of EVENT_TYPES) {
    source.addEventListener(eventName, handleMessage as EventListener);
  }
  if (onError) {
    source.onerror = onError;
  }
  return () => {
    source.close();
  };
}
