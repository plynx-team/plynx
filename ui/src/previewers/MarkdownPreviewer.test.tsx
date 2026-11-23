import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownPreviewer } from "./MarkdownPreviewer";

describe("MarkdownPreviewer link URL sanitization", () => {
  it("renders safe http, https, and mailto links as anchors", () => {
    const content = `
[HTTP Link](http://example.com)
[HTTPS Link](https://example.com/docs?query=test)
[Mailto Link](mailto:user@example.com)
`;
    render(<MarkdownPreviewer content={content} />);

    const httpAnchor = screen.getByRole("link", { name: "HTTP Link" });
    expect(httpAnchor.getAttribute("href")).toBe("http://example.com");

    const httpsAnchor = screen.getByRole("link", { name: "HTTPS Link" });
    expect(httpsAnchor.getAttribute("href")).toBe("https://example.com/docs?query=test");

    const mailtoAnchor = screen.getByRole("link", { name: "Mailto Link" });
    expect(mailtoAnchor.getAttribute("href")).toBe("mailto:user@example.com");
  });

  it("sanitizes dangerous link protocols like javascript and data", () => {
    const content = `
[Dangerous JS](javascript:alert(1))
[Data URI](data:text/html,<script>alert(1)</script>)
[VBScript](vbscript:msgbox(1))
`;
    render(<MarkdownPreviewer content={content} />);

    // Should NOT be rendered as links
    expect(screen.queryByRole("link", { name: "Dangerous JS" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Data URI" })).toBeNull();
    expect(screen.queryByRole("link", { name: "VBScript" })).toBeNull();

    // Rendered as plain text spans
    expect(screen.getByText("Dangerous JS")).toBeDefined();
    expect(screen.getByText("Data URI")).toBeDefined();
    expect(screen.getByText("VBScript")).toBeDefined();
  });
});
