import React from "react";

export interface MarkdownPreviewerProps {
  content: string;
}

function renderInline(text: string): React.ReactNode {
  // Simple regex-based inline parser
  const parts: Array<React.ReactNode> = [];
  // Match `code`, **bold**, *italic*, [link](url)
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(
        <code
          key={match.index}
          className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-emerald-300"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={match.index} className="font-bold text-white">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("*") && token.endsWith("*")) {
      parts.push(
        <em key={match.index} className="italic text-slate-200">
          {token.slice(1, -1)}
        </em>,
      );
    } else if (token.startsWith("[") && token.includes("](") && token.endsWith(")")) {
      const splitIdx = token.indexOf("](");
      const linkText = token.slice(1, splitIdx);
      const linkUrl = token.slice(splitIdx + 2, -1);
      parts.push(
        <a
          key={match.index}
          href={linkUrl}
          target="_blank"
          rel="noreferrer"
          className="text-sky-400 underline hover:text-sky-300"
        >
          {linkText}
        </a>,
      );
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

export function MarkdownPreviewer({ content }: MarkdownPreviewerProps) {
  const lines = content.split(/\r?\n/);
  const elements: Array<React.ReactNode> = [];

  let inCodeBlock = false;
  let codeBlockLines: Array<string> = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <div
            key={`code-${i}`}
            className="my-3 overflow-x-auto rounded border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-slate-200"
          >
            <pre>{codeBlockLines.join("\n")}</pre>
          </div>,
        );
        codeBlockLines = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      continue;
    }

    if (line.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="mt-4 mb-2 text-xl font-bold text-white border-b border-slate-800 pb-1">
          {renderInline(line.slice(2))}
        </h1>,
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="mt-3 mb-1.5 text-lg font-bold text-slate-100">
          {renderInline(line.slice(3))}
        </h2>,
      );
    } else if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="mt-2.5 mb-1 text-base font-semibold text-slate-200">
          {renderInline(line.slice(4))}
        </h3>,
      );
    } else if (line.startsWith("> ")) {
      elements.push(
        <blockquote
          key={i}
          className="my-2 border-l-2 border-slate-700 pl-3 italic text-slate-400"
        >
          {renderInline(line.slice(2))}
        </blockquote>,
      );
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="ml-4 list-disc text-sm text-slate-300">
          {renderInline(line.slice(2))}
        </li>,
      );
    } else if (!line.trim()) {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(
        <p key={i} className="my-1 text-sm leading-relaxed text-slate-300">
          {renderInline(line)}
        </p>,
      );
    }
  }

  if (inCodeBlock && codeBlockLines.length > 0) {
    elements.push(
      <div
        key="code-last"
        className="my-3 overflow-x-auto rounded border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-slate-200"
      >
        <pre>{codeBlockLines.join("\n")}</pre>
      </div>,
    );
  }

  return (
    <div className="prose-invert rounded border border-slate-800 bg-slate-950/70 p-5">
      {elements}
    </div>
  );
}
