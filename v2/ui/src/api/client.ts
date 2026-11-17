import type {
  EventType,
  RunEvent,
  RunListResponse,
  RunState,
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
