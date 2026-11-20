import { useEffect, useRef, useState } from "react";
import { fetchNodeLogs, subscribeRunEvents } from "../api/client";
import type { NodeLogEvent } from "../api/types.gen";
import { parseAnsi, stripAnsi } from "../utils/ansi";
import { ControlButton } from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";

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
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [filterQuery, setFilterQuery] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;
    setLoading(true);
    setError(null);
    setLines([]);

    fetchNodeLogs(runId, nodeId, 0)
      .then((res) => {
        if (!active) return;
        setLines(res.lines);
        setLoading(false);

        unsubscribe = subscribeRunEvents(
          runId,
          (event) => {
            if (!active) return;
            if (event.type === "node_log") {
              const logEvent = event as NodeLogEvent;
              if (logEvent.data.node_id === nodeId) {
                setLines((prev) => [...prev, ...logEvent.data.lines]);
              }
            }
          },
          undefined,
          { logOffset: res.offset },
        );
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [runId, nodeId]);

  useEffect(() => {
    if (autoScroll && !collapsed && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [lines, autoScroll, collapsed]);

  const handleDownload = () => {
    const rawContent = lines.join("\n");
    const blob = new Blob([stripAnsi(rawContent)], {
      type: "text/plain;charset=utf-8",
    });
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
    <div data-testid="logs-panel" className="logs-drawer">
      {/* Drawer Header */}
      <div className="logs-drawer-header">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="flex items-center gap-1.5 text-xs font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            <FeatherIcon
              name={collapsed ? "chevron-up" : "chevron-down"}
              size={14}
            />
            <FeatherIcon
              name="terminal"
              size={13}
              style={{ color: "var(--color-primary)" }}
            />
            <span className="font-mono">
              Logs:{" "}
              <span style={{ color: "var(--color-primary)" }}>{nodeId}</span>
            </span>
          </button>
          <span
            className="text-[11px] font-mono"
            style={{ color: "var(--text-tertiary)" }}
          >
            ({lines.length} lines)
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Filter logs..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="h-6 px-2 text-xs"
          />

          <label
            className="flex items-center gap-1 text-xs cursor-pointer"
            style={{ color: "var(--text-secondary)" }}
          >
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="h-3.5 w-3.5"
            />
            <span>Auto-scroll</span>
          </label>

          <ControlButton
            icon="copy"
            text={copied ? "Copied!" : "Copy"}
            onClick={handleCopy}
            className="!h-6 !min-h-6 !px-2 !text-xs"
          />

          <ControlButton
            icon="download"
            text="Download"
            onClick={handleDownload}
            className="!h-6 !min-h-6 !px-2 !text-xs"
          />

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close logs"
              className="p-1"
              style={{ color: "var(--text-secondary)" }}
            >
              <FeatherIcon name="x" size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          role="alert"
          className="px-3 py-1.5 text-xs"
          style={{
            borderBottom: "1px solid var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      )}

      {/* Log Content Area */}
      {!collapsed && (
        <div
          ref={logContainerRef}
          className="h-48 overflow-y-auto p-2.5 font-mono text-xs leading-relaxed"
          style={{
            backgroundColor: "var(--bg-app)",
            color: "var(--text-primary)",
          }}
        >
          {loading ? (
            <p style={{ color: "var(--text-tertiary)" }}>
              Loading log output...
            </p>
          ) : filteredLines.length === 0 ? (
            <p style={{ color: "var(--text-tertiary)" }}>
              {lines.length === 0
                ? "No logs recorded for this node yet."
                : "No lines match the current filter."}
            </p>
          ) : (
            <div className="space-y-0.5">
              {filteredLines.map((line, idx) => {
                const segments = parseAnsi(line);
                return (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 px-1 hover:bg-[#262626]"
                  >
                    <span
                      className="w-7 shrink-0 text-right text-[10px] select-none"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {idx + 1}
                    </span>
                    <div className="flex-1 whitespace-pre-wrap break-all">
                      {segments.map((seg, sIdx) => (
                        <span
                          key={sIdx}
                          className={`${seg.color ?? ""} ${
                            seg.bold ? "font-bold" : ""
                          } ${seg.dim ? "opacity-60" : ""} ${
                            seg.underline ? "underline" : ""
                          }`}
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
      )}
    </div>
  );
}
