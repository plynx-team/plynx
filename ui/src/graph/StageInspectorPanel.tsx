import { useState } from "react";
import type {
  AgentProvider,
  GraphEditPolicy,
  InputPortSpec,
  OpEntry,
  StageValidatorSpec,
  ValidatorMode,
  Workflow,
} from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";
import { PortInput } from "../components/PortInput";
import { DEFAULT_STAGE_ID, DEFAULT_STAGE_TITLE, getOrderedStageIds } from "./layout";

const DEFAULT_VALIDATOR_OP = "standard_io/agent:StageSupervisor";

const AGENT_PROVIDER_OPTIONS: ReadonlyArray<AgentProvider> = [
  "default",
  "claude",
  "cursor",
  "codex",
  "gemini",
  "opencode",
  "goose",
  "aider",
  "custom",
  "mock",
];

const FALLBACK_VALIDATOR_PORTS: ReadonlyArray<InputPortSpec> = [
  {
    name: "prompt_file",
    type: "file",
    media: "text/markdown",
    required: false,
    default: null,
    description: "Optional Markdown file with domain instructions.",
  },
  {
    name: "prompt",
    type: "str",
    required: false,
    default: "",
    description: "Inline domain instructions.",
  },
  {
    name: "provider",
    type: "str",
    options: [...AGENT_PROVIDER_OPTIONS],
    required: false,
    default: "default",
    description: "Coding agent CLI provider.",
  },
  {
    name: "model",
    type: "str",
    required: false,
    default: "",
    description: "Optional model identifier override.",
  },
];

export interface StageInspectorPanelProps {
  selectedStageId: string;
  workflow: Workflow;
  opsMap?: Record<string, OpEntry>;
  readOnly?: boolean;
  onSelectStage?: (stageId: string | undefined) => void;
  onUpdateStage?: (
    stageId: string,
    patch: {
      title?: string;
      require_approval?: boolean;
      validator?: StageValidatorSpec | null;
    },
  ) => void;
  onDeleteStage?: (stageId: string) => void;
  onReorderStages?: (
    newOrder: string[],
  ) => { success: boolean; reason?: string };
}

