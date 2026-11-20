import { useEffect, useMemo, useRef, useState } from "react";
import type { OpEntry } from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";

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
    <aside data-testid="op-palette" className="hub-panel">
      <div className="hub-list-header space-y-1.5">
        <div className="SearchBar w-full">
          <FeatherIcon
            name="search"
            size={13}
            style={{ color: "var(--text-tertiary)" }}
          />
          <input
            ref={searchInputRef}
            data-testid="palette-search"
            type="text"
            placeholder="Search operations (/ or ⌘K)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setQuery("");
                searchInputRef.current?.blur();
              }
            }}
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery("")}
              className="text-xs px-1"
              style={{ color: "var(--text-secondary)" }}
            >
              <FeatherIcon name="x" size={12} />
            </button>
          )}
        </div>

        {stages.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs">
            <label
              htmlFor="palette-target-stage"
              className="shrink-0"
              style={{ color: "var(--text-secondary)" }}
            >
              Stage:
            </label>
            <select
              id="palette-target-stage"
              data-testid="palette-target-stage"
              value={targetStage}
              onChange={(e) => onTargetStageChange(e.target.value)}
              className="min-w-0 flex-1 px-1.5 py-0.5 text-xs"
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

      <div className="hub-entry-list space-y-1">
        {groupedOps.length === 0 ? (
          <div
            className="p-4 text-center text-xs"
            style={{ color: "var(--text-tertiary)" }}
          >
            No operations match &ldquo;{query}&rdquo;.
          </div>
        ) : (
          groupedOps.map(({ category, items }) => {
            const isCollapsed =
              Boolean(collapsedCategories[category]) && !query.trim();
            return (
              <div
                key={category}
                data-testid={`palette-category-${category}`}
                className="hub-box"
              >
                <button
                  type="button"
                  onClick={() => toggleCategory(category)}
                  className="hub-entry-group-title w-full"
                >
                  <span className="flex items-center gap-1.5 truncate">
                    <FeatherIcon
                      name={isCollapsed ? "chevron-right" : "chevron-down"}
                      size={13}
                    />
                    <span className="truncate">{category}</span>
                  </span>
                  <span
                    className="font-mono text-[11px]"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {items.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="pl-2 pr-0.5 py-0.5 space-y-1">
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
                            ? `${op.description || op.title} (${op.id})`
                            : `Invalid op: ${op.error ?? "unknown error"}`
                        }
                        className="hub-item-node"
                      >
                        <FeatherIcon
                          name="cpu"
                          size={13}
                          style={{
                            color: op.valid
                              ? "var(--color-primary)"
                              : "var(--color-error)",
                          }}
                        />
                        <span className="hub-item-node-text">{op.title}</span>
                        <FeatherIcon
                          name="help-circle"
                          size={12}
                          style={{ color: "var(--text-tertiary)" }}
                        />
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
