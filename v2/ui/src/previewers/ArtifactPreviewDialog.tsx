import { useEffect, useState } from "react";
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
): "pdf" | "image" | "csv" | "tsv" | "json" | "markdown" | "text" {
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
  const isDirectUrl = kind === "pdf" || kind === "image";

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
        if (!res.ok) throw new Error(`Failed to load artifact (${res.status})`);
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden">
        {/* Dialog Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-950/70">
          <div className="space-y-0.5">
            <h2 className="text-base font-bold text-white">{title}</h2>
            <p className="font-mono text-xs text-slate-400">
              {filename || title} {mediaType ? `(${mediaType})` : ""}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <a
              href={url}
              download={filename || title}
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white"
            >
              Download
            </a>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              &times;
            </button>
          </div>
        </div>

        {/* Dialog Content */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-950/40">
          {error ? (
            <div
              role="alert"
              className="rounded border border-rose-900 bg-rose-950/60 p-4 text-xs text-rose-300"
            >
              {error}
            </div>
          ) : loading ? (
            <div className="p-12 text-center text-sm text-slate-400">
              Loading preview...
            </div>
          ) : (
            <div>
              {kind === "pdf" && <PdfPreviewer url={url} title={title} />}
              {kind === "image" && <ImagePreviewer url={url} alt={title} />}
              {kind === "csv" && <CsvPreviewer content={content} delimiter="," />}
              {kind === "tsv" && <CsvPreviewer content={content} delimiter="\t" />}
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
