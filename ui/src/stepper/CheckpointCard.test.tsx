import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { CheckpointCard } from "./CheckpointCard";
import * as client from "../api/client";
import type { CheckpointState } from "../api/types.gen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const singleCheckpoint: CheckpointState = {
  node_id: "pick",
  checkpoint_id: "cp_0",
  question: "Choose between foo or woo:",
  options: ["foo", "woo"],
  allow_freeform: true,
  questions: [],
  answer: null,
  created_at: 1700000000,
  answered_at: null,
};

const batchCheckpoint: CheckpointState = {
  node_id: "interview",
  checkpoint_id: "cp_0",
  question: "Target track? | Skills? | Note?",
  options: null,
  allow_freeform: false,
  questions: [
    {
      id: "role",
      header: "Track",
      question: "Target track?",
      options: ["ML", "Backend"],
      multi_select: false,
      allow_freeform: false,
    },
    {
      id: "skills",
      header: "",
      question: "Skills?",
      options: ["python", "sql"],
      multi_select: true,
      allow_freeform: true,
    },
    {
      id: "note",
      header: "",
      question: "Note?",
      options: [],
      multi_select: false,
      allow_freeform: true,
    },
  ],
  answer: null,
  created_at: 1700000000,
  answered_at: null,
};

describe("CheckpointCard component", () => {
  beforeEach(() => {
    vi.spyOn(client, "answerCheckpoint").mockResolvedValue(undefined);
  });

  it("renders a legacy single question as radios plus Other input", () => {
    render(<CheckpointCard runId="run-1" checkpoint={singleCheckpoint} />);

    expect(screen.getByText("Choose between foo or woo:")).toBeDefined();
    expect(screen.getByRole("radio", { name: "foo" })).toBeDefined();
    expect(screen.getByRole("radio", { name: "woo" })).toBeDefined();
    expect(screen.getByPlaceholderText("Other...")).toBeDefined();
    const submit = screen.getByRole("button", { name: "Submit Answers" });
    expect((submit as HTMLButtonElement).disabled).toBe(true);
  });

  it("submits a single-question radio choice as a plain string", async () => {
    const onAnswered = vi.fn();
    render(
      <CheckpointCard
        runId="run-1"
        checkpoint={singleCheckpoint}
        onAnswered={onAnswered}
      />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "foo" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit Answers" }));

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

  it("submits freeform text for a single question", async () => {
    render(<CheckpointCard runId="run-1" checkpoint={singleCheckpoint} />);

    fireEvent.change(screen.getByPlaceholderText("Other..."), {
      target: { value: "bar" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit Answers" }));

    await waitFor(() => {
      expect(client.answerCheckpoint).toHaveBeenCalledWith(
        "run-1",
        "pick",
        "cp_0",
        "bar",
      );
    });
  });

  it("renders all batch questions in one card with one submit button", () => {
    render(<CheckpointCard runId="run-1" checkpoint={batchCheckpoint} />);

    expect(screen.getByText("Track")).toBeDefined();
    expect(screen.getByText("Target track?")).toBeDefined();
    expect(screen.getByRole("radio", { name: "ML" })).toBeDefined();
    expect(screen.getByRole("checkbox", { name: "python" })).toBeDefined();
    expect(screen.getByLabelText("Answer for note")).toBeDefined();
    expect(screen.getAllByRole("button", { name: "Submit Answers" })).toHaveLength(1);
  });

  it("keeps submit disabled until every question is answered, then posts an answer map", async () => {
    const onAnswered = vi.fn();
    render(
      <CheckpointCard
        runId="run-1"
        checkpoint={batchCheckpoint}
        onAnswered={onAnswered}
      />,
    );
    const submit = screen.getByRole("button", {
      name: "Submit Answers",
    }) as HTMLButtonElement;

    fireEvent.click(screen.getByRole("radio", { name: "Backend" }));
    expect(submit.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "python" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "sql" }));
    fireEvent.change(screen.getByLabelText("Other answer for skills"), {
      target: { value: "go" },
    });
    expect(submit.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Answer for note"), {
      target: { value: "hello" },
    });
    expect(submit.disabled).toBe(false);

    fireEvent.click(submit);

    const expected = {
      role: "Backend",
      skills: ["python", "sql", "go"],
      note: "hello",
    };
    await waitFor(() => {
      expect(client.answerCheckpoint).toHaveBeenCalledWith(
        "run-1",
        "interview",
        "cp_0",
        expected,
      );
      expect(onAnswered).toHaveBeenCalledWith("interview", "cp_0", expected);
    });
  });

  it("unchecking a checkbox removes it from the answer", async () => {
    render(<CheckpointCard runId="run-1" checkpoint={batchCheckpoint} />);
    fireEvent.click(screen.getByRole("radio", { name: "ML" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "python" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "sql" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "python" }));
    fireEvent.change(screen.getByLabelText("Answer for note"), {
      target: { value: "n" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit Answers" }));

    await waitFor(() => {
      expect(client.answerCheckpoint).toHaveBeenCalledWith(
        "run-1",
        "interview",
        "cp_0",
        { role: "ML", skills: ["sql"], note: "n" },
      );
    });
  });

  it("shows an error and re-enables the form when submission fails", async () => {
    vi.spyOn(client, "answerCheckpoint").mockRejectedValue(new Error("boom"));
    render(<CheckpointCard runId="run-1" checkpoint={singleCheckpoint} />);

    fireEvent.click(screen.getByRole("radio", { name: "foo" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit Answers" }));

    expect((await screen.findByRole("alert")).textContent).toContain("boom");
    expect(
      (screen.getByRole("button", { name: "Submit Answers" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("disappears (renders null) when checkpoint is answered", () => {
    const answeredCp: CheckpointState = {
      ...singleCheckpoint,
      answer: "foo",
      answered_at: 1700000010,
    };
    const { container } = render(
      <CheckpointCard runId="run-1" checkpoint={answeredCp} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
