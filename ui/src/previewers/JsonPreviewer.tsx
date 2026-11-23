import { useMemo } from "react";

export interface JsonPreviewerProps {
  content: string;
}

export function JsonPreviewer({ content }: JsonPreviewerProps) {
  const formatted = useMemo(() => {
    try {
      const parsed = JSON.parse(content);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return content;
    }
  }, [content]);

  return (
    <div className="overflow-x-auto rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] p-3 font-mono text-xs leading-relaxed text-[#80cbc4] selection:bg-[#244b7a]">
      <pre>{formatted}</pre>
    </div>
  );
}
