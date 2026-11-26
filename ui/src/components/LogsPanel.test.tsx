import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, cleanup, act } from "@testing-library/react";
import { LogsPanel } from "./LogsPanel";
import * as client from "../api/client";
import type { NodeLogEvent, RunEvent } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LogsPanel component (Task 6.4)", () => {
  let sseCallback: ((event: RunEvent) => void) | null = null;

  beforeEach(() => {
    vi.spyOn(client, "fetchNodeLogs").mockImplementation(
      async (_runId, _nodeId, _offset, stream = "stdout") => {
        if (stream === "stderr") {
          return { lines: [], offset: 0 };
        }
        return {
          lines: [
            "Starting node attempt 1...",
            "\x1b[32mBuild environment ready\x1b[0m",
            "Executing command: echo hello",
          ],
          offset: 120,
        };
      },
    );

    vi.spyOn(client, "subscribeRunEvents").mockImplementation((_runId, cb) => {
      sseCallback = cb;
      return () => {
        sseCallback = null;
      };
    });
  });

  it("fetches history from REST and parses ANSI colors", async () => {
    render(<LogsPanel runId="run-100" nodeId="echo_node" />);

    expect(screen.getByText("Loading log output...")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("Starting node attempt 1...")).toBeDefined();
      expect(screen.getByText("Build environment ready")).toBeDefined();
      expect(screen.getByText("Executing command: echo hello")).toBeDefined();
    });

    // Check ANSI color class applied
    const coloredSpan = screen.getByText("Build environment ready");
    expect(coloredSpan.className).toContain("text-emerald-400");
  });

  it("appends live log lines from SSE stream", async () => {
    render(<LogsPanel runId="run-100" nodeId="echo_node" />);

    await waitFor(() => {
      expect(screen.getByText("Starting node attempt 1...")).toBeDefined();
    });

    // Simulate incoming SSE event
    act(() => {
      if (sseCallback) {
        const event: NodeLogEvent = {
          type: "node_log",
          ts: Date.now(),
          data: {
            run_id: "run-100",
            node_id: "echo_node",
            stream: "stdout",
            offset: 200,
            lines: ["Live stream line 1", "Live stream line 2"],
          },
        };
        sseCallback(event);
      }
    });

    await waitFor(() => {
      expect(screen.getByText("Live stream line 1")).toBeDefined();
      expect(screen.getByText("Live stream line 2")).toBeDefined();
    });
  });

  it("filters log lines with query input", async () => {
    render(<LogsPanel runId="run-100" nodeId="echo_node" />);

    await waitFor(() => {
      expect(screen.getByText("Starting node attempt 1...")).toBeDefined();
    });

    const filterInput = screen.getByPlaceholderText("Filter logs...");
    fireEvent.change(filterInput, { target: { value: "Executing" } });

    expect(screen.getByText("Executing command: echo hello")).toBeDefined();
    expect(screen.queryByText("Starting node attempt 1...")).toBeNull();

    // Verify original line number (3) is preserved instead of reset to 1
    const lineNumSpan = screen.getByText("3");
    expect(lineNumSpan).toBeDefined();
    expect(screen.queryByText("1")).toBeNull();
  });

  it("fetches both stdout and stderr history via REST", async () => {
    vi.spyOn(client, "fetchNodeLogs").mockImplementation(
      async (_runId, _nodeId, _offset, stream = "stdout") => {
        if (stream === "stderr") {
          return { lines: ["Error line from stderr"], offset: 50 };
        }
        return {
          lines: ["Standard output line"],
          offset: 100,
        };
      },
    );

    render(<LogsPanel runId="run-100" nodeId="echo_node" />);

    await waitFor(() => {
      expect(screen.getByText("Standard output line")).toBeDefined();
      expect(screen.getByText("Error line from stderr")).toBeDefined();
    });
  });

  it("subscribes to SSE stream without logOffset option to avoid duplicate connection bug", async () => {
    const subscribeSpy = vi.spyOn(client, "subscribeRunEvents");
    render(<LogsPanel runId="run-100" nodeId="echo_node" />);

    await waitFor(() => {
      expect(screen.getByText("Starting node attempt 1...")).toBeDefined();
    });

    expect(subscribeSpy).toHaveBeenCalledWith("run-100", expect.any(Function));
    // Verify no options object with logOffset was passed
    const lastCall = subscribeSpy.mock.calls[0];
    expect(lastCall[3]).toBeUndefined();
  });

  it("triggers download of accumulated logs", async () => {
    // Mock URL.createObjectURL and URL.revokeObjectURL
    const createUrlSpy = vi.fn().mockReturnValue("blob:mock-url");
    const revokeUrlSpy = vi.fn();
    window.URL.createObjectURL = createUrlSpy;
    window.URL.revokeObjectURL = revokeUrlSpy;

    render(<LogsPanel runId="run-100" nodeId="echo_node" />);

    await waitFor(() => {
      expect(screen.getByText("Starting node attempt 1...")).toBeDefined();
    });

    const downloadBtn = screen.getByRole("button", { name: "Download" });
    fireEvent.click(downloadBtn);

    expect(createUrlSpy).toHaveBeenCalled();
    expect(revokeUrlSpy).toHaveBeenCalledWith("blob:mock-url");
  });

  it("renders Agent Turns tab with turn records from agent_turns.json (FEAT-AGT-1b)", async () => {
    vi.spyOn(client, "fetchNodeAgentTurns").mockResolvedValue({
      schema: 1,
      turns: [
        {
          turn_index: 0,
          provider: "cursor",
          model: "gpt-5",
          session_id: "chat_abc123",
          status: "needs_input",
          prompt_summary: "Compare CV against job description...",
          questions: [
            {
              id: "role",
              header: "Track",
              question: "Target track?",
              options: ["ML", "Backend"],
              multi_select: false,
              allow_freeform: false,
            },
          ],
          user_answers: { role: "ML" },
          started_at: 1000,
          finished_at: 1004.25,
        },
        {
          turn_index: 1,
          provider: "cursor",
          model: "gpt-5",
          session_id: "chat_abc123",
          status: "completed",
          prompt_summary: "Compare CV against job description...",
          outputs: { match_score: 92 },
          questions: [],
          started_at: 1010,
          finished_at: 1012.5,
        },
      ],
    });

    render(<LogsPanel runId="run-100" nodeId="agent_node" />);

    await waitFor(() => {
      expect(screen.getByTestId("logs-tab-agent_turns").textContent).toContain(
        "Agent Turns (2)",
      );
    });

    fireEvent.click(screen.getByTestId("logs-tab-agent_turns"));

    expect(screen.getByTestId("agent-turn-card-0")).toBeDefined();
    expect(screen.getByTestId("agent-turn-status-0").textContent).toBe(
      "needs_input",
    );
    expect(screen.getByText("Target track?")).toBeDefined();
    expect(screen.getByText("Answer: ML")).toBeDefined();
    expect(screen.getByTestId("agent-turn-card-1")).toBeDefined();
    expect(screen.getByTestId("agent-turn-status-1").textContent).toBe(
      "completed",
    );
  });
});
