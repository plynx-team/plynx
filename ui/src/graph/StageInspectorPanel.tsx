import { useState } from "react";
import type { Workflow } from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";
import { DEFAULT_STAGE_ID, DEFAULT_STAGE_TITLE, getOrderedStageIds } from "./layout";

export interface StageInspectorPanelProps {
  selectedStageId: string;
  workflow: Workflow;
  readOnly?: boolean;
  onSelectStage?: (stageId: string | undefined) => void;
  onUpdateStage?: (
    stageId: string,
    patch: { title?: string; require_approval?: boolean },
  ) => void;
  onDeleteStage?: (stageId: string) => void;
  onReorderStages?: (
    newOrder: string[],
  ) => { success: boolean; reason?: string };
}

export function StageInspectorPanel({
  selectedStageId,
  workflow,
  readOnly = false,
  onSelectStage,
  onUpdateStage,
  onDeleteStage,
  onReorderStages,
}: StageInspectorPanelProps) {
  const [stageError, setStageError] = useState<string | null>(null);
  const stageIds = getOrderedStageIds(workflow);
  const stageSpec = workflow.stages?.[selectedStageId];
  const isDefaultStage = selectedStageId === DEFAULT_STAGE_ID;
  const stageIndex = stageIds.indexOf(selectedStageId);
  const canMoveEarlier = stageIndex > 0;
  const canMoveLater = stageIndex >= 0 && stageIndex < stageIds.length - 1;
  const memberNodes = Object.entries(workflow.nodes ?? {}).filter(
    ([, n]) => (n.stage || DEFAULT_STAGE_ID) === selectedStageId,
  );

  const handleMove = (direction: "earlier" | "later") => {
    if (!onReorderStages) return;
    const targetIdx = direction === "earlier" ? stageIndex - 1 : stageIndex + 1;
    const nextOrder = [...stageIds];
    const temp = nextOrder[stageIndex];
    nextOrder[stageIndex] = nextOrder[targetIdx];
    nextOrder[targetIdx] = temp;
    const res = onReorderStages(nextOrder);
    if (!res.success && res.reason) {
      setStageError(res.reason);
    } else {
      setStageError(null);
    }
  };

  return (
    <aside
      data-testid="stage-inspector"
      className="PropertiesBar"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="PropertiesHeader">
        <div className="flex items-center gap-1.5 truncate">
          <FeatherIcon
            name="layers"
            size={14}
            style={{ color: "var(--color-primary)" }}
          />
          <span className="truncate">
            Stage: {stageSpec?.title || selectedStageId}
          </span>
        </div>
        {onSelectStage && (
          <button
            type="button"
            aria-label="Close stage properties"
            onClick={() => onSelectStage(undefined)}
            className="control-button h-5 min-h-5 px-1.5 text-[10px]"
          >
            <FeatherIcon name="x" size={12} />
          </button>
        )}
      </div>

      <div className="PropertiesBoxRoot">
        <div className="PropertiesBox">
          <div className="PropertiesBoxHeader">Stage Details</div>
          <div className="PropertiesBoxContent space-y-2">
            <div className="ParameterItem">
              <div className="ParameterNameCell">Stage ID</div>
              <div className="ParameterValueCell font-mono text-xs flex items-center gap-1">
                <span>{selectedStageId}</span>
                {isDefaultStage && (
                  <span className="status-badge CREATED text-[9px]">Default</span>
                )}
              </div>
            </div>

            <div className="ParameterItem">
              <label
                htmlFor="inspector-stage-title"
                className="ParameterNameCell"
              >
                Title
              </label>
              <div className="ParameterValueCell">
                <input
                  id="inspector-stage-title"
                  data-testid="inspector-stage-title"
                  type="text"
                  disabled={readOnly}
                  value={
                    stageSpec?.title ??
                    (isDefaultStage ? DEFAULT_STAGE_TITLE : selectedStageId)
                  }
                  onChange={(e) =>
                    onUpdateStage?.(selectedStageId, { title: e.target.value })
                  }
                  className="w-full px-1.5 py-1 text-xs"
                />
              </div>
            </div>

            <div className="pt-1 border-t border-[#3c3c3c]">
              <label className="flex items-start gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  data-testid="inspector-stage-gate-checkbox"
                  disabled={readOnly}
                  checked={Boolean(stageSpec?.require_approval)}
                  onChange={(e) =>
                    onUpdateStage?.(selectedStageId, {
                      require_approval: e.target.checked,
                    })
                  }
                  className="mt-0.5 rounded"
                />
                <div className="text-xs">
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Approval Gate
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Pauses the run before downstream stages start until approved.
                  </span>
                </div>
              </label>
            </div>
          </div>
        </div>

        <div className="PropertiesBox">
          <div className="PropertiesBoxHeader">Stage Order</div>
          <div className="PropertiesBoxContent space-y-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span style={{ color: "var(--text-secondary)" }}>
                Position: #{stageIndex + 1} of {stageIds.length}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  data-testid="btn-stage-move-earlier"
                  disabled={readOnly || !canMoveEarlier}
                  onClick={() => handleMove("earlier")}
                  title="Move stage earlier in execution order"
                  className="control-button h-6 min-h-6 px-2 text-xs"
                >
                  <FeatherIcon name="chevron-up" size={12} />
                  <span>Earlier</span>
                </button>
                <button
                  type="button"
                  data-testid="btn-stage-move-later"
                  disabled={readOnly || !canMoveLater}
                  onClick={() => handleMove("later")}
                  title="Move stage later in execution order"
                  className="control-button h-6 min-h-6 px-2 text-xs"
                >
                  <FeatherIcon name="chevron-down" size={12} />
                  <span>Later</span>
                </button>
              </div>
            </div>
            {stageError && (
              <p
                role="alert"
                data-testid="inspector-stage-reorder-error"
                className="mt-1 text-[11px]"
                style={{ color: "var(--color-error)" }}
              >
                {stageError}
              </p>
            )}
          </div>
        </div>

        <div className="PropertiesBox">
          <div className="PropertiesBoxHeader">
            <span>Operations ({memberNodes.length})</span>
          </div>
          <div className="PropertiesBoxContent text-xs">
            {memberNodes.length === 0 ? (
              <p
                className="py-1 italic"
                style={{ color: "var(--text-tertiary)" }}
              >
                No operations in this stage.
              </p>
            ) : (
              <div className="space-y-1">
                {memberNodes.map(([nid, nSpec]) => (
                  <div
                    key={nid}
                    className="flex items-center justify-between px-2 py-1 rounded bg-[#242424] border border-[#363636]"
                  >
                    <span className="font-semibold truncate">
                      {nSpec.title || nid}
                    </span>
                    <span
                      className="font-mono text-[10px]"
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      {nid}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {!readOnly && onDeleteStage && (
          <div className="pt-2">
            <button
              type="button"
              data-testid="btn-delete-stage-inspector"
              disabled={stageIds.length <= 1}
              title={
                stageIds.length <= 1
                  ? "Cannot delete the only stage in the workflow"
                  : "Delete stage"
              }
              onClick={() => onDeleteStage(selectedStageId)}
              className="control-button danger w-full justify-center h-7 text-xs"
            >
              <FeatherIcon name="trash-2" size={12} />
              <span>
                {memberNodes.length === 0
                  ? "Delete Empty Stage"
                  : `Delete Stage (${memberNodes.length} ${
                      memberNodes.length === 1 ? "op" : "ops"
                    })`}
              </span>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
