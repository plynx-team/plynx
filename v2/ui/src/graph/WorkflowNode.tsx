import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  FeatherIcon,
  getPortIconColor,
  getPortIconName,
} from "../components/FeatherIcon";
import {
  extractNodeRef,
  inputHandleId,
  outputHandleId,
  type WorkflowGraphNode,
} from "./types";

const SCALAR_PORT_TYPES = new Set(["str", "int", "float", "bool"]);

export function WorkflowNode({ data, selected }: NodeProps<WorkflowGraphNode>) {
  const {
    nodeId,
    spec,
    opEntry,
    nodeState,
    inputs,
    outputs,
    isSelected,
    readOnly,
    onLiteralChange,
    onPreviewOutput,
  } = data;
  const status = nodeState?.status;
  const statusLower = (status || "ready").toLowerCase();
  const activeSelected = Boolean(selected || isSelected);
  const displayTitle = spec.title || opEntry?.title || nodeId;
  const description = opEntry?.description || "";

  return (
    <div
      data-testid={`graph-node-${nodeId}`}
      data-node-status={status ?? "IDLE"}
      className={`flow-node node-running-status-${statusLower} ${
        activeSelected ? "selected" : ""
      }`}
    >
      {/* Header */}
      <div className="flow-node-header">
        <div className="flex items-center justify-between gap-1.5">
          <div className="flex items-center gap-1.5 min-w-0">
            <FeatherIcon
              name="cpu"
              size={13}
              style={{ color: "var(--color-primary)" }}
            />
            <div className="flow-title-text" title={displayTitle}>
              {displayTitle}
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {status && (
              <span
                data-testid={`graph-node-status-${nodeId}`}
                className={`status-badge ${status} !text-[9px] !px-1.5 !py-0`}
              >
                {status}
              </span>
            )}
            {description && (
              <span title={description} className="cursor-help">
                <FeatherIcon
                  name="help-circle"
                  size={12}
                  style={{ color: "var(--text-secondary)" }}
                />
              </span>
            )}
          </div>
        </div>

        <div className="mt-0.5 flex items-center justify-between gap-1 text-[10px] font-normal normal-case tracking-normal">
          <span
            className="truncate font-mono"
            style={{ color: "var(--text-secondary)" }}
          >
            {nodeId}
          </span>
          {nodeState?.cache_hit && (
            <span
              data-testid={`graph-node-cache-${nodeId}`}
              className="status-badge READY !text-[9px] !px-1 !py-0"
            >
              cache hit
            </span>
          )}
        </div>
      </div>

      {/* Body: Inputs then Outputs (Legacy v1 OperationNode layout) */}
      <div className="flow-node-body">
        {inputs.map((port) => {
          const rawVal = spec.inputs?.[port.name];
          const isWired = extractNodeRef(rawVal) !== null;
          const showPrimitive =
            !isWired && SCALAR_PORT_TYPES.has(port.type);
          const effectiveVal =
            rawVal !== undefined
              ? rawVal
              : port.default !== undefined && port.default !== null
              ? port.default
              : "";

          return (
            <div
              key={port.name}
              className="flow-node-item flow-node-item-input"
            >
              <Handle
                type="target"
                position={Position.Left}
                id={inputHandleId(port.name)}
                data-testid={`handle-in-${nodeId}-${port.name}`}
                style={{
                  width: "11px",
                  height: "11px",
                  left: "-7px",
                  top: "10px",
                }}
              />
              <div className="flex items-center gap-1.5">
                <FeatherIcon
                  name={getPortIconName(port.type, port.media)}
                  size={12}
                  style={{ color: getPortIconColor(port.type) }}
                />
                <span className="truncate">{port.name}</span>
              </div>

              {showPrimitive && (
                <div
                  className="flow-node-primitive-input nodrag"
                  onClick={(e) => e.stopPropagation()}
                >
                  {port.type === "bool" ? (
                    <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                      <input
                        type="checkbox"
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
                        className="text-[11px]"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {effectiveVal ? "true" : "false"}
                      </span>
                    </label>
                  ) : port.options && port.options.length > 0 ? (
                    <select
                      disabled={readOnly}
                      value={String(effectiveVal)}
                      onChange={(e) =>
                        onLiteralChange?.(nodeId, port.name, e.target.value)
                      }
                    >
                      {port.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
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
                      value={
                        rawVal !== undefined && rawVal !== null
                          ? String(rawVal)
                          : ""
                      }
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
                </div>
              )}
            </div>
          );
        })}

        {outputs.map((port) => {
          const canPreview = nodeState?.status === "SUCCESS";
          return (
            <div
              key={port.name}
              className="flow-node-item flow-node-item-output"
            >
              <div className="flex items-center justify-end gap-1.5">
                <span className="truncate">{port.name}</span>
                <FeatherIcon
                  name={getPortIconName(port.type, port.media)}
                  size={12}
                  style={{ color: getPortIconColor(port.type) }}
                />
              </div>

              {canPreview && onPreviewOutput && (
                <button
                  type="button"
                  data-testid={`node-output-preview-${nodeId}-${port.name}`}
                  className="flow-node-item-thumbnail nodrag"
                  onClick={(e) => {
                    e.stopPropagation();
                    onPreviewOutput(nodeId, port);
                  }}
                >
                  <FeatherIcon name="eye" size={11} />
                  <span className="preview-button">preview</span>
                </button>
              )}

              <Handle
                type="source"
                position={Position.Right}
                id={outputHandleId(port.name)}
                data-testid={`handle-out-${nodeId}-${port.name}`}
                style={{
                  width: "11px",
                  height: "11px",
                  right: "-7px",
                  top: "10px",
                }}
              />
            </div>
          );
        })}
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
