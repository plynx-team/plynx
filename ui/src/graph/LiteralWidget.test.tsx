import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { InputPortSpec } from "../api/types.gen";
import { LiteralWidget } from "./LiteralWidget";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LiteralWidget / PortInput component", () => {
  it("renders strict Literal dropdown with presets and no Custom value option", () => {
    const onChange = vi.fn();
    const port: InputPortSpec = {
      name: "chord_progression",
      type: "str",
      media: null,
      options: ["I - V - vi - IV", "ii - V - I", "I - IV - V - I"],
      min: null,
      max: null,
      step: null,
      required: false,
      default: "I - V - vi - IV",
    };

    render(
      <LiteralWidget
        port={port}
        value={undefined}
        onChange={onChange}
      />,
    );

    // Dropdown renders strict options without "Custom value..."
    const select = screen.getByTestId("inspector-input-chord_progression");
    expect(select.tagName).toBe("SELECT");
    expect(screen.queryByText("Custom value...")).toBeNull();
    expect(
      screen.queryByTestId("inspector-input-chord_progression-custom-toggle"),
    ).toBeNull();

    // Preset buttons are rendered and clickable
    const presetBtn = screen.getByTestId(
      "inspector-input-chord_progression-preset-ii - V - I",
    );
    expect(presetBtn).toBeInTheDocument();
    fireEvent.click(presetBtn);

    expect(onChange).toHaveBeenCalledWith("ii - V - I");
  });

  it("preserves legacy out-of-range option as disabled fallback while keeping select strict", () => {
    const onChange = vi.fn();
    const port: InputPortSpec = {
      name: "chord_progression",
      type: "str",
      media: null,
      options: ["I - V - vi - IV", "ii - V - I"],
      min: null,
      max: null,
      step: null,
      required: false,
      default: null,
    };

    render(
      <LiteralWidget
        port={port}
        value="vi - IV - I - V"
        onChange={onChange}
      />,
    );

    const select = screen.getByTestId("inspector-input-chord_progression");
    expect(select.tagName).toBe("SELECT");
    expect(screen.getByText("vi - IV - I - V (invalid)")).toBeInTheDocument();
  });

  it("renders structured string-list editor for JSON arrays and supports add/edit/remove", () => {
    const onChange = vi.fn();
    const port: InputPortSpec = {
      name: "tags",
      type: "json",
      media: null,
      options: null,
      min: null,
      max: null,
      step: null,
      required: false,
      default: [],
    };

    render(
      <LiteralWidget
        port={port}
        value={["synthwave", "retrowave"]}
        onChange={onChange}
      />,
    );

    // Container should show items
    expect(screen.getByText("List items (2)")).toBeInTheDocument();
    const item0 = screen.getByTestId("inspector-input-tags-list-item-0");
    const item1 = screen.getByTestId("inspector-input-tags-list-item-1");
    expect(item0).toHaveValue("synthwave");
    expect(item1).toHaveValue("retrowave");

    // Edit item
    fireEvent.change(item0, { target: { value: "darksynth" } });
    expect(onChange).toHaveBeenCalledWith(["darksynth", "retrowave"]);

    // Add item
    const addBtn = screen.getByTestId("inspector-input-tags-list-add");
    fireEvent.click(addBtn);
    expect(onChange).toHaveBeenCalledWith(["synthwave", "retrowave", ""]);

    // Remove item
    const removeBtn = screen.getByTestId("inspector-input-tags-list-remove-1");
    fireEvent.click(removeBtn);
    expect(onChange).toHaveBeenCalledWith(["synthwave"]);

    // Toggle to raw JSON mode
    const modeToggle = screen.getByTestId("inspector-input-tags-json-mode-toggle");
    expect(modeToggle).toHaveTextContent("Raw JSON");
    fireEvent.click(modeToggle);

    // Now renders raw textarea
    const textarea = screen.getByTestId("inspector-input-tags");
    expect(textarea.tagName).toBe("TEXTAREA");
  });

  it("allows switching from raw JSON to list editor mode", () => {
    const onChange = vi.fn();
    const port: InputPortSpec = {
      name: "config",
      type: "json",
      media: null,
      options: null,
      min: null,
      max: null,
      step: null,
      required: false,
      default: null,
    };

    render(
      <LiteralWidget
        port={port}
        value={undefined}
        onChange={onChange}
      />,
    );

    const modeToggle = screen.getByTestId("inspector-input-config-json-mode-toggle");
    expect(modeToggle).toHaveTextContent("List editor");
    fireEvent.click(modeToggle);

    expect(
      screen.getByTestId("inspector-input-config-list-container"),
    ).toBeInTheDocument();
  });

  it("renders HTML datalist suggestions on str model port while keeping freeform input (FEAT-AGT-1b)", () => {
    const onChange = vi.fn();
    const port: InputPortSpec = {
      name: "model",
      type: "str",
      media: null,
      options: null,
      suggestions: ["claude-sonnet-4-5", "gpt-5", "gemini-2.5-pro"],
      min: null,
      max: null,
      step: null,
      required: false,
      default: "",
    };

    render(<LiteralWidget port={port} value="" onChange={onChange} />);

    const input = screen.getByTestId("inspector-input-model");
    expect(input.tagName).toBe("INPUT");
    expect(input).toHaveAttribute("list", "inspector-input-model-datalist");

    const datalist = screen.getByTestId("inspector-input-model-datalist");
    expect(datalist.tagName).toBe("DATALIST");
    expect(datalist.querySelectorAll("option")).toHaveLength(3);

    fireEvent.change(input, { target: { value: "ollama/qwen2.5-coder:32b" } });
    expect(onChange).toHaveBeenCalledWith("ollama/qwen2.5-coder:32b");
  });
});
