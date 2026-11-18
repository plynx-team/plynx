import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { StageApprovalCard } from "./StageApprovalCard";
import * as client from "../api/client";
import type { StageGateState } from "../api/types.gen";

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
});
