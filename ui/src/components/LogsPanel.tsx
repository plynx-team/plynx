import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchNodeAgentTurns,
  fetchNodeLogs,
  subscribeRunEvents,
} from "../api/client";
import type { AgentTurnModel, NodeLogEvent } from "../api/types.gen";
import { parseAnsi, stripAnsi } from "../utils/ansi";
import { ControlButton } from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";

export type LogsDrawerTab = "all" | "stdout" | "stderr" | "agent_turns";

export interface LogsPanelProps {
  runId: string;
  nodeId: string;
  onClose?: () => void;
}

function formatTurnDuration(startedAt: number, finishedAt: number): string {
  const secs = Math.max(0, finishedAt - startedAt);
  if (secs < 1) {
    return `${Math.round(secs * 1000)}ms`;
  }
  return `${secs.toFixed(2)}s`;
}

function turnStatusStyle(status: AgentTurnModel["status"]): {
  borderColor: string;
  color: string;
} {
  if (status === "completed") {
    return {
      borderColor: "var(--color-status-success, #4caf50)",
      color: "var(--color-status-success, #4caf50)",
    };
  }
  if (status === "needs_input") {
    return {
      borderColor: "var(--color-warning)",
      color: "var(--color-warning)",
    };
  }
  return {
    borderColor: "var(--color-primary)",
    color: "var(--color-primary)",
  };
}

