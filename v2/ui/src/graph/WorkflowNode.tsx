import { useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { InputPortSpec, NodeStatus } from "../api/types.gen";
import {
  FeatherIcon,
  getPortIconColor,
  getPortIconName,
  type FeatherIconName,
} from "../components/FeatherIcon";
import { MarkdownPreviewer } from "../previewers/MarkdownPreviewer";
import {
  extractNodeRef,
  inputHandleId,
  outputHandleId,
  type WorkflowGraphNode,
} from "./types";

function getStatusIcon(status?: NodeStatus): {
  icon: FeatherIconName;
  color: string;
  spin?: boolean;
} {
  switch (status) {
    case "SUCCESS":
      return { icon: "check-circle", color: "var(--color-status-success)" };
    case "RUNNING":
    case "BUILDING_ENVIRONMENT":
      return {
        icon: "loader",
        color: "var(--color-status-running)",
        spin: true,
      };
    case "WAITING_FOR_USER":
      return { icon: "help-circle", color: "var(--color-status-in-queue)" };
    case "FAILED":
      return { icon: "alert-circle", color: "var(--color-status-failed)" };
    case "CANCELED":
    case "BLOCKED":
      return { icon: "slash", color: "var(--color-status-canceled)" };
    case "PENDING":
      return { icon: "clock", color: "var(--color-status-created)" };
    default:
      return { icon: "cpu", color: "var(--color-primary)" };
  }
}

export function WorkflowNode({ data, selected }: NodeProps<WorkflowGraphNode>) {
  const {
    nodeId,
    spec,
    opEntry,
    nodeState,
    nodeDiff,
    inputs,
    outputs,
    isSelected,
    readOnly,
    onLiteralChange,
    onPreviewOutput,
  } = data;
  const [descExpanded, setDescExpanded] = useState<boolean>(false);
  const [expandedPorts, setExpandedPorts] = useState<Record<string, boolean>>(
    {},
  );

  const status = nodeState?.status;
  const statusLower = (status || "ready").toLowerCase();
  const activeSelected = Boolean(selected || isSelected);
  const displayTitle = spec.title || opEntry?.title || nodeId;
  const description = opEntry?.description?.trim() || "";
  const statusIcon = getStatusIcon(status);

  const togglePortExpanded = (portName: string) => {
    setExpandedPorts((prev) => ({
      ...prev,
      [portName]: !prev[portName],
    }));
  };

  // Unwired inputs render in the ComfyUI bottom widget stack
  const unwiredInputs: Array<InputPortSpec> = inputs.filter(
    (port) => extractNodeRef(spec.inputs?.[port.name]) === null,
  );

  const hasDiff = Boolean(nodeDiff && nodeDiff.status !== "unchanged");

  return (
    <div
      data-testid={`graph-node-${nodeId}`}
      data-node-status={status ?? "IDLE"}
      className={`flow-node node-running-status-${statusLower} ${
        activeSelected ? "selected" : ""
      } ${nodeDiff?.status === "added" ? "is-added-in-editor" : ""}`}
    >
      {/* Blender / ComfyUI Status-Colored Header */}
      <div className="flow-node-header">
        <div className="flex items-center justify-between gap-1.5">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              data-testid={status ? `graph-node-status-${nodeId}` : undefined}
              title={status ? `Status: ${status}` : "Idle"}
              className="inline-flex items-center shrink-0"
            >
              <FeatherIcon
                name={statusIcon.icon}
                size={13}
                className={statusIcon.spin ? "animate-spin" : ""}
                style={{ color: statusIcon.color }}
              />
              {status && <span className="sr-only">{status}</span>}
            </span>
            <div className="flow-title-text" title={displayTitle}>
              {displayTitle}
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {hasDiff && nodeDiff && (
              <span
                data-testid={`graph-node-diff-${nodeId}`}
                className="node-diff-badge"
                title={
                  nodeDiff.status === "added"
                    ? "This node was added in the editor after this run"
                    : "This node's inputs or operation differ from the selected run"
                }
              >
                <FeatherIcon name="git-commit" size={9} />
                <span>{nodeDiff.status === "added" ? "NEW" : "DIFF"}</span>
              </span>
            )}
            {nodeState?.cache_hit && (
              <span
                data-testid={`graph-node-cache-${nodeId}`}
                title="Cache hit"
                className="inline-flex items-center"
                style={{ color: "var(--color-status-ready)" }}
              >
                <FeatherIcon name="zap" size={12} />
                <span className="sr-only">cache hit</span>
              </span>
            )}
            {description && (
              <button
                type="button"
                data-testid={`node-desc-toggle-${nodeId}`}
                title={
                  descExpanded ? "Hide description" : "Show description"
                }
                onClick={(e) => {
                  e.stopPropagation();
                  setDescExpanded((v) => !v);
                }}
                className="nodrag p-0.5 rounded hover:bg-black/25"
                style={{ color: "var(--text-secondary)" }}
              >
                <FeatherIcon
                  name={descExpanded ? "chevron-up" : "file-text"}
                  size={12}
                />
              </button>
            )}
          </div>
        </div>

        <div className="mt-0.5 flex items-center justify-between gap-1 text-[10px] font-normal normal-case tracking-normal">
          <span
            className="truncate font-mono"
            style={{ color: "rgba(235, 235, 235, 0.7)" }}
          >
            {nodeId}
          </span>
          {spec.stage && (
            <span
              className="truncate font-mono"
              style={{ color: "rgba(235, 235, 235, 0.55)" }}
            >
              {spec.stage}
            </span>
          )}
        </div>
      </div>

      {/* Expandable Multiline / Markdown Description Section */}
      {description && descExpanded && (
        <div
          data-testid={`node-description-${nodeId}`}
          className="flow-node-description nodrag"
          onClick={(e) => e.stopPropagation()}
        >
          <MarkdownPreviewer content={description} />
        </div>
      )}

      {/* Body: ComfyUI Top Two-Column Socket Zone + Bottom Pill Widget Stack */}
      <div className="flow-node-body">
        {(inputs.length > 0 || outputs.length > 0) && (
          <div className="flow-node-sockets">
            {/* Left Column: Input Sockets */}
            <div className="flow-node-sockets-col">
              {inputs.map((port) => {
                const rawVal = spec.inputs?.[port.name];
                const ref = extractNodeRef(rawVal);
                const dotColor = getPortIconColor(port.type);
                return (
                  <div key={port.name} className="flow-node-socket-row input">
                    <Handle
                      type="target"
                      position={Position.Left}
                      id={inputHandleId(port.name)}
                      data-testid={`handle-in-${nodeId}-${port.name}`}
                      style={{
                        backgroundColor: dotColor,
                        left: "-6px",
                        top: "50%",
                        transform: "translateY(-50%)",
                      }}
                    />
                    <span
                      className="truncate"
                      style={{
                        color: ref
                          ? "var(--text-primary)"
                          : "var(--text-secondary)",
                      }}
                      title={
                        ref
                          ? `${port.name} <- $${ref.from_node}.${ref.output}`
                          : `${port.name} (${port.type})`
                      }
                    >
                      {port.name}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Right Column: Output Sockets */}
            <div className="flow-node-sockets-col">
              {outputs.map((port) => {
                const canPreview = nodeState?.status === "SUCCESS";
                const dotColor = getPortIconColor(port.type);
                return (
                  <div key={port.name} className="flow-node-socket-row output">
                    {canPreview && onPreviewOutput && (
                      <button
                        type="button"
                        data-testid={`node-output-preview-${nodeId}-${port.name}`}
                        title={`Preview ${nodeId}.${port.name}`}
                        className="flow-node-output-eye nodrag"
                        onClick={(e) => {
                          e.stopPropagation();
                          onPreviewOutput(nodeId, port);
                        }}
                      >
                        <FeatherIcon name="eye" size={11} />
                      </button>
                    )}
                    <span
                      className="truncate font-semibold"
                      title={`${port.name} (${port.type})`}
                    >
                      {port.name}
                    </span>
                    <Handle
                      type="source"
                      position={Position.Right}
                      id={outputHandleId(port.name)}
                      data-testid={`handle-out-${nodeId}-${port.name}`}
                      style={{
                        backgroundColor: dotColor,
                        right: "-6px",
                        top: "50%",
                        transform: "translateY(-50%)",
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Bottom Zone: ComfyUI Pill Widgets for Unwired Inputs */}
        {unwiredInputs.length > 0 && (
          <div
            className="flow-node-widgets nodrag"
            onClick={(e) => e.stopPropagation()}
          >
            {unwiredInputs.map((port) => {
              const inputDiff = nodeDiff?.changedInputs?.[port.name];
              const diffTitle = inputDiff
                ? `Changed since run (Run value: ${JSON.stringify(
                    inputDiff.runValue ?? null,
                  )})`
                : undefined;
              const rawVal = spec.inputs?.[port.name];
              const effectiveVal =
                rawVal !== undefined
                  ? rawVal
                  : port.default !== undefined && port.default !== null
                  ? port.default
                  : "";
              const rawString =
                rawVal !== undefined && rawVal !== null
                  ? typeof rawVal === "object"
                    ? JSON.stringify(rawVal, null, 2)
                    : String(rawVal)
                  : "";
              const isMultilineCapable =
                port.type === "str" || port.type === "json";
              const isExpanded =
                Boolean(expandedPorts[port.name]) ||
                port.type === "json" ||
                rawString.includes("\n");

              if (
                isMultilineCapable &&
                !(port.options && port.options.length > 0) &&
                isExpanded
              ) {
                return (
                  <div
                    key={port.name}
                    title={diffTitle}
                    className={`comfy-widget-multiline ${
                      inputDiff ? "is-diff" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="comfy-widget-label">
                        <FeatherIcon
                          name={getPortIconName(port.type, port.media)}
                          size={10}
                          style={{ color: getPortIconColor(port.type) }}
                        />
                        <span>{port.name}</span>
                      </span>
                      <button
                        type="button"
                        data-testid={`node-input-expand-${nodeId}-${port.name}`}
                        title="Collapse to single-line pill"
                        onClick={() => togglePortExpanded(port.name)}
                        className="p-0.5 rounded hover:bg-white/10"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        <FeatherIcon name="minimize-2" size={10} />
                      </button>
                    </div>
                    <textarea
                      data-testid={`node-input-${nodeId}-${port.name}`}
                      rows={3}
                      disabled={readOnly}
                      placeholder={
                        port.default !== null && port.default !== undefined
                          ? typeof port.default === "object"
                            ? JSON.stringify(port.default)
                            : String(port.default)
                          : port.name
                      }
                      value={rawString}
                      onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === "") {
                          onLiteralChange?.(nodeId, port.name, undefined);
                          return;
                        }
                        if (port.type === "json") {
                          try {
                            onLiteralChange?.(
                              nodeId,
                              port.name,
                              JSON.parse(raw),
                            );
                          } catch {
                            onLiteralChange?.(nodeId, port.name, raw);
                          }
                        } else {
                          onLiteralChange?.(nodeId, port.name, raw);
                        }
                      }}
                    />
                  </div>
                );
              }

              return (
                <div
                  key={port.name}
                  title={diffTitle}
                  className={`comfy-widget-pill ${inputDiff ? "is-diff" : ""}`}
                >
                  <span className="comfy-widget-label">
                    <FeatherIcon
                      name={getPortIconName(port.type, port.media)}
                      size={10}
                      style={{ color: getPortIconColor(port.type) }}
                    />
                    <span>{port.name}</span>
                  </span>

                  <div className="flex items-center justify-end gap-1 flex-1 min-w-0">
                    {port.type === "bool" ? (
                      <label className="flex items-center gap-1 cursor-pointer">
                        <input
                          type="checkbox"
                          data-testid={`node-input-${nodeId}-${port.name}`}
                          disabled={readOnly}
                          checked={Boolean(effectiveVal)}
                          onChange={(e) =>
                            onLiteralChange?.(
                              nodeId,
                              port.name,
                              e.target.checked,
                            )
                          }
                          className="!w-3.5 !h-3.5"
                        />
                        <span
                          className="font-mono text-[11px]"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {effectiveVal ? "true" : "false"}
                        </span>
                      </label>
                    ) : port.options && port.options.length > 0 ? (
                      <select
                        data-testid={`node-input-${nodeId}-${port.name}`}
                        disabled={readOnly}
                        value={String(effectiveVal)}
                        onChange={(e) =>
                          onLiteralChange?.(nodeId, port.name, e.target.value)
                        }
                      >
                        {port.options.map((opt) => (
                          <option key={String(opt)} value={String(opt)}>
                            {String(opt)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        data-testid={`node-input-${nodeId}-${port.name}`}
                        type={
                          port.type === "int" || port.type === "float"
                            ? "number"
                            : "text"
                        }
                        disabled={readOnly}
                        placeholder={
                          port.default !== null && port.default !== undefined
                            ? String(port.default)
                            : port.name
                        }
                        value={rawString}
                        onChange={(e) => {
                          const raw = e.target.value;
                          if (raw === "") {
                            onLiteralChange?.(nodeId, port.name, undefined);
                            return;
                          }
                          if (port.type === "int") {
                            const parsed = parseInt(raw, 10);
                            onLiteralChange?.(
                              nodeId,
                              port.name,
                              Number.isNaN(parsed) ? raw : parsed,
                            );
                          } else if (port.type === "float") {
                            const parsed = parseFloat(raw);
                            onLiteralChange?.(
                              nodeId,
                              port.name,
                              Number.isNaN(parsed) ? raw : parsed,
                            );
                          } else {
                            onLiteralChange?.(nodeId, port.name, raw);
                          }
                        }}
                      />
                    )}

                    {isMultilineCapable &&
                      !(port.options && port.options.length > 0) && (
                        <button
                          type="button"
                          data-testid={`node-input-expand-${nodeId}-${port.name}`}
                          title="Expand multiline editor"
                          onClick={() => togglePortExpanded(port.name)}
                          className="p-0.5 rounded hover:bg-white/10 shrink-0"
                          style={{ color: "var(--text-tertiary)" }}
                        >
                          <FeatherIcon name="maximize-2" size={10} />
                        </button>
                      )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Error footer if failed */}
      {nodeState?.error && (
        <div
          className="px-2.5 py-1.5 font-mono text-[10px] truncate rounded-b-lg"
          style={{
            borderTop: "1px solid rgba(244, 67, 54, 0.5)",
            backgroundColor: "rgba(80, 0, 0, 0.5)",
            color: "#ff8a80",
          }}
        >
          {nodeState.error}
        </div>
      )}
    </div>
  );
}
