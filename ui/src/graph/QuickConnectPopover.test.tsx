import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OpEntry } from "../api/types.gen";
import {
  QuickConnectPopover,
  type QuickConnectDropData,
} from "./QuickConnectPopover";

afterEach(() => {
  cleanup();
});

const MOCK_OPS: Array<OpEntry> = [
  {
    id: "standard_io/text:Echo",
    pack: "standard_io",
    module: "text",
    name: "Echo",
    kind: "class",
    title: "Echo Text",
    category: "Text",
    valid: true,
    error: null,
    cacheable: true,
    description: "",
    source: "",
    inputs: [
      { name: "text", type: "str", required: true, default: null, media: null },
    ],
    outputs: [{ name: "res", type: "str", media: null }],
    allow_extra_inputs: false,
  },
  {
    id: "standard_io/math:Add",
    pack: "standard_io",
    module: "math",
    name: "Add",
    kind: "class",
    title: "Add Numbers",
    category: "Math",
    valid: true,
    error: null,
    cacheable: true,
    description: "",
    source: "",
    inputs: [
      { name: "a", type: "int", required: true, default: null, media: null },
      { name: "b", type: "int", required: true, default: null, media: null },
    ],
    outputs: [{ name: "sum", type: "int", media: null }],
    allow_extra_inputs: false,
  },
  {
    id: "standard_io/text:Concat",
    pack: "standard_io",
    module: "text",
    name: "Concat",
    kind: "class",
    title: "Concat Strings",
    category: "Text",
    valid: true,
    error: null,
    cacheable: true,
    description: "",
    source: "",
    inputs: [
      { name: "first", type: "str", required: true, default: null, media: null },
      { name: "second", type: "str", required: true, default: null, media: null },
    ],
    outputs: [{ name: "combined", type: "str", media: null }],
    allow_extra_inputs: false,
  },
];

describe("QuickConnectPopover component", () => {
  it("filters compatible operations when dragged from output (source)", () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();

    const data: QuickConnectDropData = {
      originNodeId: "node_1",
      originNodeTitle: "Source Node",
      originPortName: "choice",
      handleType: "source",
      originPort: { name: "choice", type: "str" },
      screenPos: { x: 100, y: 150 },
      flowPos: { x: 200, y: 300 },
      stageId: "main",
    };

    render(
      <QuickConnectPopover
        data={data}
        ops={MOCK_OPS}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );

    expect(screen.getByTestId("quick-connect-popover")).toBeDefined();
    // Echo (text) and Concat (first, second) should be present
    expect(screen.getByText("Echo Text")).toBeDefined();
    expect(screen.getAllByText("Concat Strings")).toHaveLength(2);
    // Math Add should NOT be present (type int vs str)
    expect(screen.queryByText("Add Numbers")).toBeNull();

    // Click Concat -> second
    const secondPortItem = screen.getByTestId(
      "quick-connect-item-standard_io/text:Concat-second",
    );
    fireEvent.click(secondPortItem);

    expect(onSelect).toHaveBeenCalledWith(
      "standard_io/text:Concat",
      "second",
    );
  });

  it("filters compatible operations when dragged from input (target)", () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();

    const data: QuickConnectDropData = {
      originNodeId: "node_2",
      originNodeTitle: "Target Node",
      originPortName: "num",
      handleType: "target",
      originPort: { name: "num", type: "int" },
      screenPos: { x: 100, y: 150 },
      flowPos: { x: 200, y: 300 },
      stageId: "math_stage",
    };

    render(
      <QuickConnectPopover
        data={data}
        ops={MOCK_OPS}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );

    // Math Add has output 'sum: int'
    expect(screen.getByText("Add Numbers")).toBeDefined();
    expect(screen.queryByText("Echo Text")).toBeNull();

    const sumPortItem = screen.getByTestId(
      "quick-connect-item-standard_io/math:Add-sum",
    );
    fireEvent.click(sumPortItem);

    expect(onSelect).toHaveBeenCalledWith("standard_io/math:Add", "sum");
  });

  it("filters list by search input query", () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();

    const data: QuickConnectDropData = {
      originNodeId: "node_1",
      originPortName: "choice",
      handleType: "source",
      originPort: { name: "choice", type: "str" },
      screenPos: { x: 100, y: 150 },
      flowPos: { x: 200, y: 300 },
      stageId: "main",
    };

    render(
      <QuickConnectPopover
        data={data}
        ops={MOCK_OPS}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );

    const searchInput = screen.getByTestId("input-quick-connect-search");
    fireEvent.change(searchInput, { target: { value: "Concat" } });

    expect(screen.queryByText("Echo Text")).toBeNull();
    expect(screen.getAllByText("Concat Strings")).toHaveLength(2);
  });

  it("navigates and selects via keyboard (Enter and Escape)", () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();

    const data: QuickConnectDropData = {
      originNodeId: "node_1",
      originPortName: "choice",
      handleType: "source",
      originPort: { name: "choice", type: "str" },
      screenPos: { x: 100, y: 150 },
      flowPos: { x: 200, y: 300 },
      stageId: "main",
    };

    render(
      <QuickConnectPopover
        data={data}
        ops={MOCK_OPS}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );

    // Press Enter to select the first highlighted item (Echo -> text)
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("standard_io/text:Echo", "text");

    // Press Escape to close
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
