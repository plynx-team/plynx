import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OpEntry } from "../api/types.gen";
import { OpPalette } from "./OpPalette";

afterEach(() => {
  cleanup();
});

const OPS: Array<OpEntry> = [
  {
    id: "standard_io/demo:Echo",
    pack: "standard_io",
    module: "demo",
    name: "Echo",
    kind: "class",
    title: "Echo text",
    category: "Demo",
    cacheable: true,
    description: "Echo an input string.",
    inputs: [],
    outputs: [],
    source: "demo.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/text:Concat",
    pack: "standard_io",
    module: "text",
    name: "Concat",
    kind: "class",
    title: "Concat text",
    category: "Text / Basic",
    cacheable: true,
    description: "Join two strings.",
    inputs: [],
    outputs: [],
    source: "text.py",
    valid: true,
    error: null,
  },
  {
    id: "standard_io/demo:ReadText",
    pack: "standard_io",
    module: "demo",
    name: "ReadText",
    kind: "class",
    title: "Read text file",
    category: "Files",
    cacheable: true,
    description: "Read UTF-8 text from a file.",
    inputs: [],
    outputs: [],
    source: "demo.py",
    valid: true,
    error: null,
  },
];

describe("OpPalette component (Task 6.9)", () => {
  it("groups ops by CATEGORY and calls onAddOp when an op is clicked", () => {
    const onAddOp = vi.fn();
    render(
      <OpPalette
        ops={OPS}
        stages={["ask", "print"]}
        targetStage="print"
        onTargetStageChange={vi.fn()}
        onAddOp={onAddOp}
      />,
    );

    expect(screen.getByTestId("palette-category-Demo")).toBeInTheDocument();
    expect(screen.getByTestId("palette-category-Files")).toBeInTheDocument();
    expect(
      screen.getByTestId("palette-category-Text / Basic"),
    ).toBeInTheDocument();

    // Stage dropdown is removed from the left pane
    expect(screen.queryByTestId("palette-target-stage")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("palette-op-standard_io/text:Concat"));
    expect(onAddOp).toHaveBeenCalledWith(OPS[1]);
  });

  it("filters ops via search input and focuses search on '/' and Cmd+K shortcuts", () => {
    render(
      <OpPalette
        ops={OPS}
        stages={["main"]}
        targetStage="main"
        onTargetStageChange={vi.fn()}
        onAddOp={vi.fn()}
      />,
    );

    const searchInput = screen.getByTestId("palette-search");
    expect(document.activeElement).not.toBe(searchInput);

    // '/' focuses search
    fireEvent.keyDown(window, { key: "/" });
    expect(document.activeElement).toBe(searchInput);

    searchInput.blur();
    expect(document.activeElement).not.toBe(searchInput);

    // Cmd+K focuses search
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(document.activeElement).toBe(searchInput);

    // Filter ops
    fireEvent.change(searchInput, { target: { value: "Concat" } });
    expect(
      screen.getByTestId("palette-op-standard_io/text:Concat"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("palette-op-standard_io/demo:ReadText"),
    ).not.toBeInTheDocument();
  });

  it("truncates multi-line markdown description in tooltip title to single-line summary", () => {
    const multiLineOps: Array<OpEntry> = [
      {
        id: "media_studio/audio:Synth",
        pack: "media_studio",
        module: "audio",
        name: "Synth",
        kind: "class",
        title: "Synthesizer",
        category: "Audio",
        cacheable: true,
        description: "# Synthesizer Overview\n\nLong paragraph.\n- bullet\n- bullet",
        inputs: [],
        outputs: [],
        source: "audio.py",
        valid: true,
        error: null,
      },
    ];

    render(
      <OpPalette
        ops={multiLineOps}
        onAddOp={vi.fn()}
      />,
    );

    const button = screen.getByTestId("palette-op-media_studio/audio:Synth");
    expect(button).toHaveAttribute(
      "title",
      "Synthesizer Overview (media_studio/audio:Synth)",
    );
  });
});