export function LogsPanel({ runId, nodeId, onClose }: LogsPanelProps) {
  const [activeTab, setActiveTab] = useState<LogsDrawerTab>("all");
  const [combinedLines, setCombinedLines] = useState<Array<string>>([]);
  const [stdoutLines, setStdoutLines] = useState<Array<string>>([]);
  const [stderrLines, setStderrLines] = useState<Array<string>>([]);
  const [agentTurns, setAgentTurns] = useState<Array<AgentTurnModel>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [filterQuery, setFilterQuery] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const refreshAgentTurns = useCallback(
    async (isActiveCheck: () => boolean) => {
      if (typeof fetchNodeAgentTurns !== "function") return;
      try {
        const res = await fetchNodeAgentTurns(runId, nodeId);
        if (isActiveCheck() && Array.isArray(res?.turns)) {
          setAgentTurns(res.turns);
        }
      } catch {
        // Ignore missing/unmocked agent-turns endpoint
      }
    },
    [runId, nodeId],
  );

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;
    setLoading(true);
    setError(null);
    setCombinedLines([]);
    setStdoutLines([]);
    setStderrLines([]);
    setAgentTurns([]);

    void refreshAgentTurns(() => active);

    Promise.all([
      fetchNodeLogs(runId, nodeId, 0, "stdout"),
      fetchNodeLogs(runId, nodeId, 0, "stderr").catch(() => ({
        lines: [],
        offset: 0,
      })),
    ])
      .then(([stdoutRes, stderrRes]) => {
        if (!active) return;
        setStdoutLines(stdoutRes.lines);
        setStderrLines(stderrRes.lines);
        setCombinedLines([...stdoutRes.lines, ...stderrRes.lines]);
        setLoading(false);

        unsubscribe = subscribeRunEvents(runId, (event) => {
          if (!active) return;
          if (event.type === "node_log") {
            const logEvent = event as NodeLogEvent;
            if (logEvent.data.node_id === nodeId) {
              setCombinedLines((prev) => [...prev, ...logEvent.data.lines]);
              if (logEvent.data.stream === "stderr") {
                setStderrLines((prev) => [...prev, ...logEvent.data.lines]);
              } else {
                setStdoutLines((prev) => [...prev, ...logEvent.data.lines]);
              }
            }
          } else if (
            (event.type === "node_status" ||
              event.type === "node_checkpoint" ||
              event.type === "checkpoint_resolved") &&
            event.data.node_id === nodeId
          ) {
            void refreshAgentTurns(() => active);
          }
        });
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
  }, [runId, nodeId, refreshAgentTurns]);

  const activeLines = useMemo(() => {
    if (activeTab === "stdout") return stdoutLines;
    if (activeTab === "stderr") return stderrLines;
    return combinedLines;
  }, [activeTab, combinedLines, stdoutLines, stderrLines]);

  useEffect(() => {
    if (
      activeTab !== "agent_turns" &&
      autoScroll &&
      !collapsed &&
      logContainerRef.current
    ) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [activeLines, activeTab, autoScroll, collapsed]);

  const handleSelectTab = (tab: LogsDrawerTab) => {
    setActiveTab(tab);
    if (collapsed) {
      setCollapsed(false);
    }
    if (tab === "agent_turns") {
      let mounted = true;
      void refreshAgentTurns(() => mounted);
      return () => {
        mounted = false;
      };
    }
    return undefined;
  };

  const handleDownload = () => {
    const rawContent =
      activeTab === "agent_turns"
        ? JSON.stringify({ schema: 1, turns: agentTurns }, null, 2)
        : stripAnsi(activeLines.join("\n"));
    const mime =
      activeTab === "agent_turns"
        ? "application/json;charset=utf-8"
        : "text/plain;charset=utf-8";
    const ext = activeTab === "agent_turns" ? "agent_turns.json" : "log";
    const blob = new Blob([rawContent], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${runId.slice(0, 8)}-${nodeId}.${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    const rawContent =
      activeTab === "agent_turns"
        ? JSON.stringify({ schema: 1, turns: agentTurns }, null, 2)
        : stripAnsi(activeLines.join("\n"));
    try {
      await navigator.clipboard.writeText(rawContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard write failure
    }
  };

  const allIndexedLines = useMemo(
    () => activeLines.map((line, idx) => ({ line, originalIndex: idx + 1 })),
    [activeLines],
  );

  const filteredLines = useMemo(() => {
    if (!filterQuery.trim()) return allIndexedLines;
    const q = filterQuery.toLowerCase();
    return allIndexedLines.filter(({ line }) =>
      line.toLowerCase().includes(q),
    );
  }, [allIndexedLines, filterQuery]);

  return (
    <div data-testid="logs-panel" className="logs-drawer">
      {/* Drawer Header */}
      <div className="logs-drawer-header">
        <div className="flex flex-wrap items-center gap-2">
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
            ({combinedLines.length} lines)
          </span>

          {/* Stream & Agent Turns Tabs */}
          <div
            role="tablist"
            aria-label="Node inspector tabs"
            className="flex items-center gap-1 ml-1"
          >
            {(
              [
                { id: "all", label: "All" },
                { id: "stdout", label: "stdout" },
                { id: "stderr", label: "stderr" },
                {
                  id: "agent_turns",
                  label:
                    agentTurns.length > 0
                      ? `Agent Turns (${agentTurns.length})`
                      : "Agent Turns",
                },
              ] as const
            ).map((tab) => {
              const selected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  data-testid={`logs-tab-${tab.id}`}
                  onClick={() => handleSelectTab(tab.id)}
                  className="px-2 py-0.5 rounded text-[11px] font-mono border transition-colors"
                  style={{
                    borderColor: selected
                      ? "var(--color-primary)"
                      : "var(--border-subtle)",
                    backgroundColor: selected
                      ? "rgba(38, 128, 235, 0.16)"
                      : "transparent",
                    color: selected
                      ? "var(--text-primary)"
                      : "var(--text-secondary)",
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {activeTab !== "agent_turns" && (
            <>
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
            </>
          )}

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

      {/* Drawer Content Area */}
      {!collapsed && (
        <div
          ref={logContainerRef}
          className="h-48 overflow-y-auto p-2.5 font-mono text-xs leading-relaxed"
          style={{
            backgroundColor: "var(--bg-app)",
            color: "var(--text-primary)",
          }}
        >
          {activeTab === "agent_turns" ? (
            agentTurns.length === 0 ? (
              <p
                data-testid="agent-turns-empty"
                style={{ color: "var(--text-tertiary)" }}
              >
                No agent turns recorded for this node.
              </p>
            ) : (
              <div
                data-testid="agent-turns-list"
                className="space-y-2 font-sans"
              >
                {agentTurns.map((turn) => {
                  const badge = turnStatusStyle(turn.status);
                  return (
                    <div
                      key={turn.turn_index}
                      data-testid={`agent-turn-card-${turn.turn_index}`}
                      className="rounded p-2 space-y-1.5"
                      style={{
                        backgroundColor: "var(--bg-panel)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-mono font-semibold">
                            Turn #{turn.turn_index}
                          </span>
                          <span
                            className="px-1.5 py-0.5 rounded font-mono text-[10px] border"
                            style={{
                              borderColor: "var(--border-subtle)",
                              color: "var(--text-secondary)",
                            }}
                          >
                            {turn.provider}
                            {turn.model ? ` · ${turn.model}` : ""}
                          </span>
                          <span
                            data-testid={`agent-turn-status-${turn.turn_index}`}
                            className="px-1.5 py-0.5 rounded font-mono text-[10px] border uppercase"
                            style={badge}
                          >
                            {turn.status}
                          </span>
                        </div>
                        <div
                          className="flex items-center gap-2 text-[11px] font-mono"
                          style={{ color: "var(--text-tertiary)" }}
                        >
                          {turn.session_id && (
                            <span title="Session ID">
                              session: {turn.session_id}
                            </span>
                          )}
                          <span>
                            {formatTurnDuration(
                              turn.started_at,
                              turn.finished_at,
                            )}
                          </span>
                        </div>
                      </div>

                      {turn.prompt_summary && (
                        <div
                          className="text-xs"
                          style={{ color: "var(--text-secondary)" }}
                        >
                          {turn.prompt_summary}
                        </div>
                      )}

                      {turn.questions && turn.questions.length > 0 && (
                        <div
                          className="rounded p-1.5 space-y-1 text-xs"
                          style={{
                            backgroundColor: "var(--bg-app)",
                            border: "1px solid var(--border-subtle)",
                          }}
                        >
                          <div
                            className="text-[10px] font-semibold uppercase"
                            style={{ color: "var(--text-tertiary)" }}
                          >
                            Questions Asked
                          </div>
                          {turn.questions.map((q) => {
                            const ans = turn.user_answers?.[q.id];
                            return (
                              <div key={q.id} className="space-y-0.5">
                                <div>
                                  <span className="font-mono font-semibold">
                                    {q.id}:
                                  </span>{" "}
                                  <span>{q.question}</span>
                                </div>
                                {ans !== undefined && (
                                  <div
                                    className="font-mono text-[11px] pl-2"
                                    style={{ color: "var(--color-primary)" }}
                                  >
                                    Answer:{" "}
                                    {Array.isArray(ans)
                                      ? ans.join(", ")
                                      : ans}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {turn.graph_patch && (
                        <div
                          className="rounded p-1.5 space-y-1 text-xs"
                          style={{
                            backgroundColor: "var(--bg-app)",
                            border: "1px solid var(--border-subtle)",
                          }}
                        >
                          <div className="font-semibold">
                            Proposed Patch: {turn.graph_patch.reason}
                          </div>
                          <pre className="font-mono text-[11px] whitespace-pre-wrap overflow-x-auto">
                            {JSON.stringify(
                              {
                                add_nodes: turn.graph_patch.add_nodes,
                                rewire_inputs: turn.graph_patch.rewire_inputs,
                              },
                              null,
                              2,
                            )}
                          </pre>
                        </div>
                      )}

                      {turn.outputs && (
                        <pre
                          className="rounded p-1.5 font-mono text-[11px] whitespace-pre-wrap overflow-x-auto"
                          style={{
                            backgroundColor: "var(--bg-app)",
                            border: "1px solid var(--border-subtle)",
                          }}
                        >
                          {JSON.stringify(turn.outputs, null, 2)}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            )
          ) : loading ? (
            <p style={{ color: "var(--text-tertiary)" }}>
              Loading log output...
            </p>
          ) : filteredLines.length === 0 ? (
            <p style={{ color: "var(--text-tertiary)" }}>
              {activeLines.length === 0
                ? "No logs recorded for this node yet."
                : "No lines match the current filter."}
            </p>
          ) : (
            <div className="space-y-0.5">
              {filteredLines.map(({ line, originalIndex }) => {
                const segments = parseAnsi(line);
                return (
                  <div
                    key={originalIndex}
                    className="flex items-start gap-2.5 px-1 hover:bg-[#262626]"
                  >
                    <span
                      className="w-7 shrink-0 text-right text-[10px] select-none"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {originalIndex}
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
