import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import {
  FeatherIcon,
  getPortIconColor,
  getPortIconName,
} from "./FeatherIcon";

describe("FeatherIcon component", () => {
  it("renders inline svg from feather-icons", () => {
    const { container } = render(<FeatherIcon name="play" size={18} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("18");
    expect(svg?.innerHTML).toContain("polygon");
  });

  it("falls back to circle icon for unknown icon names", () => {
    const { container } = render(<FeatherIcon name="non-existent-icon" />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.innerHTML).toContain("circle");
  });

  it("maps port types and media types to feather icon names and colors", () => {
    expect(getPortIconName("str")).toBe("type");
    expect(getPortIconName("int")).toBe("hash");
    expect(getPortIconName("file", "image/png")).toBe("image");
    expect(getPortIconName("file", "audio/midi")).toBe("sliders");
    expect(getPortIconName("file", "audio/wav")).toBe("music");
    expect(getPortIconName("directory")).toBe("folder");
    expect(getPortIconColor("file")).toBe("#2680eb");
  });
});
