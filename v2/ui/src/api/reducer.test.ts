import { describe, expect, it } from "vitest";
import {
  applyRunEvent,
  createInitialRunState,
  reduceRunEvents,
} from "./reducer";
import type { RunEvent } from "./types.gen";

const RECORDED_FOO_OR_WOO_EVENTS: ReadonlyArray<RunEvent> = [
  {
    seq: 1,
    ts: 1731800000.0,
    type: "run_status",
    data: { run_id: "20261116_201500_a1b2c3", status: "RUNNING" },
  },
  {
    seq: 2,
    ts: 1731800000.1,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      status: "PENDING",
      cache_hit: false,
      attempt: 0,
    },
  },
  {
    seq: 3,
    ts: 1731800000.1,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "echo",
      status: "PENDING",
      cache_hit: false,
      attempt: 0,
    },
  },
  {
    seq: 4,
    ts: 1731800000.2,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      status: "RUNNING",
      cache_hit: false,
      attempt: 1,
    },
  },
  {
    seq: 5,
    ts: 1731800000.3,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      status: "WAITING_FOR_USER",
      cache_hit: false,
      attempt: 1,
      exit_code: 10,
    },
  },
  {
    seq: 6,
    ts: 1731800000.3,
    type: "node_checkpoint",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      checkpoint_id: "cp_0",
      question: "foo or woo?",
      options: ["foo", "woo"],
      allow_freeform: false,
    },
  },
  {
    seq: 7,
    ts: 1731800000.4,
    type: "checkpoint_resolved",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      checkpoint_id: "cp_0",
    },
  },
  {
    seq: 8,
    ts: 1731800000.5,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      status: "RUNNING",
      cache_hit: false,
      attempt: 2,
    },
  },
  {
    seq: 9,
    ts: 1731800000.6,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "pick",
      status: "SUCCESS",
      cache_hit: false,
      attempt: 2,
      exit_code: 0,
    },
  },
  {
    seq: 10,
    ts: 1731800000.7,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "echo",
      status: "RUNNING",
      cache_hit: false,
      attempt: 1,
    },
  },
  {
    seq: 11,
    ts: 1731800000.8,
    type: "node_status",
    data: {
      run_id: "20261116_201500_a1b2c3",
      node_id: "echo",
      status: "SUCCESS",
      cache_hit: false,
      attempt: 1,
      exit_code: 0,
    },
  },
  {
    seq: 12,
    ts: 1731800000.9,
    type: "run_status",
    data: { run_id: "20261116_201500_a1b2c3", status: "SUCCESS" },
  },
];

describe("applyRunEvent reducer", () => {
  it("reduces recorded foo_or_woo events into the final RunState", () => {
    const initial = createInitialRunState(
      "20261116_201500_a1b2c3",
      "workflows/foo_or_woo.yaml",
    );

    const pausedState = reduceRunEvents(
      initial,
      RECORDED_FOO_OR_WOO_EVENTS.slice(0, 6),
    );
    expect(pausedState.nodes.pick.status).toBe("WAITING_FOR_USER");
    expect(pausedState.nodes.echo.status).toBe("PENDING");
    expect(pausedState.checkpoints).toHaveLength(1);
    expect(pausedState.checkpoints[0].question).toBe("foo or woo?");
    expect(pausedState.checkpoints[0].answered_at).toBeNull();

    const finalState = reduceRunEvents(initial, RECORDED_FOO_OR_WOO_EVENTS);
    expect(finalState.status).toBe("SUCCESS");
    expect(finalState.nodes.pick.status).toBe("SUCCESS");
    expect(finalState.nodes.pick.attempt).toBe(2);
    expect(finalState.nodes.echo.status).toBe("SUCCESS");
    expect(finalState.nodes.echo.attempt).toBe(1);
    expect(finalState.checkpoints[0].answered_at).toBe(1731800000.4);
  });

  it("handles stage_approval and stage_resolved events", () => {
    let state = createInitialRunState("r1");
    state = applyRunEvent(state, {
      seq: 1,
      ts: 10,
      type: "stage_approval",
      data: { run_id: "r1", stage_id: "ask", title: "1. Ask" },
    });
    expect(state.stage_gates.ask.status).toBe("WAITING");

    state = applyRunEvent(state, {
      seq: 2,
      ts: 20,
      type: "stage_resolved",
      data: { run_id: "r1", stage_id: "ask" },
    });
    expect(state.stage_gates.ask.status).toBe("APPROVED");
    expect(state.stage_gates.ask.decided_at).toBe(20);
  });
});
