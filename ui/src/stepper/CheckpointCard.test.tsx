import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { CheckpointCard } from "./CheckpointCard";
import * as client from "../api/client";
import type { CheckpointState } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockCheckpoint: CheckpointState = {
  node_id: "pick",
  checkpoint_id: "cp_0",
  question: "Choose between foo or woo:",
  options: ["foo", "woo"],
  allow_freeform: true,
  answer: null,
  created_at: 1700000000,
  answered_at: null,
};

describe("CheckpointCard component (Task 6.5)", () => {
  beforeEach(() => {
    vi.spyOn(client, "answerCheckpoint").mockResolvedValue(undefined);
  });

  it("renders question, option buttons, and freeform input", () => {
    render(<CheckpointCard runId="run-1" checkpoint={mockCheckpoint} />);

    expect(screen.getByText("Choose between foo or woo:")).toBeDefined();
    expect(screen.getByRole("button", { name: "foo" })).toBeDefined();
    expect(screen.getByRole("button", { name: "woo" })).toBeDefined();
    expect(screen.getByPlaceholderText("Type your answer...")).toBeDefined();
    expect(screen.getByRole("button", { name: "Submit Answer" })).toBeDefined();
  });

  it("submits answer when an option button is clicked", async () => {
    const onAnswered = vi.fn();
    render(
      <CheckpointCard
        runId="run-1"
        checkpoint={mockCheckpoint}
        onAnswered={onAnswered}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "foo" }));

    await waitFor(() => {
      expect(client.answerCheckpoint).toHaveBeenCalledWith(
        "run-1",
        "pick",
        "cp_0",
        "foo",
      );
      expect(onAnswered).toHaveBeenCalledWith("pick", "cp_0", "foo");
    });
  });

  it("submits freeform answer", async () => {
    const onAnswered = vi.fn();
    render(
      <CheckpointCard
        runId="run-1"
        checkpoint={mockCheckpoint}
        onAnswered={onAnswered}
      />,
    );

    const input = screen.getByPlaceholderText("Type your answer...");
    fireEvent.change(input, { target: { value: "bar" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit Answer" }));

    await waitFor(() => {
      expect(client.answerCheckpoint).toHaveBeenCalledWith(
        "run-1",
        "pick",
        "cp_0",
        "bar",
      );
      expect(onAnswered).toHaveBeenCalledWith("pick", "cp_0", "bar");
    });
  });

  it("disappears (renders null) when checkpoint is answered", () => {
    const answeredCp: CheckpointState = {
      ...mockCheckpoint,
      answer: "foo",
      answered_at: 1700000010,
    };
    const { container } = render(
      <CheckpointCard runId="run-1" checkpoint={answeredCp} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
