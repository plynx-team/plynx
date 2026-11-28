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
    side_effects: "none",
    description: "Echo an input string.",
    inputs: [],
    outputs: [],
    allow_extra_inputs: false,
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
    side_effects: "none",
    description: "Join two strings.",
    inputs: [],
    outputs: [],
    allow_extra_inputs: false,
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
    side_effects: "none",
    description: "Read UTF-8 text from a file.",
    inputs: [],
    outputs: [],
    allow_extra_inputs: false,
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
        side_effects: "none",
        description: "# Synthesizer Overview\n\nLong paragraph.\n- bullet\n- bullet",
        inputs: [],
        outputs: [],
        allow_extra_inputs: false,
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

  it("renders a write warning badge on operations with side_effects === 'write'", () => {
    const opsWithWrite: Array<OpEntry> = [
      ...OPS,
      {
        id: "standard_io/http:HttpPostJson",
        pack: "standard_io",
        module: "http",
        name: "HttpPostJson",
        kind: "class",
        title: "HTTP POST JSON",
        category: "Core / Network",
        cacheable: false,
        side_effects: "write",
        description: "Send a JSON payload over HTTP POST.",
        inputs: [],
        outputs: [],
        allow_extra_inputs: false,
        source: "http.py",
        valid: true,
        error: null,
      },
    ];

    render(<OpPalette ops={opsWithWrite} onAddOp={vi.fn()} />);

    expect(
      screen.getByTestId("palette-op-write-standard_io/http:HttpPostJson"),
    ).toHaveTextContent("write");
    expect(
      screen.queryByTestId("palette-op-write-standard_io/demo:Echo"),
    ).not.toBeInTheDocument();
  });
});
