export interface PdfPreviewerProps {
  url: string;
  title?: string;
}

export function PdfPreviewer({ url, title = "PDF Preview" }: PdfPreviewerProps) {
  return (
    <div className="flex flex-col rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] overflow-hidden">
      <iframe
        src={url}
        title={title}
        className="h-[600px] w-full border-0"
      />
      <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-panel-secondary)] p-3 text-center text-xs text-[var(--text-secondary)]">
        If the PDF does not display in your browser, you can{" "}
        <a
          href={url}
          download
          className="text-[var(--color-primary-hover)] underline hover:text-[var(--color-primary)]"
        >
          download it directly
        </a>
        .
      </div>
    </div>
  );
}
