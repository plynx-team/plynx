import React from "react";

export interface MarkdownPreviewerProps {
  content: string;
  allowLinks?: boolean;
}

function isAllowedLinkUrl(url: string): boolean {
  const trimmed = url.trim();
  try {
    const parsed = new URL(trimmed);
    return (
      parsed.protocol === "http:" ||
      parsed.protocol === "https:" ||
      parsed.protocol === "mailto:"
    );
  } catch {
    return false;
  }
}

function renderInline(text: string, allowLinks: boolean): React.ReactNode {
  // Simple regex-based inline parser
  const parts: Array<React.ReactNode> = [];
  // Match `code`, **bold**, *italic*, and link or image syntax.
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|!?\[[^\]]*\]\([^)]+\))/g;

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
          className="rounded bg-[var(--bg-panel-secondary)] border border-[var(--border-subtle)] px-1.5 py-0.5 font-mono text-xs text-[#80cbc4]"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={match.index} className="font-bold text-[var(--text-primary)]">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("*") && token.endsWith("*")) {
      parts.push(
        <em key={match.index} className="italic text-[var(--text-secondary)]">
          {token.slice(1, -1)}
        </em>,
      );
    } else {
      const isImage = token.startsWith("!");
      const splitIdx = token.indexOf("](");
      const linkText = token.slice(isImage ? 2 : 1, splitIdx);
      const linkUrl = token.slice(splitIdx + 2, -1);
      if (!isImage && allowLinks && isAllowedLinkUrl(linkUrl)) {
        parts.push(
          <a
            key={match.index}
            href={linkUrl.trim()}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-primary-hover)] underline hover:text-[var(--color-primary)]"
          >
            {linkText}
          </a>,
        );
      } else {
        parts.push(<span key={match.index}>{linkText}</span>);
      }
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

export function MarkdownPreviewer({ content, allowLinks = true }: MarkdownPreviewerProps) {
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
            className="my-2 overflow-x-auto rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] p-2.5 font-mono text-xs text-[var(--text-primary)]"
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
        <h1 key={i} className="mt-3 mb-1.5 text-base font-bold text-[var(--text-primary)] border-b border-[var(--border-subtle)] pb-1">
          {renderInline(line.slice(2), allowLinks)}
        </h1>,
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="mt-2.5 mb-1 text-sm font-bold text-[var(--text-primary)]">
          {renderInline(line.slice(3), allowLinks)}
        </h2>,
      );
    } else if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="mt-2 mb-0.5 text-xs font-semibold text-[var(--text-secondary)]">
          {renderInline(line.slice(4), allowLinks)}
        </h3>,
      );
    } else if (line.startsWith("> ")) {
      elements.push(
        <blockquote
          key={i}
          className="my-1.5 border-l-2 border-[var(--border-strong)] pl-2.5 italic text-[var(--text-secondary)]"
        >
          {renderInline(line.slice(2), allowLinks)}
        </blockquote>,
      );
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="ml-4 list-disc text-xs text-[var(--text-primary)]">
          {renderInline(line.slice(2), allowLinks)}
        </li>,
      );
    } else if (!line.trim()) {
      elements.push(<div key={i} className="h-1.5" />);
    } else {
      elements.push(
        <p key={i} className="my-1 text-xs leading-relaxed text-[var(--text-primary)]">
          {renderInline(line, allowLinks)}
        </p>,
      );
    }
  }

  if (inCodeBlock && codeBlockLines.length > 0) {
    elements.push(
      <div
        key="code-last"
        className="my-2 overflow-x-auto rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] p-2.5 font-mono text-xs text-[var(--text-primary)]"
      >
        <pre>{codeBlockLines.join("\n")}</pre>
      </div>,
    );
  }

  return (
    <div className="markdown-content text-xs text-[var(--text-primary)]">
      {elements}
    </div>
  );
}
