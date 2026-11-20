export interface TextPreviewerProps {
  content: string;
}

export function TextPreviewer({ content }: TextPreviewerProps) {
  const lines = content.split(/\r?\n/);

  return (
    <div className="overflow-x-auto rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)]">
      <div className="space-y-0.5">
        {lines.map((line, idx) => (
          <div key={idx} className="flex items-start gap-3">
            <span className="w-8 shrink-0 text-right select-none text-[var(--text-tertiary)]">
              {idx + 1}
            </span>
            <span className="flex-1 whitespace-pre-wrap break-all">{line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
