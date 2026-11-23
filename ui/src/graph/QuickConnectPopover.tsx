import { useEffect, useMemo, useRef, useState } from "react";
import type {
  InputPortSpec,
  OpEntry,
  OutputPortSpec,
} from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";
import { portsCompatible } from "./validation";

export interface QuickConnectDropData {
  originNodeId: string;
  originNodeTitle?: string;
  originPortName: string;
  handleType: "source" | "target";
  originPort: OutputPortSpec | InputPortSpec;
  screenPos: { x: number; y: number };
  flowPos: { x: number; y: number };
  stageId: string;
}

export interface QuickConnectPopoverProps {
  data: QuickConnectDropData;
  ops: ReadonlyArray<OpEntry>;
  onSelect: (opId: string, portName: string) => void;
  onClose: () => void;
}

interface CompatiblePortOption {
  op: OpEntry;
  port: InputPortSpec | OutputPortSpec;
}

export function QuickConnectPopover({
  data,
  ops,
  onSelect,
  onClose,
}: QuickConnectPopoverProps) {
  const [query, setQuery] = useState<string>("");
  const [showAllOps, setShowAllOps] = useState<boolean>(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { originPort, handleType } = data;

  // Filter ops by port compatibility
  const compatibleOptions: Array<CompatiblePortOption> = useMemo(() => {
    const list: Array<CompatiblePortOption> = [];
    const validOps = ops.filter((op) => op.valid);

    for (const op of validOps) {
      if (handleType === "source") {
        // Dragged from output -> need op inputs compatible with originPort (output)
        const srcPort = originPort as OutputPortSpec;
        for (const input of op.inputs) {
          if (showAllOps || portsCompatible(srcPort, input).valid) {
            list.push({ op, port: input });
          }
        }
      } else {
        // Dragged from input -> need op outputs compatible with originPort (input)
        const dstPort = originPort as InputPortSpec;
        for (const output of op.outputs) {
          if (showAllOps || portsCompatible(output, dstPort).valid) {
            list.push({ op, port: output });
          }
        }
      }
    }
    return list;
  }, [ops, originPort, handleType, showAllOps]);

  // Apply search query filter
  const filteredOptions = useMemo(() => {
    if (!query.trim()) return compatibleOptions;
    const q = query.toLowerCase();
    return compatibleOptions.filter(
      (opt) =>
        opt.op.title.toLowerCase().includes(q) ||
        opt.op.name.toLowerCase().includes(q) ||
        opt.op.id.toLowerCase().includes(q) ||
        opt.port.name.toLowerCase().includes(q) ||
        opt.port.type.toLowerCase().includes(q),
    );
  }, [compatibleOptions, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredOptions]);

  // Handle escape and keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          filteredOptions.length > 0
            ? (prev + 1) % filteredOptions.length
            : 0,
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          filteredOptions.length > 0
            ? (prev - 1 + filteredOptions.length) % filteredOptions.length
            : 0,
        );
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const active = filteredOptions[selectedIndex];
        if (active) {
          onSelect(active.op.id, active.port.name);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredOptions, selectedIndex, onSelect, onClose]);

  // Adjust positioning to stay within viewport
  const popoverStyle = useMemo(() => {
    const width = 320;
    const height = 360;
    const margin = 16;
    let x = data.screenPos.x;
    let y = data.screenPos.y;

    if (typeof window !== "undefined") {
      if (x + width > window.innerWidth - margin) {
        x = Math.max(margin, window.innerWidth - width - margin);
      }
      if (y + height > window.innerHeight - margin) {
        y = Math.max(margin, window.innerHeight - height - margin);
      }
    }

    return {
      left: `${Math.round(x)}px`,
      top: `${Math.round(y)}px`,
      width: `${width}px`,
      maxHeight: `${height}px`,
    };
  }, [data.screenPos]);

  return (
    <div
      data-testid="quick-connect-popover"
      className="fixed z-50 rounded-lg shadow-2xl flex flex-col overflow-hidden text-xs"
      style={{
        ...popoverStyle,
        backgroundColor: "var(--bg-panel)",
        border: "1px solid var(--border-default)",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.05)",
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border-default)] bg-[var(--bg-canvas)]">
        <div className="flex items-center gap-1.5 font-medium text-[var(--text-primary)]">
          <FeatherIcon
            name="zap"
            size={14}
            style={{ color: "var(--color-primary)" }}
          />
          <span>Quick Connect</span>
        </div>
        <button
          type="button"
          data-testid="btn-close-quick-connect"
          onClick={onClose}
          className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors p-0.5"
          title="Close (Esc)"
        >
          <FeatherIcon name="x" size={14} />
        </button>
      </div>

      {/* Wire direction summary banner */}
      <div className="px-3 py-1.5 text-[11px] bg-[rgba(38,128,235,0.08)] border-b border-[var(--border-default)] text-[var(--text-secondary)] flex items-center justify-between">
        <span>
          {handleType === "source" ? (
            <>
              Output <span className="font-semibold text-[var(--color-primary)]">"{data.originPortName}"</span> ({originPort.type}) ➔
            </>
          ) : (
            <>
              ➔ Input <span className="font-semibold text-[var(--color-primary)]">"{data.originPortName}"</span> ({originPort.type})
            </>
          )}
        </span>
        <span className="text-[10px] text-[var(--text-tertiary)]">
          Stage: {data.stageId}
        </span>
      </div>

      {/* Search Bar */}
      <div className="p-2 border-b border-[var(--border-default)]">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-[var(--border-default)] bg-[var(--bg-canvas)]">
          <FeatherIcon
            name="search"
            size={13}
            style={{ color: "var(--text-tertiary)" }}
          />
          <input
            ref={searchInputRef}
            type="text"
            data-testid="input-quick-connect-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search operations or ports..."
            className="w-full bg-transparent text-xs text-[var(--text-primary)] focus:outline-none"
            autoFocus
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
            >
              <FeatherIcon name="x" size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Options List */}
      <div
        ref={listRef}
        data-testid="quick-connect-list"
        className="flex-1 overflow-y-auto p-1 space-y-0.5"
      >
        {filteredOptions.length === 0 ? (
          <div className="p-4 text-center space-y-2">
            <p className="text-[var(--text-tertiary)] text-xs">
              No matching operations found for port type{" "}
              <code className="text-[var(--color-primary)] font-mono">{originPort.type}</code>.
            </p>
            {!showAllOps && (
              <button
                type="button"
                data-testid="btn-show-all-ops"
                onClick={() => setShowAllOps(true)}
                className="text-xs text-[var(--color-primary)] underline hover:opacity-80"
              >
                Show all operations anyway
              </button>
            )}
          </div>
        ) : (
          filteredOptions.map((opt, idx) => {
            const isSelected = idx === selectedIndex;
            return (
              <button
                key={`${opt.op.id}__${opt.port.name}`}
                type="button"
                data-testid={`quick-connect-item-${opt.op.id}-${opt.port.name}`}
                onClick={() => onSelect(opt.op.id, opt.port.name)}
                onMouseEnter={() => setSelectedIndex(idx)}
                className={`w-full text-left px-2.5 py-1.5 rounded flex items-center justify-between transition-colors ${
                  isSelected
                    ? "bg-[rgba(38,128,235,0.22)] text-[var(--text-primary)]"
                    : "hover:bg-[var(--bg-button-hover)] text-[var(--text-secondary)]"
                }`}
              >
                <div className="min-w-0 pr-2">
                  <div className="font-medium text-[var(--text-primary)] truncate">
                    {opt.op.title}
                  </div>
                  <div className="text-[11px] text-[var(--text-tertiary)] flex items-center gap-1 font-mono">
                    <span className="text-[var(--color-primary)]">↳ {opt.port.name}</span>
                    <span>({opt.port.type})</span>
                  </div>
                </div>
                <div className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[var(--bg-canvas)] text-[var(--text-tertiary)] flex-shrink-0">
                  {opt.op.category || "General"}
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer hotkey tip */}
      <div className="px-3 py-1.5 text-[10px] text-[var(--text-tertiary)] border-t border-[var(--border-default)] bg-[var(--bg-canvas)] flex items-center justify-between select-none">
        <span>↑↓ Navigate &bull; Enter Select</span>
        <span>Esc Cancel</span>
      </div>
    </div>
  );
}