export function StageInspectorPanel({
  selectedStageId,
  workflow,
  opsMap = {},
  readOnly = false,
  onSelectStage,
  onUpdateStage,
  onDeleteStage,
  onReorderStages,
}: StageInspectorPanelProps) {
  const [stageError, setStageError] = useState<string | null>(null);
  const stageIds = getOrderedStageIds(workflow);
  const stageSpec = workflow.stages?.[selectedStageId];
  const validator = stageSpec?.validator ?? null;
  const isDefaultStage = selectedStageId === DEFAULT_STAGE_ID;
  const stageIndex = stageIds.indexOf(selectedStageId);
  const canMoveEarlier = stageIndex > 0;
  const canMoveLater = stageIndex >= 0 && stageIndex < stageIds.length - 1;
  const memberNodes = Object.entries(workflow.nodes ?? {}).filter(
    ([, n]) => (n.stage || DEFAULT_STAGE_ID) === selectedStageId,
  );

  const candidateValidatorOps = Object.values(opsMap).filter(
    (op) =>
      op.valid && (op.agent_role === "validator" || op.agent_role === "agent"),
  );
  const validatorOpEntry = validator ? opsMap[validator.op] : undefined;
  const validatorPorts: ReadonlyArray<InputPortSpec> =
    validatorOpEntry && validatorOpEntry.inputs.length > 0
      ? validatorOpEntry.inputs
      : FALLBACK_VALIDATOR_PORTS;

  const handleAttachValidator = () => {
    const preferred =
      candidateValidatorOps.find((op) => op.agent_role === "validator")?.id ??
      candidateValidatorOps[0]?.id ??
      DEFAULT_VALIDATOR_OP;
    onUpdateStage?.(selectedStageId, {
      validator: {
        op: preferred,
        mode: "on_anomaly",
        allow_graph_edits: "confirm",
        inputs: {},
      },
    });
  };

  const handleUpdateValidator = (patch: Partial<StageValidatorSpec>) => {
    if (!validator) return;
    onUpdateStage?.(selectedStageId, {
      validator: {
        ...validator,
        ...patch,
      },
    });
  };

  const handleValidatorPortChange = (portName: string, nextVal: unknown) => {
    if (!validator) return;
    const nextInputs = { ...(validator.inputs ?? {}) };
    if (nextVal === undefined) {
      delete nextInputs[portName];
    } else {
      nextInputs[portName] = nextVal;
    }
    handleUpdateValidator({ inputs: nextInputs });
  };

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

        {/* Stage Validator / Supervisor Box */}
        <div className="PropertiesBox" data-testid="stage-validator-editor">
          <div className="PropertiesBoxHeader flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <FeatherIcon
                name="shield"
                size={12}
                style={{ color: "var(--color-primary)" }}
              />
              <span>Stage Validator</span>
            </span>
            {!readOnly &&
              (validator ? (
                <button
                  type="button"
                  data-testid="btn-remove-stage-validator"
                  onClick={() =>
                    onUpdateStage?.(selectedStageId, { validator: null })
                  }
                  className="control-button danger !h-5 !min-h-5 !px-1.5 !text-[10px]"
                >
                  <FeatherIcon name="trash-2" size={10} />
                  <span>Remove</span>
                </button>
              ) : (
                <button
                  type="button"
                  data-testid="btn-attach-stage-validator"
                  onClick={handleAttachValidator}
                  className="control-button !h-5 !min-h-5 !px-1.5 !text-[10px]"
                >
                  <FeatherIcon name="plus" size={10} />
                  <span>Attach</span>
                </button>
              ))}
          </div>

          <div className="PropertiesBoxContent space-y-2 text-xs">
            {!validator ? (
              <p
                className="py-1 italic"
                style={{ color: "var(--text-tertiary)" }}
              >
                No validator attached. Attach a Stage Validator to inspect anomalies or propose bounded DAG repairs.
              </p>
            ) : (
              <>
                <div className="ParameterItem">
                  <label
                    htmlFor="validator-op-input"
                    className="ParameterNameCell"
                  >
                    Validator Op
                  </label>
                  <div className="ParameterValueCell">
                    {candidateValidatorOps.length > 0 ? (
                      <select
                        id="validator-op-input"
                        data-testid="validator-op-select"
                        disabled={readOnly}
                        value={validator.op}
                        onChange={(e) =>
                          handleUpdateValidator({ op: e.target.value })
                        }
                        className="w-full px-1.5 py-1 text-xs font-mono"
                      >
                        {!candidateValidatorOps.some(
                          (op) => op.id === validator.op,
                        ) && (
                          <option value={validator.op}>{validator.op}</option>
                        )}
                        {candidateValidatorOps.map((op) => (
                          <option key={op.id} value={op.id}>
                            {op.title} ({op.id})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id="validator-op-input"
                        data-testid="validator-op-input"
                        type="text"
                        disabled={readOnly}
                        value={validator.op}
                        onChange={(e) =>
                          handleUpdateValidator({ op: e.target.value })
                        }
                        className="w-full px-1.5 py-1 text-xs font-mono"
                      />
                    )}
                  </div>
                </div>

                <div className="ParameterItem">
                  <label
                    htmlFor="validator-mode-select"
                    className="ParameterNameCell"
                  >
                    Trigger Mode
                  </label>
                  <div className="ParameterValueCell">
                    <select
                      id="validator-mode-select"
                      data-testid="validator-mode-select"
                      disabled={readOnly}
                      value={validator.mode ?? "on_anomaly"}
                      onChange={(e) =>
                        handleUpdateValidator({
                          mode: e.target.value as ValidatorMode,
                        })
                      }
                      className="w-full px-1.5 py-1 text-xs"
                    >
                      <option value="on_anomaly">
                        on_anomaly (warnings or failures)
                      </option>
                      <option value="on_failure">
                        on_failure (exit 1 failures only)
                      </option>
                      <option value="always">always</option>
                    </select>
                  </div>
                </div>

                <div className="ParameterItem">
                  <label
                    htmlFor="validator-edit-policy-select"
                    className="ParameterNameCell"
                  >
                    Graph Edits
                  </label>
                  <div className="ParameterValueCell">
                    <select
                      id="validator-edit-policy-select"
                      data-testid="validator-edit-policy-select"
                      disabled={readOnly}
                      value={validator.allow_graph_edits ?? "confirm"}
                      onChange={(e) =>
                        handleUpdateValidator({
                          allow_graph_edits: e.target.value as GraphEditPolicy,
                        })
                      }
                      className="w-full px-1.5 py-1 text-xs"
                    >
                      <option value="confirm">confirm (human approval)</option>
                      <option value="auto">auto (apply automatically)</option>
                      <option value="forbidden">forbidden (read-only)</option>
                    </select>
                  </div>
                </div>

                <div className="pt-1.5 border-t border-[#3c3c3c] space-y-2">
                  <div
                    className="text-[11px] font-semibold"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Validator Inputs
                  </div>
                  {validatorPorts.map((port) => (
                    <div key={port.name} className="space-y-1">
                      <label
                        htmlFor={`validator-port-${port.name}`}
                        className="block font-mono text-[11px]"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {port.name}
                      </label>
                      <PortInput
                        id={`validator-port-${port.name}`}
                        testId={`validator-input-${port.name}`}
                        port={port}
                        value={validator.inputs?.[port.name]}
                        readOnly={readOnly}
                        showPresets={false}
                        onChange={(nextVal) =>
                          handleValidatorPortChange(port.name, nextVal)
                        }
                      />
                    </div>
                  ))}
                </div>
              </>
            )}
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
