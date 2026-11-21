import { useEffect, useState } from "react";
import { FeatherIcon } from "../components/FeatherIcon";
import { CsvPreviewer } from "./CsvPreviewer";
import { ImagePreviewer } from "./ImagePreviewer";
import { JsonPreviewer } from "./JsonPreviewer";
import { MarkdownPreviewer } from "./MarkdownPreviewer";
import { PdfPreviewer } from "./PdfPreviewer";
import { TextPreviewer } from "./TextPreviewer";

export interface ArtifactPreviewDialogProps {
  title: string;
  url: string;
  mediaType?: string | null;
  filename?: string;
  initialContent?: string;
  onClose: () => void;
}

export function detectPreviewKind(
  mediaType?: string | null,
  filename?: string,
): "pdf" | "image" | "audio" | "csv" | "tsv" | "json" | "markdown" | "text" {
  const mt = (mediaType || "").toLowerCase();
  const fn = (filename || "").toLowerCase();

  if (mt === "application/pdf" || fn.endsWith(".pdf")) return "pdf";
  if (
    mt.startsWith("image/") ||
    fn.endsWith(".png") ||
    fn.endsWith(".jpg") ||
    fn.endsWith(".jpeg") ||
    fn.endsWith(".gif") ||
    fn.endsWith(".svg") ||
    fn.endsWith(".webp")
  ) {
    return "image";
  }
  if (
    mt.startsWith("audio/") ||
    fn.endsWith(".wav") ||
    fn.endsWith(".mp3") ||
    fn.endsWith(".ogg") ||
    fn.endsWith(".m4a")
  ) {
    return "audio";
  }
  if (mt === "text/csv" || fn.endsWith(".csv")) return "csv";
  if (mt === "text/tab-separated-values" || fn.endsWith(".tsv")) return "tsv";
  if (mt === "application/json" || fn.endsWith(".json")) return "json";
  if (mt === "text/markdown" || fn.endsWith(".md")) return "markdown";
  return "text";
}

export function ArtifactPreviewDialog({
  title,
  url,
  mediaType,
  filename,
  initialContent,
  onClose,
}: ArtifactPreviewDialogProps) {
  const [content, setContent] = useState<string>(initialContent || "");
  const [loading, setLoading] = useState<boolean>(!initialContent);
  const [error, setError] = useState<string | null>(null);

  const kind = detectPreviewKind(mediaType, filename);
  const isDirectUrl = kind === "pdf" || kind === "image" || kind === "audio";

  useEffect(() => {
    if (isDirectUrl || initialContent !== undefined) {
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    fetch(url)
      .then((res) => {
        if (!res.ok)
          throw new Error(`Failed to load artifact (${res.status})`);
        return res.text();
      })
      .then((text) => {
        if (active) {
          setContent(text);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [url, isDirectUrl, initialContent]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="artifact-preview-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
    >
      <div className="PreviewDialogWindow max-h-[90vh] w-full max-w-4xl">
        {/* Dialog Header */}
        <div
          className="flex items-center justify-between px-4 py-2.5"
          style={{
            backgroundColor: "var(--bg-header)",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div className="flex items-center gap-2">
            <FeatherIcon
              name="eye"
              size={15}
              style={{ color: "var(--color-primary)" }}
            />
            <h2 className="text-sm font-bold">{title}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1"
            style={{ color: "var(--text-secondary)" }}
          >
            <FeatherIcon name="x" size={16} />
          </button>
        </div>

        {/* Informational Note Banner */}
        <div className="preview-note-banner">
          <div className="preview-note-text font-mono">
            {filename || title} {mediaType ? `(${mediaType})` : ""}
          </div>
          <a
            href={url}
            download={filename || title}
            className="preview-download-button"
          >
            <FeatherIcon name="download" size={13} />
            <span>Download</span>
          </a>
        </div>

        {/* Dialog Content */}
        <div className="preview-content-box">
          {error ? (
            <div
              role="alert"
              className="rounded p-3 text-xs"
              style={{
                border: "1px solid var(--color-error)",
                backgroundColor: "rgba(244, 67, 54, 0.15)",
                color: "#ff8a80",
              }}
            >
              {error}
            </div>
          ) : loading ? (
            <div
              className="p-10 text-center text-sm"
              style={{ color: "var(--text-secondary)" }}
            >
              Loading preview...
            </div>
          ) : (
            <div>
              {kind === "pdf" && <PdfPreviewer url={url} title={title} />}
              {kind === "image" && <ImagePreviewer url={url} alt={title} />}
              {kind === "audio" && (
                <div
                  data-testid="audio-previewer"
                  className="flex flex-col items-center justify-center p-8 bg-[#1e1e1e] rounded border border-[#3c3c3c] my-2"
                >
                  <FeatherIcon
                    name="music"
                    size={36}
                    className="text-[var(--color-primary)] mb-4"
                  />
                  <audio
                    data-testid="audio-element"
                    controls
                    src={url}
                    className="w-full max-w-md"
                  />
                </div>
              )}
              {kind === "csv" && (
                <CsvPreviewer content={content} delimiter="," />
              )}
              {kind === "tsv" && (
                <CsvPreviewer content={content} delimiter="\t" />
              )}
              {kind === "json" && <JsonPreviewer content={content} />}
              {kind === "markdown" && <MarkdownPreviewer content={content} />}
              {kind === "text" && <TextPreviewer content={content} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
