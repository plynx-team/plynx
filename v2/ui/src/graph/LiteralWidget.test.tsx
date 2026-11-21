import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { InputPortSpec } from "../api/types.gen";
import { LiteralWidget } from "./LiteralWidget";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LiteralWidget component (Task 3.1)", () => {
  it("renders preset suggestions and allows one-click filling for options parameter", () => {
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

    // Preset buttons are rendered
    const presetBtn = screen.getByTestId("inspector-input-chord_progression-preset-ii - V - I");
    expect(presetBtn).toBeInTheDocument();
    fireEvent.click(presetBtn);

    expect(onChange).toHaveBeenCalledWith("ii - V - I");
  });

  it("toggles to custom value input and allows typing custom values", () => {
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
      default: "I - V - vi - IV",
    };

    render(
      <LiteralWidget
        port={port}
        value="I - V - vi - IV"
        onChange={onChange}
      />,
    );

    // Toggle to custom value
    const toggleBtn = screen.getByTestId("inspector-input-chord_progression-custom-toggle");
    expect(toggleBtn).toHaveTextContent("Custom value");
    fireEvent.click(toggleBtn);

    // Input is now a text field
    const input = screen.getByTestId("inspector-input-chord_progression");
    expect(input.tagName).toBe("INPUT");
    fireEvent.change(input, { target: { value: "vi - IV - I - V" } });

    expect(onChange).toHaveBeenCalledWith("vi - IV - I - V");
  });

  it("auto-enables custom mode when value is not in options", () => {
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

    // Should render as an input, not a select
    const input = screen.getByTestId("inspector-input-chord_progression");
    expect(input.tagName).toBe("INPUT");
    expect(input).toHaveValue("vi - IV - I - V");
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

    expect(screen.getByTestId("inspector-input-config-list-container")).toBeInTheDocument();
  });
});
