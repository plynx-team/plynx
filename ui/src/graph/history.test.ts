import { describe, expect, it } from "vitest";
import type { Workflow, WorkflowLayout } from "../api/types.gen";
import {
  createHistory,
  pushHistory,
  redoHistory,
  undoHistory,
  type WorkflowDocSnapshot,
} from "./history";

const SAMPLE_WF_1: Workflow = {
  version: 1,
  name: "demo",
  stages: { main: { title: "Main" } },
  nodes: {
    a: { op: "test:OpA", stage: "main", inputs: {} },
  },
};

const SAMPLE_LAYOUT_1: WorkflowLayout = {
  schema: 1,
  nodes: { a: { x: 10, y: 20 } },
  viewport: { x: 0, y: 0, zoom: 1 },
};

const SAMPLE_WF_2: Workflow = {
  ...SAMPLE_WF_1,
  nodes: {
    ...SAMPLE_WF_1.nodes,
    b: { op: "test:OpB", stage: "main", inputs: {} },
  },
};

const SAMPLE_LAYOUT_2: WorkflowLayout = {
  schema: 1,
  nodes: { a: { x: 10, y: 20 }, b: { x: 100, y: 200 } },
  viewport: { x: 0, y: 0, zoom: 1 },
};

describe("Workflow History (Undo/Redo)", () => {
  it("initializes history with present state and empty past/future", () => {
    const initial: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };
    const history = createHistory(initial);

    expect(history.present).toBe(initial);
    expect(history.past).toHaveLength(0);
    expect(history.future).toHaveLength(0);
  });

  it("pushes a new state to history and clears future", () => {
    const s1: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };
    const s2: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_2,
      layout: SAMPLE_LAYOUT_2,
    };

    let history = createHistory(s1);
    history = pushHistory(history, s2);

    expect(history.past).toHaveLength(1);
    expect(history.past[0]).toBe(s1);
    expect(history.present).toBe(s2);
    expect(history.future).toHaveLength(0);
  });

  it("skips pushing identical state", () => {
    const s1: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };
    const s1Clone: WorkflowDocSnapshot = {
      workflow: { ...SAMPLE_WF_1 },
      layout: { ...SAMPLE_LAYOUT_1 },
    };

    let history = createHistory(s1);
    history = pushHistory(history, s1Clone);

    expect(history.past).toHaveLength(0);
    expect(history.present).toBe(s1);
  });

  it("coalesces rapid text edits within coalesce window", () => {
    const s1: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };
    const s2: WorkflowDocSnapshot = {
      workflow: { ...SAMPLE_WF_1, name: "demo2" },
      layout: SAMPLE_LAYOUT_1,
    };
    const s3: WorkflowDocSnapshot = {
      workflow: { ...SAMPLE_WF_1, name: "demo3" },
      layout: SAMPLE_LAYOUT_1,
    };

    let history = createHistory(s1);
    const t0 = Date.now();
    // First edit: pushed
    history = pushHistory(history, s2, {
      coalesce: true,
      lastActionTime: 0,
    });
    expect(history.past).toHaveLength(1);
    expect(history.present.workflow.name).toBe("demo2");

    // Rapid second edit (within 600ms): coalesced into present
    history = pushHistory(history, s3, {
      coalesce: true,
      lastActionTime: t0,
      coalesceWindowMs: 1000,
    });
    expect(history.past).toHaveLength(1);
    expect(history.present.workflow.name).toBe("demo3");
  });

  it("performs undo and redo cleanly", () => {
    const s1: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };
    const s2: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_2,
      layout: SAMPLE_LAYOUT_2,
    };

    let history = createHistory(s1);
    history = pushHistory(history, s2);

    // Undo: should restore s1
    const undoRes = undoHistory(history);
    expect(undoRes).not.toBeNull();
    expect(undoRes?.restored).toBe(s1);
    expect(undoRes?.history.past).toHaveLength(0);
    expect(undoRes?.history.future).toHaveLength(1);
    expect(undoRes?.history.future[0]).toBe(s2);

    // Redo: should restore s2
    const redoRes = redoHistory(undoRes!.history);
    expect(redoRes).not.toBeNull();
    expect(redoRes?.restored).toBe(s2);
    expect(redoRes?.history.past).toHaveLength(1);
    expect(redoRes?.history.past[0]).toBe(s1);
    expect(redoRes?.history.future).toHaveLength(0);
  });

  it("returns null when trying to undo at start or redo at end", () => {
    const s1: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };
    const history = createHistory(s1);

    expect(undoHistory(history)).toBeNull();
    expect(redoHistory(history)).toBeNull();
  });

  it("respects history stack depth limit", () => {
    const s1: WorkflowDocSnapshot = {
      workflow: SAMPLE_WF_1,
      layout: SAMPLE_LAYOUT_1,
    };

    let history = createHistory(s1);
    for (let i = 2; i <= 10; i++) {
      const nextWf: Workflow = { ...SAMPLE_WF_1, name: `name-${i}` };
      history = pushHistory(
        history,
        { workflow: nextWf, layout: SAMPLE_LAYOUT_1 },
        { limit: 4 },
      );
    }

    // Past should be capped at limit (4 entries)
    expect(history.past).toHaveLength(4);
    expect(history.present.workflow.name).toBe("name-10");
  });
});
