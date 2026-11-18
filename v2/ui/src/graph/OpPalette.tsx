import { useEffect, useMemo, useRef, useState } from "react";
import type { OpEntry } from "../api/types.gen";

export interface OpPaletteProps {
  ops: ReadonlyArray<OpEntry>;
  stages: ReadonlyArray<string>;
  targetStage: string;
  onTargetStageChange: (stageId: string) => void;
  onAddOp: (op: OpEntry) => void;
}

export const OP_DRAG_MIME = "application/x-plynx-op-id";

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

export function OpPalette({
  ops,
  stages,
  targetStage,
  onTargetStageChange,
  onAddOp,
}: OpPaletteProps) {
  const [query, setQuery] = useState<string>("");
  const [collapsedCategories, setCollapsedCategories] = useState<
    Record<string, boolean>
  >({});
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
        return;
      }
      if (
        event.key === "/" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !isEditableTarget(event.target)
      ) {
        event.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const groupedOps = useMemo(() => {
    const q = query.trim().toLowerCase();
    const groups: Record<string, Array<OpEntry>> = {};

    for (const op of ops) {
      if (q) {
        const haystack =
          `${op.title} ${op.name} ${op.id} ${op.category} ${op.description}`.toLowerCase();
        if (!haystack.includes(q)) continue;
      }
      const cat = op.category || "Uncategorized";
      if (!groups[cat]) {
        groups[cat] = [];
      }
      groups[cat].push(op);
    }

    return Object.entries(groups)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([category, items]) => ({
        category,
        items: [...items].sort((a, b) => a.title.localeCompare(b.title)),
      }));
  }, [ops, query]);

  const toggleCategory = (category: string) => {
    setCollapsedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  return (
    <aside
      data-testid="op-palette"
      className="flex h-full w-64 shrink-0 flex-col rounded-lg border border-slate-800 bg-slate-900/60 overflow-hidden"
    >
      <div className="border-b border-slate-800 p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Operations
          </h2>
          <span className="font-mono text-[10px] text-slate-500">
            / or ⌘K
          </span>
        </div>

        <div className="relative">
          <input
            ref={searchInputRef}
            data-testid="palette-search"
            type="text"
            placeholder="Search operations..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setQuery("");
                searchInputRef.current?.blur();
              }
            }}
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-500 hover:text-slate-300"
            >
              &times;
            </button>
          )}
        </div>

        {stages.length > 0 && (
          <div className="flex items-center gap-2 text-[11px]">
            <label htmlFor="palette-target-stage" className="text-slate-400 shrink-0">
              Add to stage:
            </label>
            <select
              id="palette-target-stage"
              data-testid="palette-target-stage"
              value={targetStage}
              onChange={(e) => onTargetStageChange(e.target.value)}
              className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[11px] text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              {stages.map((stageId) => (
                <option key={stageId} value={stageId}>
                  {stageId}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {groupedOps.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500">
            No operations match &ldquo;{query}&rdquo;.
          </div>
        ) : (
          groupedOps.map(({ category, items }) => {
            const isCollapsed = Boolean(collapsedCategories[category]) && !query.trim();
            return (
              <div
                key={category}
                data-testid={`palette-category-${category}`}
                className="space-y-1"
              >
                <button
                  type="button"
                  onClick={() => toggleCategory(category)}
                  className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                >
                  <span className="truncate">{category}</span>
                  <span className="font-mono text-[10px] text-slate-500">
                    {isCollapsed ? "+" : "−"} {items.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="space-y-1 pl-1">
                    {items.map((op) => (
                      <button
                        key={op.id}
                        type="button"
                        data-testid={`palette-op-${op.id}`}
                        disabled={!op.valid}
                        draggable={op.valid}
                        onDragStart={(e) => {
                          e.dataTransfer.setData(OP_DRAG_MIME, op.id);
                          e.dataTransfer.effectAllowed = "copy";
                        }}
                        onClick={() => {
                          if (op.valid) onAddOp(op);
                        }}
                        title={
                          op.valid
                            ? `${op.description || op.title} — click or drag to add`
                            : `Invalid op: ${op.error ?? "unknown error"}`
                        }
                        className={`group flex w-full flex-col rounded-md border px-2.5 py-2 text-left transition-colors ${
                          op.valid
                            ? "border-slate-800 bg-slate-950/70 hover:border-emerald-600/70 hover:bg-slate-900 cursor-pointer"
                            : "border-rose-900/50 bg-rose-950/20 opacity-60 cursor-not-allowed"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1.5">
                          <span className="truncate text-xs font-medium text-slate-200 group-hover:text-white">
                            {op.title}
                          </span>
                          <span className="shrink-0 text-[10px] text-emerald-400 opacity-0 group-hover:opacity-100">
                            + Add
                          </span>
                        </div>
                        <span className="truncate font-mono text-[10px] text-slate-500">
                          {op.id}
                        </span>
                        {op.description && (
                          <span className="mt-0.5 line-clamp-1 text-[10px] text-slate-400">
                            {op.description}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
