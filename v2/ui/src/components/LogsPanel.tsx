import { useEffect, useRef, useState } from "react";
import { fetchNodeLogs, subscribeRunEvents } from "../api/client";
import type { NodeLogEvent } from "../api/types.gen";
import { parseAnsi, stripAnsi } from "../utils/ansi";

export interface LogsPanelProps {
  runId: string;
  nodeId: string;
  onClose?: () => void;
}

export function LogsPanel({ runId, nodeId, onClose }: LogsPanelProps) {
  const [lines, setLines] = useState<Array<string>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [filterQuery, setFilterQuery] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Load history from REST on mount or nodeId change
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setLines([]);

    fetchNodeLogs(runId, nodeId, 0)
      .then((res) => {
        if (!active) return;
        setLines(res.lines);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    // Listen to live SSE node_log events
    const unsubscribe = subscribeRunEvents(runId, (event) => {
      if (!active) return;
      if (event.type === "node_log") {
        const logEvent = event as NodeLogEvent;
        if (logEvent.data.node_id === nodeId) {
          setLines((prev) => [...prev, ...logEvent.data.lines]);
        }
      }
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [runId, nodeId]);

  // Auto-scroll to bottom as new lines arrive
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  const handleDownload = () => {
    const rawContent = lines.join("\n");
    const blob = new Blob([stripAnsi(rawContent)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${runId.slice(0, 8)}-${nodeId}.log`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    const rawContent = stripAnsi(lines.join("\n"));
    try {
      await navigator.clipboard.writeText(rawContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard write failure
    }
  };

  const filteredLines = filterQuery.trim()
    ? lines.filter((line) =>
        line.toLowerCase().includes(filterQuery.toLowerCase()),
      )
    : lines;

  return (
    <div
      data-testid="logs-panel"
      className="flex flex-col rounded-lg border border-slate-800 bg-slate-950 shadow-xl overflow-hidden"
    >
      {/* Panel Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800 bg-slate-900/80 px-4 py-3 gap-3">
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <h3 className="font-mono text-xs font-bold text-white">
            Logs: <span className="text-emerald-400">{nodeId}</span>
          </h3>
          <span className="text-[11px] text-slate-500 font-mono">
            ({lines.length} lines)
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Filter logs..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-300 placeholder-slate-600 focus:border-slate-700 focus:outline-none"
          />

          <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-slate-700 bg-slate-900 text-emerald-600"
            />
            <span>Auto-scroll</span>
          </label>

          <button
            type="button"
            onClick={handleCopy}
            className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            {copied ? "Copied!" : "Copy"}
          </button>

          <button
            type="button"
            onClick={handleDownload}
            className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            Download
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close logs"
              className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            >
              &times;
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          role="alert"
          className="border-b border-rose-900 bg-rose-950/60 p-2.5 text-xs text-rose-300"
        >
          {error}
        </div>
      )}

      {/* Log Content Area */}
      <div
        ref={logContainerRef}
        className="h-72 overflow-y-auto p-4 font-mono text-xs leading-relaxed text-slate-300 selection:bg-emerald-900 selection:text-emerald-100"
      >
        {loading ? (
          <p className="text-slate-500">Loading log output...</p>
        ) : filteredLines.length === 0 ? (
          <p className="text-slate-600">
            {lines.length === 0
              ? "No logs recorded for this node yet."
              : "No lines match the current filter."}
          </p>
        ) : (
          <div className="space-y-0.5">
            {filteredLines.map((line, idx) => {
              const segments = parseAnsi(line);
              return (
                <div key={idx} className="flex items-start gap-3 hover:bg-slate-900/40">
                  <span className="w-8 shrink-0 text-right text-[10px] select-none text-slate-600">
                    {idx + 1}
                  </span>
                  <div className="flex-1 whitespace-pre-wrap break-all">
                    {segments.map((seg, sIdx) => (
                      <span
                        key={sIdx}
                        className={`${seg.color ?? ""} ${seg.bold ? "font-bold" : ""} ${
                          seg.dim ? "opacity-60" : ""
                        } ${seg.underline ? "underline" : ""}`}
                      >
                        {seg.text}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
