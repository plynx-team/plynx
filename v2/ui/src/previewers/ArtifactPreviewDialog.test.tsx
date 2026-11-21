import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import {
  ArtifactPreviewDialog,
  detectPreviewKind,
} from "./ArtifactPreviewDialog";
import { CsvPreviewer } from "./CsvPreviewer";
import { JsonPreviewer } from "./JsonPreviewer";
import { MarkdownPreviewer } from "./MarkdownPreviewer";
import { ImagePreviewer } from "./ImagePreviewer";
import { PdfPreviewer } from "./PdfPreviewer";
import { TextPreviewer } from "./TextPreviewer";

afterEach(() => {
  cleanup();
});

describe("detectPreviewKind", () => {
  it("detects PDF from media type and extension", () => {
    expect(detectPreviewKind("application/pdf")).toBe("pdf");
    expect(detectPreviewKind(null, "report.pdf")).toBe("pdf");
  });

  it("detects Images from media type and extension", () => {
    expect(detectPreviewKind("image/png")).toBe("image");
    expect(detectPreviewKind(null, "photo.jpg")).toBe("image");
    expect(detectPreviewKind(null, "diagram.svg")).toBe("image");
  });

  it("detects Audio from media type and extension", () => {
    expect(detectPreviewKind("audio/wav")).toBe("audio");
    expect(detectPreviewKind("audio/mpeg")).toBe("audio");
    expect(detectPreviewKind(null, "chime.wav")).toBe("audio");
    expect(detectPreviewKind(null, "song.mp3")).toBe("audio");
  });

  it("detects CSV and TSV", () => {
    expect(detectPreviewKind("text/csv")).toBe("csv");
    expect(detectPreviewKind(null, "table.csv")).toBe("csv");
    expect(detectPreviewKind(null, "table.tsv")).toBe("tsv");
  });

  it("detects JSON and Markdown", () => {
    expect(detectPreviewKind("application/json")).toBe("json");
    expect(detectPreviewKind(null, "data.json")).toBe("json");
    expect(detectPreviewKind("text/markdown")).toBe("markdown");
    expect(detectPreviewKind(null, "README.md")).toBe("markdown");
  });

  it("falls back to text", () => {
    expect(detectPreviewKind("text/plain")).toBe("text");
    expect(detectPreviewKind(null, "unknown.xyz")).toBe("text");
  });
});

describe("Individual Previewers (Task 6.7)", () => {
  it("renders CsvPreviewer as an HTML table", () => {
    const csvData = "name,age,city\nAlice,30,NYC\nBob,25,SFO";
    render(<CsvPreviewer content={csvData} />);

    expect(screen.getByText("name")).toBeDefined();
    expect(screen.getByText("age")).toBeDefined();
    expect(screen.getByText("Alice")).toBeDefined();
    expect(screen.getByText("NYC")).toBeDefined();
    expect(screen.getByText("Bob")).toBeDefined();
  });

  it("renders JsonPreviewer with formatted JSON", () => {
    const jsonStr = '{"status":"ok","count":42}';
    render(<JsonPreviewer content={jsonStr} />);

    expect(screen.getByText(/"status": "ok"/)).toBeDefined();
    expect(screen.getByText(/"count": 42/)).toBeDefined();
  });

  it("renders MarkdownPreviewer with headings, bold, inline code, and lists", () => {
    const md = "# Main Title\n\n**Bold text** with `inline code`.\n\n- Item 1\n- Item 2";
    render(<MarkdownPreviewer content={md} />);

    expect(screen.getByText("Main Title")).toBeDefined();
    expect(screen.getByText("Bold text")).toBeDefined();
    expect(screen.getByText("inline code")).toBeDefined();
    expect(screen.getByText("Item 1")).toBeDefined();
    expect(screen.getByText("Item 2")).toBeDefined();
  });

  it("renders ImagePreviewer with image element", () => {
    render(<ImagePreviewer url="/api/v1/blobs/test.png" alt="Test image" />);
    const img = screen.getByRole("img") as HTMLImageElement;
    expect(img.src).toContain("/api/v1/blobs/test.png");
    expect(img.alt).toBe("Test image");
  });

  it("renders PdfPreviewer with iframe", () => {
    render(<PdfPreviewer url="/api/v1/blobs/doc.pdf" title="Doc PDF" />);
    const iframe = screen.getByTitle("Doc PDF") as HTMLIFrameElement;
    expect(iframe.src).toContain("/api/v1/blobs/doc.pdf");
  });

  it("renders TextPreviewer with lines", () => {
    render(<TextPreviewer content={"Line 1\nLine 2"} />);
    expect(screen.getByText("Line 1")).toBeDefined();
    expect(screen.getByText("Line 2")).toBeDefined();
  });
});

describe("ArtifactPreviewDialog component (Task 6.7)", () => {
  it("renders modal with title, download link, and close button", () => {
    const onClose = vi.fn();
    render(
      <ArtifactPreviewDialog
        title="Sample JSON Output"
        url="/api/v1/runs/1/nodes/echo/outputs/res"
        filename="result.json"
        mediaType="application/json"
        initialContent='{"result":"hello world"}'
        onClose={onClose}
      />,
    );

    expect(screen.getByText("Sample JSON Output")).toBeDefined();
    expect(screen.getByText(/result\.json/)).toBeDefined();
    expect(screen.getByText(/"result": "hello world"/)).toBeDefined();

    const closeBtn = screen.getByRole("button", { name: "Close dialog" });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});
