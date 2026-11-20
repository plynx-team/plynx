import type { Workflow, WorkflowLayout } from "../api/types.gen";

export interface WorkflowDocSnapshot {
  workflow: Workflow;
  layout: WorkflowLayout;
}

export interface WorkflowHistory {
  past: Array<WorkflowDocSnapshot>;
  present: WorkflowDocSnapshot;
  future: Array<WorkflowDocSnapshot>;
}

export interface PushHistoryOptions {
  limit?: number;
  coalesce?: boolean;
  lastActionTime?: number;
  coalesceWindowMs?: number;
}

export function createHistory(initial: WorkflowDocSnapshot): WorkflowHistory {
  return {
    past: [],
    present: initial,
    future: [],
  };
}

export function areSnapshotsEqual(
  a: WorkflowDocSnapshot,
  b: WorkflowDocSnapshot,
): boolean {
  return (
    JSON.stringify(a.workflow) === JSON.stringify(b.workflow) &&
    JSON.stringify(a.layout.nodes) === JSON.stringify(b.layout.nodes)
  );
}

export function pushHistory(
  history: WorkflowHistory,
  next: WorkflowDocSnapshot,
  options?: PushHistoryOptions,
): WorkflowHistory {
  const limit = options?.limit ?? 50;
  const coalesceWindowMs = options?.coalesceWindowMs ?? 600;

  // No-op if content is identical
  if (areSnapshotsEqual(history.present, next)) {
    return history;
  }

  // Coalesce rapid edits (e.g. typing in text fields)
  if (
    options?.coalesce &&
    options?.lastActionTime &&
    Date.now() - options.lastActionTime < coalesceWindowMs
  ) {
    return {
      past: history.past,
      present: next,
      future: [],
    };
  }

  return {
    past: [...history.past, history.present].slice(-limit),
    present: next,
    future: [],
  };
}

export function undoHistory(history: WorkflowHistory): {
  history: WorkflowHistory;
  restored: WorkflowDocSnapshot;
} | null {
  if (history.past.length === 0) return null;

  const previous = history.past[history.past.length - 1];
  const newPast = history.past.slice(0, -1);

  return {
    history: {
      past: newPast,
      present: previous,
      future: [history.present, ...history.future],
    },
    restored: previous,
  };
}

export function redoHistory(history: WorkflowHistory): {
  history: WorkflowHistory;
  restored: WorkflowDocSnapshot;
} | null {
  if (history.future.length === 0) return null;

  const next = history.future[0];
  const newFuture = history.future.slice(1);

  return {
    history: {
      past: [...history.past, history.present],
      present: next,
      future: newFuture,
    },
    restored: next,
  };
}
