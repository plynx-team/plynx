export interface TextPreviewerProps {
  content: string;
}

export function TextPreviewer({ content }: TextPreviewerProps) {
  const lines = content.split(/\r?\n/);

  return (
    <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-300">
      <div className="space-y-0.5">
        {lines.map((line, idx) => (
          <div key={idx} className="flex items-start gap-3">
            <span className="w-8 shrink-0 text-right select-none text-slate-600">
              {idx + 1}
            </span>
            <span className="flex-1 whitespace-pre-wrap break-all">{line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
