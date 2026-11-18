export interface PdfPreviewerProps {
  url: string;
  title?: string;
}

export function PdfPreviewer({ url, title = "PDF Preview" }: PdfPreviewerProps) {
  return (
    <div className="flex flex-col rounded border border-slate-800 bg-slate-950 overflow-hidden">
      <iframe
        src={url}
        title={title}
        className="h-[600px] w-full border-0"
      />
      <div className="border-t border-slate-800 bg-slate-900/60 p-3 text-center text-xs text-slate-400">
        If the PDF does not display in your browser, you can{" "}
        <a
          href={url}
          download
          className="text-emerald-400 underline hover:text-emerald-300"
        >
          download it directly
        </a>
        .
      </div>
    </div>
  );
}
