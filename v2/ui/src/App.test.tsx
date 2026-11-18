import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup, act } from "@testing-library/react";
import { App } from "./App";
import * as client from "./api/client";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App component shell", () => {
  beforeEach(() => {
    vi.spyOn(client, "fetchRuns").mockResolvedValue({ runs: [] });
    vi.spyOn(client, "fetchWorkflows").mockResolvedValue([
      {
        path: "examples/workflows/foo_or_woo.yaml",
        name: "Foo or Woo Demo",
        stage_count: 2,
      },
    ]);
  });

  it("renders Navbar and default RunList view", async () => {
    window.location.hash = "";
    render(<App />);

    expect(screen.getByText("PLynx")).toBeDefined();
    expect(screen.getAllByText("Runs").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Workflows").length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(screen.getByText("No runs found")).toBeDefined();
    });
  });

  it("switches to Workflows view on hash change", async () => {
    window.location.hash = "#/workflows";
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Foo or Woo Demo")).toBeDefined();
    });
  });

  it("switches to RunDetail view when visiting a run URL", async () => {
    vi.spyOn(client, "fetchRunState").mockResolvedValue({
      id: "run-target-999",
      workflow_path: "examples/workflows/foo_or_woo.yaml",
      workflow_sha256: "hash123",
      status: "RUNNING",
      run_inputs: {},
      cancel_requested: false,
      pinned: false,
      created_at: 1700000000,
      nodes: {
        n1: {
          node_id: "n1",
          status: "RUNNING",
          cache_hit: false,
          attempt: 1,
        },
      },
      checkpoints: [],
      stage_gates: {},
    });
    vi.spyOn(client, "subscribeRunEvents").mockReturnValue(() => {});

    act(() => {
      window.location.hash = "#/runs/run-target-999";
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText("run-target-999").length).toBeGreaterThan(0);
      expect(screen.getByText("n1")).toBeDefined();
    });
  });
});
