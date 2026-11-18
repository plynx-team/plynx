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
    <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-emerald-300 selection:bg-emerald-950">
      <pre>{formatted}</pre>
    </div>
  );
}
