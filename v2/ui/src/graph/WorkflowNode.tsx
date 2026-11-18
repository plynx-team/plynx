import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeStatus } from "../api/types.gen";
import { nodeStatusBadgeClasses } from "../stepper/NodeRow";
import {
  extractNodeRef,
  inputHandleId,
  outputHandleId,
  type WorkflowGraphNode,
} from "./types";

function nodeBorderClasses(status: NodeStatus | undefined, selected: boolean): string {
  if (selected) {
    return "border-emerald-400 ring-2 ring-emerald-500/30";
  }
  switch (status) {
    case "SUCCESS":
      return "border-emerald-700/80";
    case "RUNNING":
      return "border-sky-500/90 shadow-sky-900/30";
    case "BUILDING_ENVIRONMENT":
      return "border-indigo-500/90";
    case "WAITING_FOR_USER":
      return "border-amber-500/90";
    case "FAILED":
      return "border-rose-600/90";
    case "CANCELED":
    case "BLOCKED":
      return "border-slate-700";
    default:
      return "border-slate-700/90 hover:border-slate-500";
  }
}

export function WorkflowNode({ data, selected }: NodeProps<WorkflowGraphNode>) {
  const { nodeId, spec, opEntry, nodeState, inputs, outputs, isSelected } = data;
  const status = nodeState?.status;
  const activeSelected = Boolean(selected || isSelected);
  const displayTitle = spec.title || opEntry?.title || nodeId;

  return (
    <div
      data-testid={`graph-node-${nodeId}`}
      data-node-status={status ?? "IDLE"}
      className={`w-[260px] rounded-lg border bg-slate-950/95 shadow-lg transition-colors ${nodeBorderClasses(
        status,
        activeSelected,
      )}`}
    >
      {/* Header */}
      <div className="border-b border-slate-800 bg-slate-900/90 px-3 py-2 rounded-t-lg">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-xs font-semibold text-white">
              {displayTitle}
            </div>
            <div className="truncate font-mono text-[10px] text-slate-400">
              {nodeId}
            </div>
          </div>

          {status && (
            <span
              data-testid={`graph-node-status-${nodeId}`}
              className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${nodeStatusBadgeClasses(
                status,
              )}`}
            >
              {status}
            </span>
          )}
        </div>

        <div className="mt-1 flex items-center justify-between gap-2">
          <span className="truncate font-mono text-[10px] text-slate-500">
            {spec.op}
          </span>
          {nodeState?.cache_hit && (
            <span
              data-testid={`graph-node-cache-${nodeId}`}
              className="shrink-0 rounded border border-teal-800 bg-teal-950 px-1.5 py-0.2 text-[9px] font-semibold text-teal-300"
            >
              cache hit
            </span>
          )}
        </div>
      </div>

      {/* Ports body */}
      <div className="flex justify-between gap-2 px-0 py-2 text-[11px]">
        {/* Input ports */}
        <div className="flex-1 min-w-0 space-y-1">
          {inputs.map((port) => {
            const rawVal = spec.inputs?.[port.name];
            const isWired = extractNodeRef(rawVal) !== null;
            const hasLiteral = rawVal !== undefined && !isWired;
            return (
              <div
                key={port.name}
                className="relative flex items-center gap-1.5 pl-3 pr-1 h-5"
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={inputHandleId(port.name)}
                  data-testid={`handle-in-${nodeId}-${port.name}`}
                  className="!h-2.5 !w-2.5 !border-2 !border-slate-950 !bg-sky-400"
                />
                <span
                  className={`truncate font-mono text-[11px] ${
                    isWired
                      ? "text-sky-300"
                      : hasLiteral
                      ? "text-slate-300"
                      : port.required && port.default === null
                      ? "text-amber-300"
                      : "text-slate-400"
                  }`}
                >
                  {port.name}
                </span>
                <span className="shrink-0 rounded bg-slate-900 px-1 text-[9px] text-slate-500">
                  {port.type}
                </span>
              </div>
            );
          })}
        </div>

        {/* Output ports */}
        <div className="flex-1 min-w-0 space-y-1">
          {outputs.map((port) => (
            <div
              key={port.name}
              className="relative flex items-center justify-end gap-1.5 pl-1 pr-3 h-5"
            >
              <span className="shrink-0 rounded bg-slate-900 px-1 text-[9px] text-slate-500">
                {port.type}
              </span>
              <span className="truncate font-mono text-[11px] text-emerald-300">
                {port.name}
              </span>
              <Handle
                type="source"
                position={Position.Right}
                id={outputHandleId(port.name)}
                data-testid={`handle-out-${nodeId}-${port.name}`}
                className="!h-2.5 !w-2.5 !border-2 !border-slate-950 !bg-emerald-400"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Error footer if failed */}
      {nodeState?.error && (
        <div className="border-t border-rose-900/70 bg-rose-950/50 px-2.5 py-1.5 font-mono text-[10px] text-rose-300 truncate rounded-b-lg">
          {nodeState.error}
        </div>
      )}
    </div>
  );
}
