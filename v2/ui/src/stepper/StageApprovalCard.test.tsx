import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { StageApprovalCard } from "./StageApprovalCard";
import * as client from "../api/client";
import type { OpEntry, StageGateState } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockWaitingGate: StageGateState = {
  stage_id: "s1_ingest",
  status: "WAITING",
  created_at: 1700000000,
};

describe("StageApprovalCard component (Task 6.6)", () => {
  beforeEach(() => {
    vi.spyOn(client, "approveStage").mockResolvedValue(undefined);
  });

  it("renders stage title, info, and Approve & Continue button", () => {
    render(
      <StageApprovalCard
        runId="run-777"
        stageId="s1_ingest"
        stageTitle="1. Ingest"
        gateState={mockWaitingGate}
      />,
    );

    expect(screen.getByText("Stage Gate: Approval Required")).toBeDefined();
    expect(screen.getByText(/1. Ingest/)).toBeDefined();
    expect(
      screen.getByRole("button", { name: "Approve & Continue" }),
    ).toBeDefined();
  });

  it("submits approval when Approve & Continue button is clicked", async () => {
    const onApproved = vi.fn();
    render(
      <StageApprovalCard
        runId="run-777"
        stageId="s1_ingest"
        stageTitle="1. Ingest"
        gateState={mockWaitingGate}
        onApproved={onApproved}
      />,
    );

    const btn = screen.getByRole("button", { name: "Approve & Continue" });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(client.approveStage).toHaveBeenCalledWith("run-777", "s1_ingest");
      expect(onApproved).toHaveBeenCalledWith("s1_ingest");
    });
  });

  it("disappears (renders null) when gate is already APPROVED", () => {
    const approvedGate: StageGateState = {
      ...mockWaitingGate,
      status: "APPROVED",
      decided_at: 1700000010,
    };

    const { container } = render(
      <StageApprovalCard
        runId="run-777"
        stageId="s1_ingest"
        gateState={approvedGate}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("displays error banner if approveStage fails", async () => {
    vi.spyOn(client, "approveStage").mockRejectedValue(
      new Error("Gate already decided"),
    );

    render(
      <StageApprovalCard
        runId="run-777"
        stageId="s1_ingest"
        gateState={mockWaitingGate}
      />,
    );

    const btn = screen.getByRole("button", { name: "Approve & Continue" });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "Gate already decided",
      );
    });
  });

  it("renders stage inputs form when missing required inputs exist and submits them", async () => {
    const mockWorkflow = {
      version: 1 as const,
      stages: {
        stage2: { title: "2. Transform" },
      },
      nodes: {
        processor: {
          op: "standard_io/demo:Echo",
          stage: "stage2",
        },
      },
    };

    const mockOpsMap = {
      "standard_io/demo:Echo": {
        id: "standard_io/demo:Echo",
        title: "Echo",
        pack: "standard_io",
        valid: true,
        inputs: [
          {
            name: "text",
            type: "str" as const,
            required: true,
            default: null,
          },
        ],
        outputs: [],
      },
    };

    const onApproved = vi.fn();

    render(
      <StageApprovalCard
        runId="run-999"
        stageId="stage2"
        stageTitle="2. Transform"
        gateState={{ stage_id: "stage2", status: "WAITING", created_at: 100 }}
        workflow={mockWorkflow}
        runInputs={{}}
        opsMap={mockOpsMap as unknown as Record<string, OpEntry>}
        onApproved={onApproved}
      />,
    );

    expect(screen.getByText("Stage Inputs: Input Required")).toBeDefined();
    expect(screen.getByText(/requires inputs before running/)).toBeDefined();

    const submitBtn = screen.getByRole("button", { name: "Submit Inputs & Continue" });

    // Clicking submit with empty required input shows validation error
    fireEvent.click(submitBtn);
    expect(screen.getByText("text is required")).toBeDefined();
    expect(client.approveStage).not.toHaveBeenCalled();

    // Fill in the input
    const inputEl = screen.getByPlaceholderText("Enter value...");
    fireEvent.change(inputEl, { target: { value: "hello world" } });

    // Submit now
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(client.approveStage).toHaveBeenCalledWith("run-999", "stage2", {
        "processor.text": "hello world",
      });
      expect(onApproved).toHaveBeenCalledWith("stage2");
    });
  });
});
